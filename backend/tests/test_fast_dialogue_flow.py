import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.engine.chatbot_engine import ChatbotEngine

def _make_session(*, state="AWAITING_REPORT", extracted_data="{}"):
    session = MagicMock()
    session.id = 1
    session.user_id = "test_user_99"
    session.channel = "telegram"
    session.state = state
    session.extracted_data = extracted_data
    session.conversation_history = "[]"
    session.contact_name = "Pelapor Utama"
    session.contact_phone = "+62812345678"
    return session

@pytest.fixture
def engine():
    with patch("app.engine.chatbot_engine.ActionHandler"):
        return ChatbotEngine()

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    return db

@pytest.mark.asyncio
async def test_greeting_has_no_category_buttons(engine, mock_db):
    """Verify that generic greetings return no category selection buttons."""
    session = _make_session()
    engine.get_or_create_session = AsyncMock(return_value=session)
    
    with patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = {}
        result = await engine.process_message("test_user_99", "Halo", "telegram", mock_db)
        
        # Must return instructions without category buttons
        assert result.get("buttons") == []
        assert "Pusat Pelayanan Darurat" in result["text"]

@pytest.mark.asyncio
async def test_initial_chronology_uses_ai_extraction(engine, mock_db):
    """Verify that the initial chronology message uses AI extraction (use_llm=True)."""
    session = _make_session()
    engine.get_or_create_session = AsyncMock(return_value=session)
    
    with patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = {"jenis_kejadian": "KMM"}
        
        await engine.process_message("test_user_99", "Ada orang tersesat di hutan", "telegram", mock_db)
        
        # Verify extract_incident_data was called with use_llm=True
        mock_extract.assert_called_once()
        args, kwargs = mock_extract.call_args
        assert kwargs.get("use_llm") is True

@pytest.mark.asyncio
async def test_final_confirming_triggers_single_llm_refinement(engine, mock_db):
    """Verify that when transitioning to CONFIRMING state, the unified LLM refinement is executed."""
    existing_data = {
        "jenis_kejadian": "KMM",
        "waktu": "tadi pagi pukul 8",
        "lokasi_teks": "Hutan Sedanau",
        "korban": "1 orang"
    }
    session = _make_session(state="AWAITING_KORBAN_KONDISI", extracted_data=json.dumps(existing_data))
    engine.get_or_create_session = AsyncMock(return_value=session)
    engine._get_full_question_sequence = AsyncMock(return_value=["korban_kondisi"])
    
    # We answer the last question (korban_kondisi) which triggers the confirming state
    with patch("app.services.llm_rag.LLMRagService.refine_full_report_draft", new_callable=AsyncMock) as mock_refine:
        mock_refine.return_value = {
            "jenis_kejadian": "KMM",
            "waktu": "040800 G",  # Structured PDTW
            "lokasi_teks": "Hutan Sedanau",
            "korban": "1 orang",
            "korban_s": 0,
            "korban_md": 0,
            "korban_dp": 1
        }
        
        result = await engine.process_message("test_user_99", "1 orang masih hilang", "telegram", mock_db)
        
        # Verify refine_full_report_draft was called once
        mock_refine.assert_called_once()
        
        # Verify the session is in CONFIRMING state and data was refined
        assert session.state == "CONFIRMING"
        ext_data = json.loads(session.extracted_data)
        assert ext_data["waktu"] == "040800 G"
        assert ext_data["korban_dp"] == 1
        assert "RINGKASAN DATA LAPORAN SAR" in result["text"]
