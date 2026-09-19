import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from main import app
from app.api.routes.mobile_chat import get_pusat_db, verify_reporter, active_mobile_connections
from app.models.chat_session import ChatSession
from app.models.contact import Contact

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    
    # execute mock
    mock_result = MagicMock()
    db.execute = AsyncMock(return_value=mock_result)
    
    # Return contact by default
    mock_contact = Contact(id=42, phone_number="6281234567890", name="Budi Santoso", source="mobile")
    
    # Return mock session
    mock_session = ChatSession(
        id=12,
        user_id="mobile_42",
        channel="mobile",
        state="AWAITING_REPORT",
        conversation_history=json.dumps([])
    )
    
    def execute_side_effect(stmt, *args, **kwargs):
        res = MagicMock()
        # If querying Contact
        if "contacts" in str(stmt):
            res.scalar_one_or_none.return_value = mock_contact
        # If querying ChatSession
        elif "chat_sessions" in str(stmt):
            res.scalar_one_or_none.return_value = mock_session
            res.scalars.return_value.first.return_value = mock_session
        return res
        
    db.execute.side_effect = execute_side_effect
    return db

@pytest.fixture
async def client(mock_db):
    app.dependency_overrides[get_pusat_db] = lambda: mock_db
    app.dependency_overrides[verify_reporter] = lambda: {"contact_id": 42}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
class TestMobileChat:

    async def test_get_mobile_session_success(self, client):
        response = await client.get("/api/chat/mobile/session")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == 12
        assert data["user_id"] == "mobile_42"
        assert data["contact_name"] == "Budi Santoso"
        assert data["contact_phone"] == "6281234567890"

    @patch("app.engine.chatbot_engine.chatbot_engine.process_message", new_callable=AsyncMock)
    async def test_send_mobile_message_success(self, mock_process, client):
        mock_process.return_value = {"text": "Bagaimana kondisi cuaca di lokasi?"}
        
        response = await client.post(
            "/api/chat/mobile/message",
            json={"message": "Tolong, ada orang tenggelam"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["reply"] == "Bagaimana kondisi cuaca di lokasi?"
        assert isinstance(data["history"], list)
