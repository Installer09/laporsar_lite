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
            default_dev_keys = {
                "sarbot-dev-secret-key-change-in-production",
                "laporsar-dev-secret-key-change-in-production"
            }
            if settings.SECRET_KEY not in default_dev_keys and settings.DEV_ADMIN_PASSWORD == "admin":
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
        
        # Global Super Admin or global admin bypass if they have no tenant scope
        if (
            payload.get("sub") == settings.DEV_SUPERADMIN_USERNAME
            or (payload.get("role") == "Super Admin" and not token_tenant_slug)
            or (payload.get("role") == "admin" and not token_tenant_slug)
        ):
            return payload
            
        # Extract requested workspace slug from request headers, subdomain, or path params
        req_tenant_slug = request.headers.get("X-Tenant-Slug") or request.headers.get("x-tenant-slug")
        
        if not req_tenant_slug:
            host = request.headers.get("host", "").lower()
            if not any(ignored in host for ignored in ("trycloudflare.com", "pages.dev", "vercel.app", "ngrok")):
                clean_host = host.split(":")[0].strip("[]")
                is_ip = False
                try:
                    import ipaddress
                    ipaddress.ip_address(clean_host)
                    is_ip = True
                except (ValueError, Exception):
                    is_ip = False

                if not is_ip:
                    parts = host.split(".")
                    if len(parts) > 1:
                        first_part = parts[0].split(":")[0]
                        if first_part not in ("www", "admin", "localhost", "127", "localhost:3000", "localhost:8000", "laporsar", "api") and not first_part.isdigit():
                            req_tenant_slug = first_part
                    
        if not req_tenant_slug:
            req_tenant_slug = request.path_params.get("tenant_slug")
            
        if not req_tenant_slug:
            req_tenant_slug = token_tenant_slug or "pusat"
            
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
    """Enforce admin-only access check (Super Admin or Tenant Admin)."""
    role = payload.get("role")
    if role not in ("Super Admin", "Admin", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin privileges required"
        )
    return payload

def verify_operator_or_admin(payload: dict = Depends(verify_jwt)):
    """Enforce operator or admin access check. Excludes 'User' role."""
    role = payload.get("role")
    if role not in ("Super Admin", "Admin", "admin", "Operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Operator or Admin privileges required"
        )
    return payload

def verify_super_admin(payload: dict = Depends(verify_jwt)):
    """Enforce super-admin-only access check (Global Super Admin, non-tenant)."""
    is_super_admin = (
        payload.get("role") == "Super Admin"
        or payload.get("sub") == getattr(settings, "DEV_SUPERADMIN_USERNAME", "superadmin")
    )
    if not is_super_admin or payload.get("tenant_slug") not in (None, "pusat"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Super Admin privileges required"
        )
    return payload


