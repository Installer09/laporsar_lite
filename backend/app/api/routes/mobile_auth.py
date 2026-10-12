import logging
import secrets
import json
from datetime import datetime, timezone, timedelta
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as redis_client

from app.db.session import get_master_db, get_tenant_sessionmaker, get_redis
from app.models.master_models import Tenant
from app.models.contact import Contact
from app.schemas.mobile_auth import OTPRequest, OTPVerify, MobileLoginResponse, MobileContactResponse
from app.services.reply_dispatcher import ReplyDispatcher
from app.core.tenant_config import get_tenant_settings
from app.core.config import settings as global_settings

logger = logging.getLogger(__name__)
router = APIRouter(redirect_slashes=False)

# Helper to get the pusat tenant database session
async def get_pusat_db(db_master: AsyncSession = Depends(get_master_db)) -> AsyncSession:
    result = await db_master.execute(
        select(Tenant).where(Tenant.slug == "pusat", Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=500,
            detail="Tenant 'pusat' tidak ditemukan atau tidak aktif."
        )
    session_maker = get_tenant_sessionmaker(tenant.db_url)
    async with session_maker() as session:
        session.info["tenant_slug"] = "pusat"
        yield session

@router.post("/otp/request")
async def request_otp(
    req: OTPRequest,
    db_pusat: AsyncSession = Depends(get_pusat_db),
    redis: redis_client.Redis = Depends(get_redis)
):
    """
    Generate OTP code and send it to the user's phone number via WhatsApp.
    Stores name and OTP in Redis with a 5-minute TTL.
    """
    phone = req.phone_number
    name = req.name

    # Rate limiting: Max 3 OTP requests per 5 minutes per phone
    from app.core.rate_limiter import check_rate_limit, record_failed_attempt, reset_failed_attempts
    allowed = await check_rate_limit(redis, f"otp_req:{phone}", max_requests=3, window_seconds=300)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Terlalu banyak permintaan OTP. Silakan tunggu beberapa menit sebelum mencoba kembali."
        )

    # Generate 6-digit OTP code using cryptographically secure random numbers (CWE-330 mitigation)
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    logger.info(f"Generated OTP {otp_code} for mobile user {phone} ({name})")

    # Store OTP and name in Redis
    redis_key = f"otp:{phone}"
    redis_data = {
        "otp": otp_code,
        "name": name
    }
    try:
        await redis.setex(redis_key, 300, json.dumps(redis_data))
    except Exception as redis_err:
        logger.error(f"Failed to store OTP in Redis: {redis_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memproses OTP. Layanan cache bermasalah."
        )

    # Get WhatsApp configurations for 'pusat'
    tenant_settings = await get_tenant_settings(db_pusat)
    wa_token = tenant_settings.WHATSAPP_API_TOKEN
    phone_id = tenant_settings.WHATSAPP_PHONE_NUMBER_ID

    # Send OTP message
    otp_message = (
        f"Halo {name},\n\n"
        f"Kode OTP Lapor SAR Anda adalah: *{otp_code}*\n\n"
        "Kode ini rahasia, berlaku selama 5 menit, dan digunakan untuk masuk ke aplikasi Lapor SAR Mobile."
    )
    
    # Send using reply dispatcher
    sent = await ReplyDispatcher.send_whatsapp_reply(
        recipient_phone=phone,
        text=otp_message,
        wa_token=wa_token,
        phone_id=phone_id
    )

    if not sent:
        # In development mode, we can allow falling back / showing OTP in response if WhatsApp is not configured
        if global_settings.DEV_ADMIN_ENABLED:
            logger.warning("WhatsApp API not configured or failed to send OTP. Developer mode is active, returning OTP in response.")
            return {
                "status": "success",
                "message": "OTP terkirim (mode pengembang)",
                "dev_otp": otp_code  # Only return for development ease
            }
        
        logger.error(f"Failed to send WhatsApp OTP to {phone}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gagal mengirimkan kode OTP via WhatsApp. Pastikan nomor terdaftar WhatsApp."
        )

    return {
        "status": "success",
        "message": "Kode OTP berhasil dikirimkan via WhatsApp."
    }

@router.post("/otp/verify", response_model=MobileLoginResponse)
async def verify_otp(
    req: OTPVerify,
    db_pusat: AsyncSession = Depends(get_pusat_db),
    redis: redis_client.Redis = Depends(get_redis)
):
    """
    Verify the OTP code. If valid, register/update the Contact in the 'pusat' DB and issue a JWT token.
    """
    phone = req.phone_number
    code = req.otp_code

    redis_key = f"otp:{phone}"
    try:
        cached_data_str = await redis.get(redis_key)
    except Exception as redis_err:
        logger.error(f"Failed to fetch OTP from Redis: {redis_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memverifikasi OTP. Layanan cache bermasalah."
        )

    if not cached_data_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kode OTP kedaluwarsa atau tidak ditemukan. Silakan minta kode baru."
        )

    cached_data = json.loads(cached_data_str)
    stored_otp = cached_data.get("otp")
    stored_name = cached_data.get("name")

    if stored_otp != code:
        from app.core.rate_limiter import record_failed_attempt
        attempts, is_locked = await record_failed_attempt(redis, f"otp_verify:{phone}", max_attempts=5, window_seconds=300)
        if is_locked:
            try:
                await redis.delete(redis_key)
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Terlalu banyak percobaan salah. Kode OTP telah dibatalkan demi keamanan."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kode OTP yang Anda masukkan salah (percobaan {attempts}/5)."
        )

    # OTP is correct -> reset attempts and delete from Redis
    try:
        from app.core.rate_limiter import reset_failed_attempts
        await reset_failed_attempts(redis, f"otp_verify:{phone}")
        await redis.delete(redis_key)
    except Exception as redis_del_err:
        logger.warning(f"Failed to delete verified OTP from Redis: {redis_del_err}")

    # Check and register contact in DB
    try:
        # Search by phone number
        result = await db_pusat.execute(
            select(Contact).where(Contact.phone_number == phone)
        )
        contact = result.scalar_one_or_none()

        if not contact:
            # Create a new contact
            contact = Contact(
                phone_number=phone,
                name=stored_name,
                source="mobile"
            )
            db_pusat.add(contact)
            await db_pusat.commit()
            await db_pusat.refresh(contact)
            logger.info(f"Registered new mobile contact: {phone} ({stored_name})")
        else:
            # Update name if different or update source
            if contact.name != stored_name or contact.source != "mobile":
                contact.name = stored_name
                contact.source = "mobile"
                await db_pusat.commit()
                await db_pusat.refresh(contact)
                logger.info(f"Updated mobile contact name: {phone} -> {stored_name}")
    except Exception as db_err:
        await db_pusat.rollback()
        logger.error(f"Database error during contact registration: {db_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal menyimpan data pelapor ke database."
        )

    # Generate JWT Token for mobile reporter
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    payload = {
        "sub": phone,
        "role": "reporter",
        "contact_id": contact.id,
        "tenant_slug": "pusat",
        "exp": expire
    }
    
    token = jwt.encode(payload, global_settings.SECRET_KEY, algorithm=global_settings.ALGORITHM)

    return MobileLoginResponse(
        access_token=token,
        token_type="bearer",
        contact=MobileContactResponse.model_validate(contact)
    )
