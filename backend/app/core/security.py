from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import ValidationError
import jwt
import bcrypt
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

import hashlib

def _prehash(password: str) -> bytes:
    """Hash password with SHA-256 before passing to bcrypt to bypass 72-byte limit."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest().encode('utf-8')

def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(_prehash(plain_password), hashed_password.encode('utf-8'))

def get_password_hash(password: str):
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode('utf-8')

from typing import Optional

security = HTTPBearer(auto_error=False)

async def verify_jwt(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Zero-Trust: Enforce JWT authentication for Admin endpoints.
    Allows DEV_ADMIN fallback when token is missing and DEV_ADMIN_ENABLED is True.
    Validates that the tenant scope in the token matches the requested tenant context.
    """
    if not credentials or not credentials.credentials:
        if settings.DEV_ADMIN_ENABLED:
            if settings.SECRET_KEY != "sarbot-dev-secret-key-change-in-production" and settings.DEV_ADMIN_PASSWORD == "admin":
                logger.error("CRITICAL SECURITY VIOLATION: Default DEV_ADMIN credentials used with a production SECRET_KEY. Bypassing fallback auth!")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed: Default dev admin credentials disabled in production",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return {"sub": settings.DEV_ADMIN_USERNAME, "role": "admin"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # Cross-Tenant authorization enforcement
        token_tenant_slug = payload.get("tenant_slug")
        
        # Dev admin or global admin bypass if they have no tenant scope
        if payload.get("sub") == settings.DEV_ADMIN_USERNAME or (payload.get("role") == "admin" and not token_tenant_slug):
            return payload
            
        # Extract requested workspace slug from request headers, subdomain, or path params
        req_tenant_slug = request.headers.get("X-Tenant-Slug") or request.headers.get("x-tenant-slug")
        
        if not req_tenant_slug:
            host = request.headers.get("host", "")
            parts = host.split(".")
            if len(parts) > 1:
                first_part = parts[0].split(":")[0]
                if first_part not in ("www", "admin", "localhost", "127", "localhost:3000", "localhost:8000"):
                    req_tenant_slug = first_part
                    
        if not req_tenant_slug:
            req_tenant_slug = request.path_params.get("tenant_slug")
            
        if not req_tenant_slug:
            req_tenant_slug = "pusat"
            
        if req_tenant_slug and token_tenant_slug:
            if token_tenant_slug.lower().strip() != req_tenant_slug.lower().strip():
                logger.warning(f"Security Warning: Tenant mismatch. User '{payload.get('sub')}' scoped to '{token_tenant_slug}' attempted to access '{req_tenant_slug}'.")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Akses lintas instansi/workspace ditolak."
                )
                
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_admin(payload: dict = Depends(verify_jwt)):
    """Enforce admin-only access check."""
    if payload.get("role") not in ("admin", "Super Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin privileges required"
        )
    return payload

def verify_operator_or_admin(payload: dict = Depends(verify_jwt)):
    """Enforce operator or admin access check. Excludes 'User' role."""
    if payload.get("role") not in ("admin", "Super Admin", "Operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Operator or Admin privileges required"
        )
    return payload

def verify_super_admin(payload: dict = Depends(verify_jwt)):
    """Enforce super-admin-only access check."""
    if payload.get("role") != "Super Admin" or payload.get("tenant_slug") not in (None, "pusat"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Super Admin privileges required"
        )
    return payload


