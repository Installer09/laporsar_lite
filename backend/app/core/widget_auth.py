from fastapi import Header, Request, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from urllib.parse import urlparse
from typing import Optional
import logging

from app.db.session import get_db
from app.models.settings_models import WidgetIntegrationRequest
from app.core.security import verify_jwt, security
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_domain_from_url(url: str) -> str:
    """Extract host and port domain from URL."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    parsed = urlparse(url)
    return parsed.netloc.lower()

def get_hostname_from_url(url: str) -> str:
    """Extract hostname (domain or IP without port) from URL."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    parsed = urlparse(url)
    return (parsed.hostname or "").lower()


async def verify_widget_key(
    request: Request,
    x_widget_api_key: str = Header(None, alias="X-Widget-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> WidgetIntegrationRequest:
    """Verify that a request to public widget endpoints has a valid and approved API Key and correct origin."""
    if not x_widget_api_key:
        logger.warning("Request missing X-Widget-API-Key header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Widget API Key."
        )
    
    query = select(WidgetIntegrationRequest).where(
        WidgetIntegrationRequest.api_key == x_widget_api_key,
        WidgetIntegrationRequest.status == "APPROVED"
    )
    result = await db.execute(query)
    integration = result.scalars().first()
    
    if not integration:
        logger.warning(f"Invalid or unapproved API Key: {x_widget_api_key}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or unapproved Widget API Key."
        )
    
    # Check origin/referer domain
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        logger.warning(f"Request using API Key '{x_widget_api_key}' lacks Origin/Referer header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Domain origin verification failed. Request lacks Origin or Referer."
        )
        
    origin_domain = get_domain_from_url(origin)
    allowed_domain = get_domain_from_url(integration.website_url)
    
    if origin_domain != allowed_domain:
        logger.warning(f"Domain mismatch for API Key '{x_widget_api_key}': origin '{origin_domain}' does not match allowed domain '{allowed_domain}'.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Domain origin verification failed. Origin '{origin_domain}' is not authorized."
        )
        
    return integration

async def verify_web_chat_access(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_widget_api_key: Optional[str] = Header(None, alias="X-Widget-API-Key"),
    db: AsyncSession = Depends(get_db)
):
    """Allow access to web chat either via operator JWT or via approved widget API key with matching domain origin."""
    if credentials and credentials.credentials:
        try:
            payload = await verify_jwt(request, credentials)
            if payload:
                return None
        except HTTPException:
            pass

    # Allow dev admin fallback if settings.DEV_ADMIN_ENABLED is True and request comes from FRONTEND_URL or localhost
    if settings.DEV_ADMIN_ENABLED:
        origin = request.headers.get("origin") or request.headers.get("referer")
        is_allowed = False
        if origin:
            if settings.FRONTEND_URL:
                origin_domain = get_domain_from_url(origin)
                allowed_domain = get_domain_from_url(settings.FRONTEND_URL)
                if origin_domain == allowed_domain:
                    is_allowed = True
            
            # Also allow fallback if the origin hostname is local (localhost, 127.0.0.1, ::1)
            if not is_allowed:
                origin_hostname = get_hostname_from_url(origin)
                if origin_hostname in ("localhost", "127.0.0.1", "::1"):
                    is_allowed = True
                    
        if is_allowed:
            try:
                payload = await verify_jwt(request, credentials)
                if payload:
                    return None
            except HTTPException:
                pass
            
    # Fallback to widget API key validation
    return await verify_widget_key(request, x_widget_api_key, db)
