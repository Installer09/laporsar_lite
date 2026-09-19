import pytest
import jwt
import re
from fastapi import HTTPException, status
from unittest.mock import MagicMock, AsyncMock
from app.core.config import settings
from app.core.security import verify_super_admin
from app.services.geo_service import parse_coordinates
from app.services.rule_extractor import RuleExtractor

# =====================================================================
# 1. Test DMS Coordinate Parsing Gaps
# =====================================================================

def test_dms_parsing_optional_seconds_geo_service():
    """Verify that geo_service correctly parses DMS coordinates that omit seconds."""
    # 03°23' LU -> 3 + 23/60 = 3.383333
    # 106°14' BT -> 106 + 14/60 = 106.233333
    coords = parse_coordinates("Kejadian di 03°23' LU / 106°14' BT")
    assert coords is not None
    lat, lon = coords
    assert abs(lat - 3.383333) < 0.0001
    assert abs(lon - 106.233333) < 0.0001


def test_dms_parsing_optional_seconds_rule_extractor():
    """Verify that rule_extractor correctly extracts DMS coordinates that omit seconds."""
    coords = RuleExtractor.extract_koordinat("Kapal mati mesin di koordinat 03°23' LU, 106°14' BT")
    assert coords is not None
    lat, lon = coords
    assert abs(lat - 3.383333) < 0.0001
    assert abs(lon - 106.233333) < 0.0001


# =====================================================================
# 2. Test Super Admin Multi-Tenant Isolation
# =====================================================================

@pytest.mark.asyncio
async def test_verify_super_admin_tenant_isolation():
    """Verify that verify_super_admin rejects regional Super Admins and allows global Super Admins."""
    # Regional Super Admin (slug = natuna)
    regional_payload = {"sub": "regional_admin", "role": "Super Admin", "tenant_slug": "natuna"}
    with pytest.raises(HTTPException) as exc:
        verify_super_admin(regional_payload)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Super Admin privileges required" in exc.value.detail

    # Global Super Admin (slug = pusat)
    global_payload = {"sub": "global_admin", "role": "Super Admin", "tenant_slug": "pusat"}
    res = verify_super_admin(global_payload)
    assert res == global_payload

    # Global Admin (slug = None)
    global_payload_none = {"sub": "global_admin", "role": "Super Admin", "tenant_slug": None}
    res_none = verify_super_admin(global_payload_none)
    assert res_none == global_payload_none


# =====================================================================
# 3. Test API endpoints for User Role Promotion Restriction
# =====================================================================

@pytest.mark.asyncio
async def test_user_creation_update_role_restriction():
    """Verify endpoints block non-pusat tenants from creating or updating users to Super Admin."""
    from main import app
    from httpx import AsyncClient, ASGITransport
    from app.db.session import get_db, get_master_db, get_tenant
    
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    
    mock_tenant = MagicMock()
    mock_tenant.slug = "natuna" # Non-pusat UPT
    
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_master_db] = lambda: mock_db
    app.dependency_overrides[get_tenant] = lambda: mock_tenant
    
    try:
        # Create user token
        token = jwt.encode(
            {"sub": "natuna_admin", "role": "admin", "tenant_slug": "natuna"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": "natuna"
        }
        transport = ASGITransport(app=app)
        
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # A. Attempt to create a user with 'Super Admin' role in regional tenant -> should be blocked
            create_resp = await ac.post(
                "/api/settings/users",
                json={
                    "name": "New User",
                    "email": "new@natuna.com",
                    "password": "password123",
                    "role": "Super Admin"
                },
                headers=headers
            )
            assert create_resp.status_code == status.HTTP_403_FORBIDDEN
            assert "Hanya Kantor SAR Pusat" in create_resp.json()["detail"]

            # B. Attempt to update a user to 'Super Admin' role in regional tenant -> should be blocked
            # Mock get user first
            from app.models.settings_models import User
            mock_user = User(id=1, email="old@natuna.com", role="Operator")
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_db.execute.return_value = mock_result
            
            update_resp = await ac.put(
                "/api/settings/users/1",
                json={
                    "role": "Super Admin"
                },
                headers=headers
            )
            assert update_resp.status_code == status.HTTP_403_FORBIDDEN
            assert "Hanya Kantor SAR Pusat" in update_resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# =====================================================================
# 4. Test Web Chat Authorization Bypass Mitigation
# =====================================================================

@pytest.mark.asyncio
async def test_web_chat_invalid_token_no_bypass():
    """Verify that sending an invalid token doesn't bypass JWT verification in web chat endpoint."""
    from main import app
    from httpx import AsyncClient, ASGITransport
    from app.db.session import get_db
    
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Send invalid token signature -> should be verified properly (not skipped as coroutine)
            # Since the token is invalid, it throws HTTPException, then falls back to widget verification.
            # Because we didn't specify X-Widget-API-Key, it should fail with 403 "Missing Widget API Key."
            # If the bypass were still present, it would bypass widget check and return 422 or proceed to chatbot engine.
            response = await ac.post(
                "/api/chat/sessions/web/message",
                json={"user_id": "web_test_123", "message": "Halo"},
                headers={"Authorization": "Bearer completely_invalid_garbage_token_signature"}
            )
            assert response.status_code == 403
            assert "Missing Widget API Key." in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
