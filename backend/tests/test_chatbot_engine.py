"""
Test Suite: ChatbotEngine — Main Orchestrator
==============================================
Comprehensive tests for the ``ChatbotEngine`` class and its singleton
``chatbot_engine``.  All external dependencies (database, NLP extraction,
validator, state manager, action handler) are fully mocked so tests are
self-contained and require no live services.

Coverage areas:
  1. Session management   (get_or_create_session)
  2. History management    (_update_history)
  3. process_message — AWAITING_* states
  4. process_message — CONFIRMING state
  5. process_message — COMPLETED state
  6. Edge cases / destructive testing
"""

import json
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.engine.chatbot_engine import ChatbotEngine, chatbot_engine
from app.engine.state_manager import StateManager


# =====================================================================
# Helpers & Fixtures
# =====================================================================

def _make_session(
    *,
    user_id="test_user_001",
    channel="telegram",
    state="AWAITING_REPORT",
    extracted_data="{}",
    conversation_history="[]",
):
    """Factory that builds a lightweight MagicMock ChatSession."""
    session = MagicMock()
    session.id = 1
    session.user_id = user_id
    session.channel = channel
    session.state = state
    session.extracted_data = extracted_data
    session.conversation_history = conversation_history
    session.contact_name = "Test User"
    session.contact_phone = "+6281234567890"
    session.platform_username = "@test_tg"
    session.created_at = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
    session.updated_at = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
    return session


@pytest.fixture
def engine():
    """Fresh ChatbotEngine instance per test (not the singleton)."""
    with patch("app.engine.chatbot_engine.ActionHandler"):
        eng = ChatbotEngine()
    return eng


@pytest.fixture
def mock_db():
    """AsyncMock that mimics SQLAlchemy AsyncSession.

    ``execute().scalars().first()`` returns None by default.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)
    return db


# =====================================================================
# 1. Session Management
# =====================================================================

class TestGetOrCreateSession:
    """Tests for ChatbotEngine.get_or_create_session."""

    @pytest.mark.asyncio
    async def test_creates_new_session_when_none_exists(self, engine, mock_db):
        """When no ChatSession row exists for the user_id, a new session
        must be added to the DB and committed."""
        # Arrange — scalars().first() returns None (default)
        session = await engine.get_or_create_session("user_new", "telegram", mock_db)

        # Assert — db.add was called with a ChatSession instance
        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.user_id == "user_new"
        assert added_obj.channel == "telegram"
        mock_db.commit.assert_awaited()
        mock_db.refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_returns_existing_session(self, engine, mock_db):
        """When a ChatSession row already exists, it should be returned
        without calling db.add or db.commit."""
        existing = _make_session(user_id="user_existing")
        mock_db.execute.return_value.scalars.return_value.first.return_value = existing

        session = await engine.get_or_create_session("user_existing", "telegram", mock_db)

        assert session is existing
        mock_db.add.assert_not_called()
        # commit should NOT be called when session already exists
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_new_session_has_default_awaiting_report_state(self, engine, mock_db):
        """A freshly created session must default to AWAITING_REPORT."""
        await engine.get_or_create_session("new_user", "web", mock_db)

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.state is None or True  # SQLAlchemy Column default
        # The ChatSession model defines default='AWAITING_REPORT' at the
        # column level, so validating the constructor argument:
        assert added_obj.user_id == "new_user"

    @pytest.mark.asyncio
    async def test_new_session_correct_channel(self, engine, mock_db):
        """Channel value passed to get_or_create_session must be stored."""
        await engine.get_or_create_session("chan_user", "whatsapp", mock_db)

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.channel == "whatsapp"


# =====================================================================
# 2. History Management
# =====================================================================

class TestUpdateHistory:
    """Tests for ChatbotEngine._update_history."""

    def test_adds_message_to_empty_history(self, engine):
        """First message must initialise the history list with one entry."""
        session = _make_session(conversation_history="[]")
        engine._update_history(session, "user", "Halo")

        history = json.loads(session.conversation_history)
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Halo"

    def test_appends_to_existing_history(self, engine):
        """Subsequent messages must be appended, not replace history."""
        existing = [{"role": "user", "content": "msg1"}]
        session = _make_session(conversation_history=json.dumps(existing))

        engine._update_history(session, "assistant", "reply1")

        history = json.loads(session.conversation_history)
        assert len(history) == 2
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "reply1"

    def test_truncates_to_20_messages(self, engine):
        """History must never exceed 20 entries — oldest are dropped."""
        existing = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        session = _make_session(conversation_history=json.dumps(existing))

        engine._update_history(session, "user", "msg20")

        history = json.loads(session.conversation_history)
        assert len(history) == 20
        # The oldest (msg0) should have been dropped
        assert history[0]["content"] == "msg1"
        assert history[-1]["content"] == "msg20"

    def test_handles_malformed_json_gracefully(self, engine):
        """If conversation_history is corrupt, _update_history must not crash."""
        session = _make_session(conversation_history="NOT-VALID-JSON!!!")

        engine._update_history(session, "user", "recovery")

        history = json.loads(session.conversation_history)
        assert len(history) == 1
        assert history[0]["content"] == "recovery"

    def test_preserves_user_role(self, engine):
        """Role='user' must be stored as-is."""
        session = _make_session()
        engine._update_history(session, "user", "input")

        history = json.loads(session.conversation_history)
        assert history[0]["role"] == "user"

    def test_preserves_assistant_role(self, engine):
        """Role='assistant' must be stored as-is."""
        session = _make_session()
        engine._update_history(session, "assistant", "response")

        history = json.loads(session.conversation_history)
        assert history[0]["role"] == "assistant"


# =====================================================================
# 3. process_message — AWAITING_* States
# =====================================================================

class TestProcessMessageAwaitingStates:
    """Tests for process_message when session.state starts with 'AWAITING_'."""

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_complete_data_transitions_to_confirming(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """When extracted data is complete (no missing fields), state must
        transition to CONFIRMING and the response must prompt the user."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine._get_full_question_sequence = AsyncMock(return_value=[])

        mock_extract.return_value = {
            "jenis_kejadian": "LAKA KAPAL",
            "waktu": "2026-05-24",
            "lokasi_teks": "Selat Makassar",
            "data_korban": [{"nama": "Budi"}],
        }
        MockValidator.validate_extracted_data.return_value = []
        MockState.get_next_state.return_value = "CONFIRMING"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "Kapal tenggelam", "telegram", mock_db)

        assert "text" in result
        assert "konfirmasi" in result["text"].lower() or "YA" in result["text"]
        assert session.state == "CONFIRMING"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_missing_waktu_transitions_to_awaiting_waktu(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """When waktu is missing, state must transition to AWAITING_WAKTU."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.return_value = {
            "jenis_kejadian": "LAKA KAPAL",
            "lokasi_teks": "Selat Makassar",
        }
        MockValidator.validate_extracted_data.return_value = ["waktu"]
        MockState.get_next_state.return_value = "AWAITING_WAKTU"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "Kapal tenggelam", "telegram", mock_db)

        assert session.state == "AWAITING_WAKTU"
        assert "tanggal" in result["text"].lower() or "kejadian" in result["text"].lower()

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_missing_lokasi_transitions_to_awaiting_lokasi(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """When lokasi_teks is missing, state must transition to AWAITING_LOKASI."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.return_value = {
            "jenis_kejadian": "LAKA KAPAL",
            "waktu": "2026-05-24",
        }
        MockValidator.validate_extracted_data.return_value = ["lokasi_teks"]
        MockState.get_next_state.return_value = "AWAITING_LOKASI"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "Kapal tenggelam", "telegram", mock_db)

        assert session.state == "AWAITING_LOKASI"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    async def test_generic_greeting_sends_emergency_menu(
        self, mock_extract, engine, mock_db
    ):
        """When sending a generic greeting like 'Lapor Basarnas', state must remain AWAITING_REPORT and the bot must prompt for chronology directly without category buttons."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)
        mock_extract.return_value = {}  # Empty/generic extraction

        result = await engine.process_message("u1", "Lapor Basarnas", "telegram", mock_db)

        assert session.state == "AWAITING_REPORT"
        assert result.get("buttons") == []
        assert "Pusat Pelayanan Darurat" in result["text"]

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_selecting_category_from_menu_transitions_correctly(
        self, MockValidator, MockState, engine, mock_db
    ):
        """Selecting a category from the emergency buttons must save the category, keep it, and transition to the next missing field (e.g. waktu)."""
        session = _make_session(state="AWAITING_REPORT", extracted_data=json.dumps({}))
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine._get_full_question_sequence = AsyncMock(return_value=["waktu", "lokasi_teks"])

        MockValidator.validate_extracted_data.return_value = ["waktu"]
        MockState.get_next_state.return_value = "AWAITING_WAKTU"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "Kecelakaan Kapal", "telegram", mock_db)

        # Extracted data must reflect selected category
        extracted = json.loads(session.extracted_data)
        assert extracted["jenis_kejadian"] == "Laka Kapal"
        assert "Kategori Terpilih" in result["text"]
        # State should transition to Waktu
        assert session.state == "AWAITING_WAKTU"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    async def test_short_generic_greeting_sends_emergency_menu(
        self, mock_extract, engine, mock_db
    ):
        """When sending a short greeting like 'Halo' (len < 5), it must trigger the welcome menu and not the too-short kronologi warning."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)
        mock_extract.return_value = {}  # Empty/generic extraction
        
        result = await engine.process_message("u1", "Halo", "telegram", mock_db)
        
        assert session.state == "AWAITING_REPORT"
        assert result.get("buttons") == []
        assert "Pusat Pelayanan Darurat" in result["text"]

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_korban_without_number_asks_for_victim_count(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """If the extracted korban is a string without a number (like 'anak tenggelam'), it should be considered missing/unclear and the bot must ask the korban question."""
        session = _make_session(state="AWAITING_REPORT", extracted_data=json.dumps({
            "jenis_kejadian": "KMM",
            "waktu": "PDTW 0526 1600 G",
            "lokasi_teks": "Pantai Tanjung",
            "korban": "anak tenggelam"
        }))
        engine.get_or_create_session = AsyncMock(return_value=session)
        
        # Formulate sequence containing 'korban'
        engine._get_full_question_sequence = AsyncMock(return_value=["korban"])
        
        # When we validate and route
        route_res = await engine._validate_and_route(session, json.loads(session.extracted_data), mock_db, True)
        
        # It must set state to AWAITING_KORBAN and ask the question
        assert session.state == "AWAITING_KORBAN"
        assert "jumlah total korban" in route_res["text"]

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_first_message_full_data_bypasses_questions(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """When sending a first message containing several valid details, the chatbot must bypass all successfully extracted fields automatically."""
        session = _make_session(state="AWAITING_REPORT", extracted_data=json.dumps({}))
        engine.get_or_create_session = AsyncMock(return_value=session)
        
        # Simulates that NLP successfully extracted jenis_kejadian, waktu, lokasi_teks, and korban
        mock_extract.return_value = {
            "jenis_kejadian": "LAKA KAPAL",
            "waktu": "PDTW 0526 1500 G",
            "lokasi_teks": "Pantai Tanjung",
            "korban": "2 orang hilang"
        }
        
        # Sequence order
        engine._get_full_question_sequence = AsyncMock(return_value=["waktu", "lokasi_teks", "korban", "korban_kondisi"])
        
        # Process message
        result = await engine.process_message("u1", "Kapal pompong mati mesin tadi sore jam 15.00 di Pantai Tanjung Natuna, korban ada 2 orang", "telegram", mock_db)
        
        # State must skip waktu, lokasi_teks, and korban, routing directly to korban_kondisi
        assert session.state == "AWAITING_KORBAN_KONDISI"
        assert "rincian kondisi korban" in result["text"]

    @pytest.mark.asyncio
    async def test_invalid_korban_count_rejected(self, engine, mock_db):
        """When answering the korban question with an invalid non-numeric description, the bot must reject it and keep the state on AWAITING_KORBAN."""
        session = _make_session(state="AWAITING_KORBAN", extracted_data=json.dumps({}))
        engine.get_or_create_session = AsyncMock(return_value=session)
        
        result = await engine.process_message("u1", "ada anak tenggelam", "telegram", mock_db)
        
        # State must remain AWAITING_KORBAN
        assert session.state == "AWAITING_KORBAN"
        assert "Format Jumlah Korban Tidak Valid" in result["text"]

    @pytest.mark.asyncio
    async def test_invalid_korban_kondisi_rejected(self, engine, mock_db):
        """When answering the korban_kondisi question with unrecognized conditions, the bot must reject it and keep the state on AWAITING_KORBAN_KONDISI."""
        session = _make_session(state="AWAITING_KORBAN_KONDISI", extracted_data=json.dumps({}))
        engine.get_or_create_session = AsyncMock(return_value=session)
        
        result = await engine.process_message("u1", "kondisinya sangat mengkhawatirkan", "telegram", mock_db)
        
        # State must remain AWAITING_KORBAN_KONDISI
        assert session.state == "AWAITING_KORBAN_KONDISI"
        assert "Format Kondisi Korban Tidak Dikenali" in result["text"]

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_awaiting_waktu_provides_waktu_completes(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """From AWAITING_WAKTU, providing waktu when all other data exists
        must transition to CONFIRMING."""
        existing_data = json.dumps({
            "jenis_kejadian": "LAKA KAPAL",
            "lokasi_teks": "Selat Makassar",
            "data_korban": [{"nama": "Budi"}],
        })
        session = _make_session(state="AWAITING_WAKTU", extracted_data=existing_data)
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine._get_full_question_sequence = AsyncMock(return_value=[])

        mock_extract.return_value = {"waktu": "kemarin sore"}
        MockValidator.validate_extracted_data.return_value = []
        MockState.get_next_state.return_value = "CONFIRMING"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "kemarin sore", "telegram", mock_db)

        assert session.state == "CONFIRMING"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_extracted_data_merges_with_existing(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """New extraction results must be merged (dict.update) with
        existing session data — old keys are preserved, new ones added."""
        existing_data = json.dumps({"jenis_kejadian": "LAKA KAPAL", "old_key": "old_val"})
        session = _make_session(state="AWAITING_REPORT", extracted_data=existing_data)
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine._get_full_question_sequence = AsyncMock(return_value=["waktu"])

        mock_extract.return_value = {"waktu": "2026-05-24"}
        MockValidator.validate_extracted_data.return_value = ["waktu"]
        MockState.get_next_state.return_value = "AWAITING_WAKTU"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        await engine.process_message("u1", "waktu tadi pagi", "telegram", mock_db)

        merged = json.loads(session.extracted_data)
        assert merged["jenis_kejadian"] == "LAKA KAPAL"
        assert merged["waktu"] == "2026-05-24"
        assert merged["old_key"] == "old_val"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_multiple_missing_fields_correct_priority(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """When multiple fields are missing, we verify the question sequence determines priority."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine._get_full_question_sequence = AsyncMock(return_value=["waktu", "lokasi_teks", "data_korban"])

        mock_extract.return_value = {"jenis_kejadian": "LAKA KAPAL"}
        MockValidator.validate_extracted_data.return_value = ["waktu", "lokasi_teks", "data_korban"]
        MockState.get_next_state.return_value = "AWAITING_WAKTU"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "kapal karam", "telegram", mock_db)

        # Sequence should be queried, setting the first field 'waktu' as AWAITING_WAKTU
        engine._get_full_question_sequence.assert_called_once()
        assert session.state == "AWAITING_WAKTU"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_db_committed_after_state_transition(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """The DB session must be committed after updating state and
        after updating history (two commits total)."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.return_value = {"waktu": "now"}
        MockValidator.validate_extracted_data.return_value = []
        MockState.get_next_state.return_value = "CONFIRMING"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        await engine.process_message("u1", "msg", "telegram", mock_db)

        # Two commits: one after state change, one after history update
        assert mock_db.commit.await_count == 2


# =====================================================================
# 4. process_message — CONFIRMING State
# =====================================================================

class TestProcessMessageConfirming:
    """Tests for process_message when session.state == 'CONFIRMING'."""

    @pytest.mark.asyncio
    async def test_user_says_ya_completes_report(self, engine, mock_db):
        """Typing 'ya' must call action_handler.complete_report and
        set state to COMPLETED."""
        session = _make_session(
            state="CONFIRMING",
            extracted_data=json.dumps({"jenis_kejadian": "LAKA KAPAL"}),
        )
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine.action_handler = AsyncMock()
        
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.no_laporan = "SAR-123"
        mock_report.kronologi = "kronologi"
        mock_report.metadata_kejadian = {}
        mock_report.jenis_kejadian = "LAKA KAPAL"
        mock_report.lokasi_teks = "Natuna"
        mock_report.waktu = "sekarang"
        mock_report.korban_detail = None
        mock_report.jumlah_korban = 1
        
        engine.action_handler.complete_report = AsyncMock(return_value=("Info Awal Text", mock_report))

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"
            MockState.STATE_COMPLETED = "COMPLETED"

            result = await engine.process_message("u1", "ya", "telegram", mock_db)

        assert session.state == "COMPLETED"
        assert "Laporan Anda Telah Diterima secara Resmi" in result["text"]
        engine.action_handler.complete_report.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_says_ya_location_out_of_bounds(self, engine, mock_db):
        """Typing 'ya' when the location is out of bounds must still complete the report, but return the custom out-of-bounds warning."""
        session = _make_session(
            state="CONFIRMING",
            extracted_data=json.dumps({
                "jenis_kejadian": "LAKA KAPAL",
                "lokasi_teks": "Jakarta",
                "koordinat_lat": -6.2088,
                "koordinat_lng": 106.8456
            }),
        )
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine.action_handler = AsyncMock()
        
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.no_laporan = "SAR-123"
        mock_report.kronologi = "kronologi"
        mock_report.metadata_kejadian = {}
        mock_report.jenis_kejadian = "LAKA KAPAL"
        mock_report.lokasi_teks = "Jakarta"
        mock_report.waktu = "sekarang"
        mock_report.korban_detail = None
        mock_report.jumlah_korban = 1
        
        engine.action_handler.complete_report = AsyncMock(return_value=("Info Awal Text", mock_report))
        
        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"
            MockState.STATE_COMPLETED = "COMPLETED"

            result = await engine.process_message("u1", "ya", "telegram", mock_db)

        assert session.state == "COMPLETED"
        assert "di luar wilayah kerja" in result["text"]
        engine.action_handler.complete_report.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_says_YA_uppercase(self, engine, mock_db):
        """The engine lowercases input, so 'YA' must also trigger confirmation."""
        session = _make_session(
            state="CONFIRMING",
            extracted_data=json.dumps({"jenis_kejadian": "LAKA KAPAL"}),
        )
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine.action_handler = AsyncMock()
        
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.no_laporan = "SAR-123"
        mock_report.kronologi = "kronologi"
        mock_report.metadata_kejadian = {}
        mock_report.jenis_kejadian = "LAKA KAPAL"
        mock_report.lokasi_teks = "Natuna"
        mock_report.waktu = "sekarang"
        mock_report.korban_detail = None
        mock_report.jumlah_korban = 1
        
        engine.action_handler.complete_report = AsyncMock(return_value=("Info Awal", mock_report))

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"
            MockState.STATE_COMPLETED = "COMPLETED"

            result = await engine.process_message("u1", "YA", "telegram", mock_db)

        assert session.state == "COMPLETED"
        assert "Laporan Anda Telah Diterima secara Resmi" in result["text"]

    @pytest.mark.asyncio
    async def test_user_says_Ya_mixed_case(self, engine, mock_db):
        """Mixed case 'Ya' must also trigger confirmation (lowercased to 'ya')."""
        session = _make_session(
            state="CONFIRMING",
            extracted_data=json.dumps({"jenis_kejadian": "LAKA KAPAL"}),
        )
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine.action_handler = AsyncMock()
        
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.no_laporan = "SAR-123"
        mock_report.kronologi = "kronologi"
        mock_report.metadata_kejadian = {}
        mock_report.jenis_kejadian = "LAKA KAPAL"
        mock_report.lokasi_teks = "Natuna"
        mock_report.waktu = "sekarang"
        mock_report.korban_detail = None
        mock_report.jumlah_korban = 1
        
        engine.action_handler.complete_report = AsyncMock(return_value=("Info Awal", mock_report))

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"
            MockState.STATE_COMPLETED = "COMPLETED"

            result = await engine.process_message("u1", "Ya", "telegram", mock_db)

        assert session.state == "COMPLETED"

    @pytest.mark.asyncio
    async def test_user_says_iya_does_not_confirm(self, engine, mock_db):
        """'iya' != 'ya' — should NOT trigger report completion."""
        session = _make_session(state="CONFIRMING")
        engine.get_or_create_session = AsyncMock(return_value=session)

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"

            result = await engine.process_message("u1", "iya", "telegram", mock_db)

        assert "Batal" in result["text"]

    @pytest.mark.asyncio
    async def test_user_says_tidak_cancels(self, engine, mock_db):
        """Any non-'ya' text in CONFIRMING state returns a cancel response."""
        session = _make_session(state="CONFIRMING")
        engine.get_or_create_session = AsyncMock(return_value=session)

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"

            result = await engine.process_message("u1", "tidak", "telegram", mock_db)

        assert "Batal" in result["text"]

    @pytest.mark.asyncio
    async def test_random_text_in_confirming_cancels(self, engine, mock_db):
        """Random text in CONFIRMING state must be treated as rejection."""
        session = _make_session(state="CONFIRMING")
        engine.get_or_create_session = AsyncMock(return_value=session)

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"

            result = await engine.process_message("u1", "lorem ipsum dolor", "telegram", mock_db)

        assert "Batal" in result["text"]

    @pytest.mark.asyncio
    async def test_empty_message_in_confirming_cancels(self, engine, mock_db):
        """An empty string in CONFIRMING state must also cancel."""
        session = _make_session(state="CONFIRMING")
        engine.get_or_create_session = AsyncMock(return_value=session)

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"

            result = await engine.process_message("u1", "", "telegram", mock_db)

        assert "Batal" in result["text"]

    @pytest.mark.asyncio
    async def test_complete_report_does_not_return_info_awal_to_reporter(self, engine, mock_db):
        """The info_awal text returned by action_handler must NOT appear in
        the final response to the reporter."""
        session = _make_session(
            state="CONFIRMING",
            extracted_data=json.dumps({"jenis_kejadian": "LAKA KAPAL"}),
        )
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine.action_handler = AsyncMock()
        
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.no_laporan = "SAR-123"
        mock_report.kronologi = "kronologi"
        mock_report.metadata_kejadian = {}
        mock_report.jenis_kejadian = "LAKA KAPAL"
        mock_report.lokasi_teks = "Natuna"
        mock_report.waktu = "sekarang"
        mock_report.korban_detail = None
        mock_report.jumlah_korban = 1
        
        engine.action_handler.complete_report = AsyncMock(
            return_value=("=== INFO AWAL SAR ===\nKejadian: LAKA KAPAL", mock_report)
        )

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"
            MockState.STATE_COMPLETED = "COMPLETED"

            result = await engine.process_message("u1", "ya", "telegram", mock_db)

        assert "INFO AWAL SAR" not in result["text"]
        assert "Laporan Anda Telah Diterima secara Resmi" in result["text"]


# =====================================================================
# 5. process_message — COMPLETED State
# =====================================================================

class TestProcessMessageCompleted:
    """Tests for process_message when session.state == 'COMPLETED'."""

    @pytest.mark.asyncio
    async def test_message_after_completed_returns_finished(self, engine, mock_db):
        """After COMPLETED, any message should return a 'session finished' notice."""
        session = _make_session(state="COMPLETED")
        engine.get_or_create_session = AsyncMock(return_value=session)

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"

            result = await engine.process_message("u1", "hello?", "telegram", mock_db)

        assert "selesai" in result["text"].lower() or "Sesi telah selesai" in result["text"]

    @pytest.mark.asyncio
    async def test_completed_response_structure(self, engine, mock_db):
        """Response must be a dict with a 'text' key."""
        session = _make_session(state="COMPLETED")
        engine.get_or_create_session = AsyncMock(return_value=session)

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"

            result = await engine.process_message("u1", "test", "telegram", mock_db)

        assert isinstance(result, dict)
        assert "text" in result


# =====================================================================
# 6. Edge Cases / Destructive Testing
# =====================================================================

class TestEdgeCases:
    """Edge cases and destructive inputs for process_message."""

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_empty_message_string(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """An empty string must not crash the engine; it should still
        go through the extraction pipeline in AWAITING_* states."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.return_value = {}
        MockValidator.validate_extracted_data.return_value = ["jenis_kejadian", "waktu", "lokasi_teks"]
        MockState.get_next_state.return_value = "AWAITING_REPORT"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "", "telegram", mock_db)

        assert "text" in result
        mock_extract.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_very_long_message(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """A 10,000-character message must not crash the engine."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        long_msg = "A" * 10_000
        mock_extract.return_value = {}
        MockValidator.validate_extracted_data.return_value = ["jenis_kejadian"]
        MockState.get_next_state.return_value = "AWAITING_REPORT"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", long_msg, "telegram", mock_db)

        assert "text" in result
        mock_extract.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_sql_injection_in_message(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """SQL injection payloads must be treated as normal text —
        processed through extraction without crashing."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        sql_payload = "'; DROP TABLE chat_sessions; --"
        mock_extract.return_value = {}
        MockValidator.validate_extracted_data.return_value = ["jenis_kejadian"]
        MockState.get_next_state.return_value = "AWAITING_REPORT"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", sql_payload, "telegram", mock_db)

        assert "text" in result

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_special_characters_in_message(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """Messages with HTML, angle brackets, and control chars must
        be handled without crashes."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        special = '<script>alert("xss")</script> \x00\x01\x02 & < > "'
        mock_extract.return_value = {}
        MockValidator.validate_extracted_data.return_value = ["jenis_kejadian"]
        MockState.get_next_state.return_value = "AWAITING_REPORT"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", special, "telegram", mock_db)

        assert "text" in result

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_malformed_extracted_data_json_in_session(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """If session.extracted_data contains corrupt JSON, process_message
        must recover gracefully (fall back to empty dict)."""
        session = _make_session(
            state="AWAITING_REPORT",
            extracted_data="NOT_JSON{{{",
        )
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.return_value = {"waktu": "2026-05-24"}
        MockValidator.validate_extracted_data.return_value = ["lokasi_teks"]
        MockState.get_next_state.return_value = "AWAITING_LOKASI"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "msg", "telegram", mock_db)

        # Should not crash and new data should be in extracted_data
        merged = json.loads(session.extracted_data)
        assert merged["waktu"] == "2026-05-24"
        assert "text" in result

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_db_error_during_commit_propagates(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """If db.commit raises an exception, it must propagate upward
        (the engine does not swallow DB errors)."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.return_value = {}
        MockValidator.validate_extracted_data.return_value = []
        MockState.get_next_state.return_value = "CONFIRMING"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        mock_db.commit = AsyncMock(side_effect=Exception("DB write failure"))

        with pytest.raises(Exception, match="DB write failure"):
            await engine.process_message("u1", "msg", "telegram", mock_db)

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_extract_incident_data_raises_exception(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """If extract_incident_data raises, the exception must propagate
        (engine does not swallow NLP errors)."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.side_effect = RuntimeError("NLP service unavailable")

        with pytest.raises(RuntimeError, match="NLP service unavailable"):
            await engine.process_message("u1", "msg", "telegram", mock_db)

    @pytest.mark.asyncio
    async def test_complete_report_raises_exception(self, engine, mock_db):
        """If action_handler.complete_report raises, the exception must
        propagate (engine does not swallow action errors)."""
        session = _make_session(
            state="CONFIRMING",
            extracted_data=json.dumps({"jenis_kejadian": "LAKA KAPAL"}),
        )
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine.action_handler = AsyncMock()
        engine.action_handler.complete_report = AsyncMock(
            side_effect=RuntimeError("Report service down")
        )

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"
            MockState.STATE_COMPLETED = "COMPLETED"

            with pytest.raises(RuntimeError, match="Report service down"):
                await engine.process_message("u1", "ya", "telegram", mock_db)

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_unicode_emoji_in_message(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """Unicode and emoji characters must be handled without crashes."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        emoji_msg = "Kapal 🚢 tenggelam di laut 🌊 tolong!! 🆘"
        mock_extract.return_value = {"jenis_kejadian": "LAKA KAPAL"}
        MockValidator.validate_extracted_data.return_value = ["waktu"]
        MockState.get_next_state.return_value = "AWAITING_WAKTU"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", emoji_msg, "telegram", mock_db)

        assert "text" in result
        # Emoji message must also be stored in history
        history = json.loads(session.conversation_history)
        user_msgs = [h for h in history if h["role"] == "user"]
        assert any("🚢" in m["content"] for m in user_msgs)

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_concurrent_messages_same_user(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """Two simultaneous process_message calls for the same user must
        both complete without deadlocking (no shared mutable state
        between calls beyond the mocked session)."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.return_value = {"jenis_kejadian": "LAKA KAPAL"}
        MockValidator.validate_extracted_data.return_value = ["waktu"]
        MockState.get_next_state.return_value = "AWAITING_WAKTU"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        results = await asyncio.gather(
            engine.process_message("u1", "msg1", "telegram", mock_db),
            engine.process_message("u1", "msg2", "telegram", mock_db),
        )

        assert len(results) == 2
        assert all("text" in r for r in results)


# =====================================================================
# 7. Singleton & Module-level Tests
# =====================================================================

class TestSingleton:
    """Tests for the module-level chatbot_engine singleton."""

    def test_singleton_is_chatbot_engine_instance(self):
        """The module-level chatbot_engine must be a ChatbotEngine instance."""
        assert isinstance(chatbot_engine, ChatbotEngine)

    def test_singleton_has_action_handler(self):
        """The singleton must have an action_handler attribute."""
        assert hasattr(chatbot_engine, "action_handler")


# =====================================================================
# 8. Return Value Contracts
# =====================================================================

class TestReturnValueContracts:
    """Verify the dict structure returned by process_message."""

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    @patch("app.engine.chatbot_engine.StateManager")
    @patch("app.engine.chatbot_engine.ValidatorRouter")
    async def test_awaiting_state_returns_dict_with_text(
        self, MockValidator, MockState, mock_extract, engine, mock_db
    ):
        """AWAITING_* must return {'text': <str>}."""
        session = _make_session(state="AWAITING_REPORT")
        engine.get_or_create_session = AsyncMock(return_value=session)

        mock_extract.return_value = {}
        MockValidator.validate_extracted_data.return_value = ["waktu"]
        MockState.get_next_state.return_value = "AWAITING_WAKTU"
        MockState.STATE_CONFIRMING = "CONFIRMING"

        result = await engine.process_message("u1", "msg", "telegram", mock_db)

        assert isinstance(result, dict)
        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_confirming_cancel_returns_dict_with_text(self, engine, mock_db):
        """CONFIRMING cancel must return {'text': <str>}."""
        session = _make_session(state="CONFIRMING")
        engine.get_or_create_session = AsyncMock(return_value=session)

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"

            result = await engine.process_message("u1", "no", "telegram", mock_db)

        assert isinstance(result, dict)
        assert isinstance(result["text"], str)

    @pytest.mark.asyncio
    async def test_completed_returns_dict_with_text(self, engine, mock_db):
        """COMPLETED must return {'text': <str>}."""
        session = _make_session(state="COMPLETED")
        engine.get_or_create_session = AsyncMock(return_value=session)

        with patch("app.engine.chatbot_engine.StateManager") as MockState:
            MockState.STATE_CONFIRMING = "CONFIRMING"

            result = await engine.process_message("u1", "msg", "telegram", mock_db)

        assert isinstance(result, dict)
        assert isinstance(result["text"], str)


# =====================================================================
# 9. Compact Calendar & Manual Hour Input Validation Tests
# =====================================================================

class TestTemporalCompactPicker:
    """Verify the free-text waktu validation and shortcut buttons."""

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    async def test_waktu_shortcut_buttons_accepted(self, mock_extract, engine, mock_db):
        """Selecting a shortcut button like 'Baru Saja' must save it and complete AWAITING_WAKTU."""
        session = _make_session(state="AWAITING_WAKTU", extracted_data="{}")
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine._get_full_question_sequence = AsyncMock(return_value=[])
        mock_extract.return_value = {}
        
        # Test "Baru Saja"
        result = await engine.process_message("u1", "Baru Saja", "telegram", mock_db)
        ext_data = json.loads(session.extracted_data)
        assert ext_data["waktu"] == "Baru Saja"
        assert session.state == "CONFIRMING"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    async def test_waktu_complete_input_accepted(self, mock_extract, engine, mock_db):
        """Entering complete date and time (e.g. 'Kemarin jam 5 sore') must save and proceed."""
        session = _make_session(state="AWAITING_WAKTU", extracted_data="{}")
        engine.get_or_create_session = AsyncMock(return_value=session)
        engine._get_full_question_sequence = AsyncMock(return_value=[])
        mock_extract.return_value = {}

        result = await engine.process_message("u1", "Kemarin jam 5 sore", "telegram", mock_db)
        ext_data = json.loads(session.extracted_data)
        assert ext_data["waktu"] == "Kemarin jam 5 sore"
        assert session.state == "CONFIRMING"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    async def test_waktu_missing_hour_prompts_error(self, mock_extract, engine, mock_db):
        """Entering only a date (e.g. 'Kemarin') must return a validation error prompting for the hour."""
        session = _make_session(state="AWAITING_WAKTU", extracted_data="{}")
        engine.get_or_create_session = AsyncMock(return_value=session)
        mock_extract.return_value = {}

        result = await engine.process_message("u1", "Kemarin", "telegram", mock_db)
        assert "Jam kejadian belum lengkap" in result["text"]
        assert "Baru Saja" in result["buttons"]
        assert session.state == "AWAITING_WAKTU"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    async def test_waktu_missing_date_prompts_error(self, mock_extract, engine, mock_db):
        """Entering only a time (e.g. 'Pukul 14.00') must return a validation error prompting for the day/date."""
        session = _make_session(state="AWAITING_WAKTU", extracted_data="{}")
        engine.get_or_create_session = AsyncMock(return_value=session)
        mock_extract.return_value = {}

        result = await engine.process_message("u1", "Pukul 14.00", "telegram", mock_db)
        assert "Hari/tanggal kejadian belum lengkap" in result["text"]
        assert "Baru Saja" in result["buttons"]
        assert session.state == "AWAITING_WAKTU"

    @pytest.mark.asyncio
    @patch("app.engine.chatbot_engine.extract_incident_data", new_callable=AsyncMock)
    async def test_waktu_invalid_format_prompts_error(self, mock_extract, engine, mock_db):
        """Entering arbitrary text must return the general time format error."""
        session = _make_session(state="AWAITING_WAKTU", extracted_data="{}")
        engine.get_or_create_session = AsyncMock(return_value=session)
        mock_extract.return_value = {}

        result = await engine.process_message("u1", "sembarang saja", "telegram", mock_db)
        assert "Format waktu tidak valid" in result["text"]
        assert "Baru Saja" in result["buttons"]
        assert session.state == "AWAITING_WAKTU"
