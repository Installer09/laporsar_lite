import pytest
import jwt
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.core.security import verify_password, get_password_hash, verify_jwt
from app.core.config import settings

@pytest.fixture
def test_password():
    return "secret123"

@pytest.fixture
def hashed_password(test_password):
    return get_password_hash(test_password)

class TestPasswordHashing:
    def test_hash_and_verify_correct(self, test_password, hashed_password):
        assert verify_password(test_password, hashed_password) is True

    def test_verify_wrong_password(self, hashed_password):
        assert verify_password("wrong_password", hashed_password) is False

    def test_hash_same_password_twice(self, test_password):
        hash1 = get_password_hash(test_password)
        hash2 = get_password_hash(test_password)
        assert hash1 != hash2

    def test_empty_password(self):
        empty_hash = get_password_hash("")
        assert verify_password("", empty_hash) is True
        assert verify_password(" ", empty_hash) is False

    def test_long_password(self):
        long_pass = "A" * 1000
        long_hash = get_password_hash(long_pass)
        assert verify_password(long_pass, long_hash) is True

    def test_unicode_password(self):
        unicode_pass = "密码123🔑"
        unicode_hash = get_password_hash(unicode_pass)
        assert verify_password(unicode_pass, unicode_hash) is True

    def test_special_chars_password(self):
        special_pass = "!@#$%^&*()_+{}|:\"<>?~`-=[]\\;',./"
        special_hash = get_password_hash(special_pass)
        assert verify_password(special_pass, special_hash) is True

class TestJWTVerification:
    @pytest.fixture(autouse=True)
    def disable_dev_admin(self):
        with patch("app.core.security.settings.DEV_ADMIN_ENABLED", False):
            yield

    @pytest.fixture
    def valid_token(self):
        payload = {"sub": "test_user"}
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @pytest.fixture
    def expired_token(self):
        # Generate token that is already expired
        payload = {"sub": "test_user", "exp": 0}
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @pytest.mark.asyncio
    async def test_valid_jwt(self, valid_token):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.path_params = {}
        payload = await verify_jwt(mock_request, creds)
        assert payload["sub"] == "test_user"

    @pytest.mark.asyncio
    async def test_expired_jwt(self, expired_token):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.path_params = {}
        with pytest.raises(HTTPException) as exc:
            await verify_jwt(mock_request, creds)
        assert exc.value.status_code == 401
        assert "Token expired" in exc.value.detail

    @pytest.mark.asyncio
    async def test_malformed_jwt(self):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not.a.jwt")
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.path_params = {}
        with pytest.raises(HTTPException) as exc:
            await verify_jwt(mock_request, creds)
        assert exc.value.status_code == 401
        assert "Invalid token" in exc.value.detail

    @pytest.mark.asyncio
    async def test_wrong_secret(self):
        payload = {"sub": "test_user"}
        wrong_token = jwt.encode(payload, "wrong_secret", algorithm=settings.ALGORITHM)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=wrong_token)
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.path_params = {}
        with pytest.raises(HTTPException) as exc:
            await verify_jwt(mock_request, creds)
        assert exc.value.status_code == 401
        assert "Invalid token" in exc.value.detail

    @pytest.mark.asyncio
    async def test_wrong_algorithm(self):
        payload = {"sub": "test_user"}
        wrong_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS512")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=wrong_token)
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.path_params = {}
        with pytest.raises(HTTPException) as exc:
            await verify_jwt(mock_request, creds)
        assert exc.value.status_code == 401
        assert "Invalid token" in exc.value.detail

    @pytest.mark.asyncio
    async def test_empty_string_token(self):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.path_params = {}
        with pytest.raises(HTTPException) as exc:
            await verify_jwt(mock_request, creds)
        assert exc.value.status_code == 401
        assert "Invalid token" in exc.value.detail

    @pytest.mark.asyncio
    async def test_none_token(self):
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.path_params = {}
        with pytest.raises(HTTPException) as exc:
            await verify_jwt(mock_request, None) # type: ignore
        assert exc.value.status_code == 401

class TestSecurityAudit:
    def test_insecure_default_secret_key(self):
        # Enforce that SECRET_KEY is set and meets minimum secure length of 32 characters
        assert len(settings.SECRET_KEY) >= 32

    def test_dev_admin_backdoor_enabled(self):
        assert settings.DEV_ADMIN_ENABLED is True

    def test_dev_admin_credentials(self):
        assert settings.DEV_ADMIN_USERNAME == "admin"
        assert settings.DEV_ADMIN_PASSWORD == "admin"

    def test_token_expiration_length(self):
        # 10080 minutes = 7 days
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 10080
