import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from main import app
from app.api.routes.mobile_auth import get_pusat_db
from app.db.session import get_redis
from app.models.contact import Contact

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    # In-memory dictionary to act as fake redis store
    store = {}
    
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
    
    # Execute query side-effect
    mock_result = MagicMock()
    db.execute = AsyncMock(return_value=mock_result)
    
    # By default contact doesn't exist
    mock_result.scalar_one_or_none.return_value = None
    return db

@pytest.fixture
async def client(mock_db, mock_redis):
    # Override dependencies
    app.dependency_overrides[get_pusat_db] = lambda: mock_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
class TestMobileAuth:

    @patch("app.services.reply_dispatcher.ReplyDispatcher.send_whatsapp_reply", new_callable=AsyncMock)
    @patch("app.core.config.settings.DEV_ADMIN_ENABLED", False)
    async def test_request_otp_success(self, mock_send_wa, client, mock_redis):
        mock_send_wa.return_value = True
        
        response = await client.post(
            "/api/auth/mobile/otp/request",
            json={"name": "Budi Santoso", "phone_number": "081234567890"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify saved in Redis (the phone starts with 62)
        cached = await mock_redis.get("otp:6281234567890")
        assert cached is not None
        data = json.loads(cached)
        assert data["name"] == "Budi Santoso"
        assert len(data["otp"]) == 6

    async def test_request_otp_invalid_phone(self, client):
        response = await client.post(
            "/api/auth/mobile/otp/request",
            json={"name": "Budi Santoso", "phone_number": "123"}
        )
        assert response.status_code == 422 # Pydantic validation error

    async def test_request_otp_short_name(self, client):
        response = await client.post(
            "/api/auth/mobile/otp/request",
            json={"name": "A", "phone_number": "081234567890"}
        )
        assert response.status_code == 422 # Pydantic validation error

    @patch("app.services.reply_dispatcher.ReplyDispatcher.send_whatsapp_reply", new_callable=AsyncMock)
    @patch("app.core.config.settings.DEV_ADMIN_ENABLED", True)
    async def test_request_otp_dev_mode_fallback(self, mock_send_wa, client, mock_redis):
        # WA failed to send, but DEV mode is enabled
        mock_send_wa.return_value = False
        
        response = await client.post(
            "/api/auth/mobile/otp/request",
            json={"name": "Budi Santoso", "phone_number": "081234567890"}
        )
        assert response.status_code == 200
        assert "dev_otp" in response.json()
        assert response.json()["message"] == "OTP terkirim (mode pengembang)"

    async def test_verify_otp_success_new_contact(self, client, mock_db, mock_redis):
        # Set up active OTP in mock redis
        await mock_redis.setex("otp:6281234567890", 300, json.dumps({"otp": "123456", "name": "Budi Santoso"}))
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None # simulate contact not existing
        mock_db.execute.return_value = mock_result
        
        # Let's patch db.add and refresh to assign mock_contact
        def mock_refresh(target):
            target.id = 42
            
        mock_db.refresh.side_effect = mock_refresh
        
        response = await client.post(
            "/api/auth/mobile/otp/verify",
            json={"phone_number": "081234567890", "otp_code": "123456"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["contact"]["id"] == 42
        assert data["contact"]["phone_number"] == "6281234567890"
        assert data["contact"]["name"] == "Budi Santoso"
        
        # Redis key should be deleted
        assert await mock_redis.get("otp:6281234567890") is None

    async def test_verify_otp_invalid_code(self, client, mock_redis):
        await mock_redis.setex("otp:6281234567890", 300, json.dumps({"otp": "123456", "name": "Budi Santoso"}))
        
        response = await client.post(
            "/api/auth/mobile/otp/verify",
            json={"phone_number": "081234567890", "otp_code": "000000"}
        )
        assert response.status_code == 400
        assert "Kode OTP yang Anda masukkan salah" in response.json()["detail"]

    async def test_verify_otp_expired(self, client):
        # No OTP in Redis
        response = await client.post(
            "/api/auth/mobile/otp/verify",
            json={"phone_number": "081234567890", "otp_code": "123456"}
        )
        assert response.status_code == 400
        assert "Kode OTP kedaluwarsa atau tidak ditemukan" in response.json()["detail"]
