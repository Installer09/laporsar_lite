import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from main import app
from app.db.session import get_db, get_master_db, get_redis, get_tenant
from app.api.routes.mobile_auth import get_pusat_db
from app.models.contact import Contact
from app.models.settings_models import User
from app.models.master_models import Tenant
from app.core.rate_limiter import sanitize_csv_cell, check_rate_limit, record_failed_attempt, reset_failed_attempts
from app.schemas.settings_schemas import UserCreate
from app.api.routes.contacts import ContactCreate

# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    store = {}

    async def incr(key):
        store[key] = store.get(key, 0) + 1
        return store[key]

    async def expire(key, ttl):
        return True

    async def setex(key, ttl, value):
        store[key] = value
        return True

    async def get(key):
        return store.get(key)

    async def delete(key):
        if key in store:
            del store[key]
            return 1
        return 0

    redis.incr = incr
    redis.expire = expire
    redis.setex = setex
    redis.get = get
    redis.delete = delete
    return redis


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.info = {"tenant_slug": "pusat"}

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.fixture
async def client(mock_db, mock_redis):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_master_db] = lambda: mock_db
    app.dependency_overrides[get_pusat_db] = lambda: mock_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. SECURITY HEADERS TESTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_headers_middleware(client):
    """Verify standard security headers are injected into all HTTP responses."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=(self)" in response.headers.get("Permissions-Policy", "")


# ---------------------------------------------------------------------------
# 2. RATE LIMITING ON LOGIN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_rate_limiting(client, mock_redis):
    """Verify that excessive login attempts trigger HTTP 429 Too Many Requests."""
    for i in range(15):
        res = await client.post(
            "/api/auth/login",
            json={"username": f"attacker_{i}@example.com", "password": "wrongpassword"}
        )
        assert res.status_code in (401, 403, 404, 422)

    # 16th attempt should be blocked by rate limiter
    res = await client.post(
        "/api/auth/login",
        json={"username": "attacker_16@example.com", "password": "wrongpassword"}
    )
    assert res.status_code == 429
    assert "Terlalu banyak percobaan login" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 3. OTP RATE LIMITING & LOCKOUT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.reply_dispatcher.ReplyDispatcher.send_whatsapp_reply", new_callable=AsyncMock)
@patch("app.core.config.settings.DEV_ADMIN_ENABLED", False)
async def test_mobile_otp_request_rate_limit(mock_send_wa, client, mock_redis):
    """Verify that requesting OTP more than 3 times for the same number triggers HTTP 429."""
    mock_send_wa.return_value = True

    for i in range(3):
        res = await client.post(
            "/api/auth/mobile/otp/request",
            json={"name": "Pelapor Uji", "phone_number": "081299998888"}
        )
        assert res.status_code == 200

    # 4th request must be rejected
    res = await client.post(
        "/api/auth/mobile/otp/request",
        json={"name": "Pelapor Uji", "phone_number": "081299998888"}
    )
    assert res.status_code == 429
    assert "Terlalu banyak permintaan OTP" in res.json()["detail"]


@pytest.mark.asyncio
async def test_mobile_otp_verify_attempt_lockout(client, mock_redis):
    """Verify that 5 failed OTP attempts invalidate the OTP and lock out the user."""
    # Seed active OTP
    phone = "6281299991111"
    await mock_redis.setex(f"otp:{phone}", 300, json.dumps({"otp": "654321", "name": "Budi"}))

    # Send 4 wrong attempts
    for attempt in range(1, 5):
        res = await client.post(
            "/api/auth/mobile/otp/verify",
            json={"phone_number": "081299991111", "otp_code": "000000"}
        )
        assert res.status_code == 400
        assert f"percobaan {attempt}/5" in res.json()["detail"]

    # 5th wrong attempt must trigger lockout and invalidate OTP
    res = await client.post(
        "/api/auth/mobile/otp/verify",
        json={"phone_number": "081299991111", "otp_code": "000000"}
    )
    assert res.status_code == 429
    assert "Terlalu banyak percobaan salah" in res.json()["detail"]

    # Verify OTP was deleted from Redis
    cached = await mock_redis.get(f"otp:{phone}")
    assert cached is None


# ---------------------------------------------------------------------------
# 4. CSV FORMULA INJECTION PREVENTION (CWE-1236)
# ---------------------------------------------------------------------------

def test_sanitize_csv_cell_formula_injection():
    """Verify formula characters are escaped with leading single quote."""
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-2+3") == "'-2+3"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_cell("\tTabLeading") == "'\tTabLeading"
    assert sanitize_csv_cell("Normal Text") == "Normal Text"
    assert sanitize_csv_cell(None) == ""
    assert sanitize_csv_cell(123) == "123"


# ---------------------------------------------------------------------------
# 5. STORED XSS SANITIZATION ON CONTACTS
# ---------------------------------------------------------------------------

def test_contact_create_xss_sanitization():
    """Verify ContactBase escapes HTML tags to prevent stored XSS."""
    payload = ContactCreate(
        name="<script>alert('XSS')</script> Budi",
        phone_number="081234567890",
        notes="<b onmouseover='stealCookie()'>Catatan</b>",
        last_location="<i>Pantai Natuna</i>"
    )
    assert "<script>" not in payload.name
    assert "&lt;script&gt;" in payload.name
    assert "<b" not in payload.notes
    assert "&lt;b" in payload.notes
    assert "<i>" not in payload.last_location
    assert "&lt;i&gt;" in payload.last_location


# ---------------------------------------------------------------------------
# 6. PAGINATION LIMIT CONSTRAINTS (DOS PREVENTION)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pagination_limit_cap_on_reports(client):
    """Verify that /api/reports rejects excessive limit values (>500)."""
    from app.core.security import verify_operator_or_admin
    app.dependency_overrides[verify_operator_or_admin] = lambda: {"sub": "admin", "role": "admin"}
    try:
        res = await client.get("/api/reports?limit=9999")
        assert res.status_code == 422  # Validation error from FastAPI Query(le=500)
    finally:
        app.dependency_overrides.pop(verify_operator_or_admin, None)


@pytest.mark.asyncio
async def test_pagination_limit_cap_on_dictionary(client):
    """Verify that /api/knowledge/dictionary rejects excessive limit values (>1000)."""
    res = await client.get("/api/knowledge/dictionary?limit=9999")
    assert res.status_code == 422  # Validation error from FastAPI Query(le=1000)


# ---------------------------------------------------------------------------
# 7. REDIS CACHING ON PUBLIC TENANTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_tenants_caching(client, mock_redis, mock_db):
    """Verify that /api/public/tenants serves from cache when available."""
    cached_payload = [
        {
            "name": "Basarnas Pusat Command Center",
            "slug": "pusat",
            "logo_path": "/logo.png",
            "address": "Jakarta Pusat",
            "wa_phone": "0811223344",
            "wa_link": "https://wa.me/62811223344",
            "fallback_phone": "115",
            "lat": -6.175,
            "lng": 106.827
        }
    ]
    await mock_redis.setex("cache:public_tenants", 300, json.dumps(cached_payload))

    res = await client.get("/api/public/tenants")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["slug"] == "pusat"
    # DB execute should not have been called for tenants because of cache hit
    mock_db.execute.assert_not_called()
