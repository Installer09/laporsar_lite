import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from app.db.session import get_db
from app.models.chat_session import ChatSession
from app.engine.chatbot_engine import chatbot_engine

client = TestClient(app)

@pytest.fixture
def mock_session():
    session = ChatSession(
        id=123,
        user_id="wa_62812345678",
        channel="whatsapp",
        state="AWAITING_KOORDINAT",
        contact_name="Pelapor Utama",
        contact_phone="62812345678",
        extracted_data=json.dumps({
            "jenis_kejadian": "KMM",
            "lokasi_teks": "Hutan Sedanau",
            "korban": "1 orang"
        }),
        conversation_history="[]"
    )
    return session

@pytest.mark.asyncio
async def test_get_webview_session(mock_session):
    # Mock database session
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_session)
    
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get("/api/public/webview-session/123")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == 123
        assert data["channel"] == "whatsapp"
        assert data["koordinat_lat"] is None
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_submit_webview_location(mock_session):
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_session)
    mock_db.commit = AsyncMock()
    
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        # Mock reply dispatcher and chatbot engine route
        with patch("app.services.reply_dispatcher.ReplyDispatcher.send_whatsapp_reply", new_callable=AsyncMock) as mock_dispatch:
            
            payload = {
                "koordinat_lat": 3.9528,
                "koordinat_lng": 108.3541,
                "lokasi_teks": "Pantai Sedanau"
            }
            
            response = client.post("/api/public/webview-session/123/location", json=payload)
            assert response.status_code == 200
            
            # Check that mock_session extracted_data was updated correctly
            ext_data = json.loads(mock_session.extracted_data)
            assert ext_data["koordinat_lat"] == 3.9528
            assert ext_data["koordinat_lng"] == 108.3541
            assert ext_data["_explicit_koordinat"] is True
            assert ext_data["lokasi_teks"] == "Pantai Sedanau"
            
            # Verify WhatsApp dispatch notification was triggered
            mock_dispatch.assert_called_once()
            args, kwargs = mock_dispatch.call_args
            assert "62812345678" in args[0]
            assert "Lokasi kejadian berhasil disimpan" in args[1]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_victim_bypass_logic(mock_session):
    # Set relationship as Victim (Korban)
    ext_data = json.loads(mock_session.extracted_data)
    ext_data["pelapor_hubungan"] = "Korban"
    mock_session.extracted_data = json.dumps(ext_data)
    
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_session)
    mock_db.commit = AsyncMock()
    
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch("app.services.reply_dispatcher.ReplyDispatcher.send_whatsapp_reply", new_callable=AsyncMock) as mock_dispatch:
            
            payload = {
                "koordinat_lat": 3.9528,
                "koordinat_lng": 108.3541,
                "lokasi_teks": "Pantai Sedanau"
            }
            
            response = client.post("/api/public/webview-session/123/location", json=payload)
            assert response.status_code == 200
            
            # Since reporter is Victim, coordinate submission should automatically fill pelapor_lat/lng
            ext_data = json.loads(mock_session.extracted_data)
            assert ext_data["pelapor_lat"] == 3.9528
            assert ext_data["pelapor_lng"] == 108.3541
            assert ext_data["is_current_location_shared"] is True
            assert ext_data["reporter_location"] == "Sudah terverifikasi (Pelapor adalah Korban)"
            
            # Verify that reporter_location is indeed skipped in the question sequence
            sequence = await chatbot_engine._get_full_question_sequence(mock_session, ext_data, mock_db)
            assert "reporter_location" not in sequence
    finally:
        app.dependency_overrides.clear()
