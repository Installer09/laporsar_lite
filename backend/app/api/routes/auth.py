from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta
import jwt
import uuid
import logging
from app.core.config import settings
from app.db.session import get_db, get_master_db, get_tenant, get_tenant_sessionmaker, get_redis
from app.models.settings_models import User
from app.models.master_models import Tenant, UserTenantMapping
from app.schemas.settings_schemas import ForgotPasswordRequest, ResetPasswordRequest, UserCreate, UserResponse, UserUpdate
from app.core.security import verify_password, get_password_hash, verify_jwt
from app.core.rate_limiter import check_rate_limit, record_failed_attempt, reset_failed_attempts
from app.services.email_service import email_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(redirect_slashes=False)

class LoginRequest(BaseModel):
    username: str # This is the email
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest, 
    http_req: Request = None,
    db: AsyncSession = Depends(get_db), 
    db_master: AsyncSession = Depends(get_master_db),
    tenant = Depends(get_tenant),
    redis = Depends(get_redis)
):
    # Rate limit check: max 15 login attempts per minute per IP
    client_ip = http_req.client.host if (http_req and http_req.client) else "unknown"
    allowed = await check_rate_limit(redis, f"login_ip:{client_ip}", max_requests=15, window_seconds=60)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Terlalu banyak percobaan login dari alamat IP ini. Silakan tunggu beberapa saat."
        )

    # 1. Dev Admin check first (always allowed to bypass)
    if (
        settings.DEV_ADMIN_ENABLED
        and request.username == settings.DEV_ADMIN_USERNAME
        and request.password == settings.DEV_ADMIN_PASSWORD
    ):
        payload = {
            "sub": settings.DEV_ADMIN_USERNAME,
            "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            "role": "admin",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}

    # 2. Centralized Login resolution if tenant DB is not pre-resolved
    resolved_db = db
    resolved_tenant_slug = tenant.slug if tenant else None

    if not resolved_db:
        # Query master DB to find tenant slug for this email
        email_clean = request.username.lower().strip()
        result_map = await db_master.execute(
            select(UserTenantMapping).where(UserTenantMapping.email == email_clean)
        )
        mapping = result_map.scalar_one_or_none()
        if not mapping:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Username atau password salah")
        
        resolved_tenant_slug = mapping.tenant_slug
        
        # Get tenant connection details from Master DB
        result_tenant = await db_master.execute(
            select(Tenant).where(Tenant.slug == resolved_tenant_slug, Tenant.is_active == True)
        )
        active_tenant = result_tenant.scalar_one_or_none()
        if not active_tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Instansi Anda sedang dinonaktifkan."
            )
        
        # Get temporary DB session for the resolved tenant
        tenant_sessionmaker = get_tenant_sessionmaker(active_tenant.db_url)
        async with tenant_sessionmaker() as temp_db:
            # Find user and verify password in the resolved database
            result_user = await temp_db.execute(select(User).where(User.email == request.username))
            user = result_user.scalar_one_or_none()
            
            if not user or not verify_password(request.password, user.hashed_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Username atau password salah")
            
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
            
            # Generate token
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            payload = {
                "sub": user.email,
                "exp": expire,
                "role": user.role,
                "user_id": user.id,
                "tenant_slug": resolved_tenant_slug
            }
            token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
            return {"access_token": token, "token_type": "bearer"}

    # 3. Existing subdomain-based login fallback
    result = await resolved_db.execute(select(User).where(User.email == request.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Username atau password salah")
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user.email,
        "exp": expire,
        "role": user.role,
        "user_id": user.id,
        "tenant_slug": resolved_tenant_slug
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse)
async def register(
    user_in: UserCreate, 
    db: AsyncSession = Depends(get_db),
    db_master: AsyncSession = Depends(get_master_db),
    tenant = Depends(get_tenant)
):
    if not db or not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Tenant-Slug, parameter path tenant_slug, atau subdomain wajib disertakan saat registrasi."
        )

    email_clean = user_in.email.lower().strip()

    # 1. Enforce global email uniqueness by checking master DB first
    result_map = await db_master.execute(
        select(UserTenantMapping).where(UserTenantMapping.email == email_clean)
    )
    if result_map.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Check local user table in tenant DB just in case
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = get_password_hash(user_in.password)
    new_user = User(
        name=user_in.name,
        email=user_in.email,
        phone=user_in.phone,
        role="User",  # Enforce User role for self-registration
        hashed_password=hashed_pwd,
        is_active=True,  # Auto-activate for citizen reporting
        is_verified=False
    )
    
    # 3. Create mapping
    new_mapping = UserTenantMapping(
        email=email_clean,
        tenant_slug=tenant.slug
    )

    db.add(new_user)
    db_master.add(new_mapping)
    
    # Commit to master first
    try:
        await db_master.commit()
    except Exception as master_err:
        await db_master.rollback()
        await db.rollback()
        logger.error(f"Failed to commit master user mapping registry during registration: {master_err}")
        raise HTTPException(status_code=500, detail="Database transaction failed on master registry")

    # Commit to tenant DB
    try:
        await db.commit()
        await db.refresh(new_user)
        return new_user
    except Exception as tenant_err:
        await db.rollback()
        logger.error(f"Tenant DB commit failed during registration, triggering compensator on master: {tenant_err}")
        
        # Compensating transaction to delete mapping from master DB
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as compensating_session:
                stmt = select(UserTenantMapping).where(
                    UserTenantMapping.email == email_clean
                )
                res = await compensating_session.execute(stmt)
                m = res.scalar_one_or_none()
                if m:
                    await compensating_session.delete(m)
                    await compensating_session.commit()
                    logger.info(f"Successfully cleaned up master mapping for {email_clean}")
        except Exception as comp_err:
            logger.error(f"CRITICAL: Failed to clean up master registry mapping for {email_clean}: {comp_err}")
            
        raise HTTPException(status_code=500, detail="Database transaction failed on tenant database")


@router.get("/me", response_model=UserResponse)
async def get_me(payload: dict = Depends(verify_jwt), db: AsyncSession = Depends(get_db)):
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")
        
    if not db:
        if email == settings.DEV_ADMIN_USERNAME:
            return UserResponse(
                id=0, name="Admin Dev", email=email, role="admin", 
                is_active=True, is_verified=True, photo_url=None
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Tenant-Slug, parameter path tenant_slug, atau subdomain tidak terdeteksi."
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        if email == settings.DEV_ADMIN_USERNAME:
            # Mock admin user for dev
            return UserResponse(
                id=0, name="Admin Dev", email=email, role="admin", 
                is_active=True, is_verified=True, photo_url=None
            )
        raise HTTPException(status_code=404, detail="User not found")
        
    return user

@router.put("/me", response_model=UserResponse)
async def update_me(user_update: UserUpdate, payload: dict = Depends(verify_jwt), db: AsyncSession = Depends(get_db)):
    email = payload.get("sub")
    if not email or email == settings.DEV_ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Cannot modify dev admin profile")
        
    result = await db.execute(select(User).where(User.email == email))
    db_user = result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user_update.name is not None: db_user.name = user_update.name
    if user_update.phone is not None: db_user.phone = user_update.phone
    if user_update.photo_url is not None: db_user.photo_url = user_update.photo_url
    if user_update.password and user_update.password.strip(): 
        db_user.hashed_password = get_password_hash(user_update.password.strip())
    
    try:
        await db.commit()
        await db.refresh(db_user)
        return db_user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update user {email}: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    
    if not user:
        # For security, don't reveal if email exists
        return {"status": "success", "message": "If the email is registered, a reset link will be sent."}
    
    token = str(uuid.uuid4())
    user.reset_token = token
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save reset token for {user.email}: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

    
    # Send email
    sent = email_service.send_reset_password_email(user.email, token)
    if not sent:
        logger.warning(f"Password reset email could not be sent for {user.email}. Check SMTP config.")

    return {"status": "success", "message": "Reset link sent to your email."}

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.reset_token == req.token))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    
    user.hashed_password = get_password_hash(req.new_password)
    user.reset_token = None # Clear token
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to reset password: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")
    
    return {"status": "success", "message": "Password updated successfully. You can now login."}
