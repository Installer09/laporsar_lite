"""
Shared Pytest Fixtures — SAR-BOT v3 Backend Test Suite
======================================================
Provides reusable mock objects and sample data for unit testing the
SAR-BOT v3 backend without requiring a live database, external APIs,
or running services.

Fixtures:
  - mock_db:                       AsyncMock of SQLAlchemy AsyncSession
  - sample_extracted_data_*:       Various extracted-data dicts (complete, partial, empty)
  - sample_chat_session:           Mock ChatSession ORM object
  - sample_report:                 Mock Report ORM object
  - sample_knowledge_entry:        Mock DictionaryWord ORM object
  - sample_contact:                Mock Contact ORM object
  - sample_attachment:             Mock Attachment ORM object
  - sample_system_setting:         Mock SystemSetting ORM object
  - sample_location:               Mock Location ORM object
  - sample_classification:         Mock Classification ORM object
  - sample_user:                   Mock User ORM object
  - mock_chatbot_engine:           Patched chatbot_engine singleton
  - mock_validator_router:         Patched ValidatorRouter class methods
  - mock_state_manager:            Patched StateManager class methods
  - mock_message_formatter:        Patched message_formatter singleton
  - mock_nlp_extractor:            Patched sar_nlp_extractor singleton
  - mock_ai_provider_manager:      Patched ai_provider_manager singleton
  - mock_reply_dispatcher:         Patched reply_dispatcher singleton
  - mock_storage_service:          Patched storage_service singleton
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# 1. Database Session Mock
# =====================================================================

@pytest.fixture
def mock_db():
    """Provide an AsyncMock that mimics SQLAlchemy AsyncSession.

    All standard session methods (add, flush, commit, rollback, execute,
    refresh, delete, close) are available as async callables.  The
    ``execute`` method returns a MagicMock whose ``.scalars().first()``
    and ``.scalars().all()`` return ``None`` / ``[]`` by default — tests
    can override as needed.
    """
    db = AsyncMock()

    # Ensure the common coroutine methods are async-awaitable
    db.add = MagicMock()  # add() is synchronous in SQLAlchemy
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.close = AsyncMock()

    # execute() returns a result with scalars() helper
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)

    # Support async context-manager protocol (async with SessionLocal() as s)
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)

    return db


# =====================================================================
# 2. Extracted Data Fixtures (NLP pipeline output)
# =====================================================================

@pytest.fixture
def sample_extracted_data_complete():
    """Complete extracted data dict with all required fields populated.

    Represents a fully-successful NLP extraction — every field the
    ValidatorRouter checks is present.
    """
    return {
        "jenis_kejadian": "LAKA KAPAL",
        "waktu": "2026-05-24 08:30 WIB",
        "lokasi_teks": "Perairan Selat Makassar, 10 NM dari Pantai Balikpapan",
        "korban": "3 orang ABK, 1 meninggal dunia, 2 dalam pencarian",
        "data_korban": [
            {
                "nama": "Budi Santoso",
                "umur": "35",
                "jenis_kelamin": "Laki-laki",
                "alamat": "Jl. Pelabuhan No. 12, Balikpapan",
                "kondisi": "Meninggal Dunia",
            },
            {
                "nama": "Ahmad Yani",
                "umur": "28",
                "jenis_kelamin": "Laki-laki",
                "alamat": "Kampung Nelayan, Makassar",
                "kondisi": "Dalam Pencarian",
            },
            {
                "nama": "Siti Rahayu",
                "umur": "42",
                "jenis_kelamin": "Perempuan",
                "alamat": "Desa Pantai Indah, Balikpapan",
                "kondisi": "Selamat",
            },
        ],
        "kronologi": (
            "KM Sejahtera mengalami mati mesin di perairan Selat Makassar "
            "saat cuaca buruk. Kapal terbalik oleh ombak besar sekitar pukul 08:30 WIB. "
            "Satu ABK ditemukan meninggal, dua lainnya masih dalam pencarian."
        ),
    }


@pytest.fixture
def sample_extracted_data_missing_waktu(sample_extracted_data_complete):
    """Extracted data with waktu (time) field missing — triggers AWAITING_WAKTU state."""
    data = sample_extracted_data_complete.copy()
    data["waktu"] = None
    return data


@pytest.fixture
def sample_extracted_data_missing_lokasi(sample_extracted_data_complete):
    """Extracted data with lokasi_teks (location) field missing — triggers AWAITING_LOKASI state."""
    data = sample_extracted_data_complete.copy()
    data["lokasi_teks"] = None
    return data


@pytest.fixture
def sample_extracted_data_missing_korban(sample_extracted_data_complete):
    """Extracted data with all victim info missing — triggers AWAITING_KORBAN state."""
    data = sample_extracted_data_complete.copy()
    data["data_korban"] = []
    data["korban"] = None
    return data


@pytest.fixture
def sample_extracted_data_missing_kejadian(sample_extracted_data_complete):
    """Extracted data with jenis_kejadian (incident type) missing."""
    data = sample_extracted_data_complete.copy()
    data["jenis_kejadian"] = None
    return data


@pytest.fixture
def sample_extracted_data_empty():
    """Completely empty extraction result — all fields None or empty.

    Simulates a message that yields no structured information at all.
    """
    return {
        "jenis_kejadian": None,
        "waktu": None,
        "lokasi_teks": None,
        "korban": None,
        "data_korban": [],
        "kronologi": None,
    }


# =====================================================================
# 3. ORM Model Mock Fixtures
# =====================================================================

@pytest.fixture
def sample_chat_session():
    """Mock ChatSession ORM object in AWAITING_REPORT state with empty data.

    Attributes mirror the real ChatSession columns so that tests working
    with chatbot_engine, state_manager, etc. have a realistic object.
    """
    session = MagicMock()
    session.id = 1
    session.user_id = "test_user_001"
    session.channel = "telegram"
    session.state = "AWAITING_REPORT"
    session.extracted_data = "{}"
    session.conversation_history = "[]"
    session.contact_name = "Test User"
    session.contact_phone = "+6281234567890"
    session.platform_username = "@test_user_tg"
    session.created_at = datetime(2026, 5, 24, 1, 0, 0, tzinfo=timezone.utc)
    session.updated_at = datetime(2026, 5, 24, 1, 0, 0, tzinfo=timezone.utc)
    return session


@pytest.fixture
def sample_report():
    """Mock Report ORM object representing a complete pending report.

    All key columns are populated with realistic SAR domain data so tests
    for report_service, action_handler, and message_formatter have
    meaningful values to work with.
    """
    report = MagicMock()
    report.id = 1
    report.no_laporan = "SAR/IA/2605/001"
    report.pelapor_nama = "Test Reporter"
    report.pelapor_nomor = "+6281234567890"
    report.jenis_kejadian = "LAKA KAPAL"
    report.waktu = "2026-05-24 08:30 WIB"
    report.lokasi_teks = "Perairan Selat Makassar"
    report.koordinat_lat = -1.2345
    report.koordinat_lng = 116.8500
    report.pos_sar_terdekat = "Pos SAR Balikpapan"
    report.jarak_ke_lokasi = "15 KM"
    report.heading_ke_lokasi = 45.0
    report.gmaps_link = "https://maps.google.com/?q=-1.2345,116.8500"
    report.korban = "3 orang ABK"
    report.korban_total = 3
    report.korban_selamat = 1
    report.korban_meninggal = 1
    report.korban_hilang = 1
    report.data_korban = [
        {
            "nama": "Budi Santoso",
            "umur": "35",
            "jenis_kelamin": "Laki-laki",
            "alamat": "Balikpapan",
            "kondisi": "Meninggal Dunia",
        }
    ]
    report.metadata_kejadian = {"nama_kapal": "KM Sejahtera", "gt": "50"}
    report.unsur_alut = {"unsur": ["Tim SAR Balikpapan"], "alut": ["RIB", "Heli"]}
    report.kronologi = "Kapal terbalik akibat cuaca buruk."
    report.eviden_id = "ev_001"
    report.status = "PENDING"
    report.created_at = datetime(2026, 5, 24, 1, 30, 0, tzinfo=timezone.utc)
    report.updated_at = datetime(2026, 5, 24, 1, 30, 0, tzinfo=timezone.utc)
    return report


@pytest.fixture
def sample_knowledge_entry():
    """Mock DictionaryWord (KnowledgeEntry) ORM object.

    Represents an approved knowledge-base entry used by the NLP pipeline
    for keyword-based NER (incident keyword mapping).
    """
    entry = MagicMock()
    entry.id = 1
    entry.word = "KMM"
    entry.definition = "Kondisi Membahayakan Manusia — kategori kejadian SAR"
    entry.context_example = "Terjadi KMM di perairan Balikpapan"
    entry.source_message = "Admin input"
    entry.source_user = "admin"
    entry.status = "APPROVED"
    entry.frequency = 5
    entry.word_type = "ABBREVIATION"
    entry.is_auto_detected = False
    entry.ner_type = "INCIDENT_KEYWORD"
    entry.ner_target = "KMM"
    entry.created_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    entry.updated_at = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    return entry


@pytest.fixture
def sample_contact():
    """Mock Contact ORM object representing a known reporter."""
    contact = MagicMock()
    contact.id = 1
    contact.phone_number = "+6281234567890"
    contact.name = "Budi Pelapor"
    contact.source = "telegram"
    contact.notes = "Nelayan Balikpapan, sering melaporkan kejadian laut"
    contact.last_location = "Balikpapan"
    contact.created_at = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)
    contact.updated_at = datetime(2026, 5, 20, 14, 0, 0, tzinfo=timezone.utc)
    return contact


@pytest.fixture
def sample_attachment():
    """Mock Attachment ORM object for a photo uploaded via Telegram."""
    attachment = MagicMock()
    attachment.id = 1
    attachment.report_id = None  # Not yet linked to a report
    attachment.user_id = "test_user_001"
    attachment.channel = "telegram"
    attachment.file_key = "telegram/photos/2026/05/abc123def456.jpg"
    attachment.bucket = "laporsar-attachments"
    attachment.original_filename = "photo_20260524.jpg"
    attachment.mime_type = "image/jpeg"
    attachment.file_size = 245_760
    attachment.file_type = "photo"
    attachment.created_at = datetime(2026, 5, 24, 2, 0, 0, tzinfo=timezone.utc)
    return attachment


@pytest.fixture
def sample_system_setting():
    """Mock SystemSetting ORM object for a Telegram bot token setting."""
    setting = MagicMock()
    setting.id = 1
    setting.key = "telegram_token"
    setting.value = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
    return setting


@pytest.fixture
def sample_location():
    """Mock Location ORM object representing a SAR station/pos."""
    location = MagicMock()
    location.id = 1
    location.name = "Kantor SAR Balikpapan"
    location.type = "Kantor"
    location.lat = -1.2675
    location.lng = 116.8289
    location.address = "Jl. Jenderal Sudirman No. 1, Balikpapan"
    location.unsur = "Tim SAR Balikpapan, Tim Rescue"
    location.alut = "RIB, Heli Bell 412, Rescue Car"
    return location


@pytest.fixture
def sample_classification():
    """Mock Classification ORM object for incident type keyword mapping."""
    classification = MagicMock()
    classification.id = 1
    classification.category = "LAKA KAPAL"
    classification.keywords = "kapal tenggelam,kapal terbalik,laka kapal,kecelakaan kapal"
    return classification


@pytest.fixture
def sample_user():
    """Mock User ORM object for an active operator account."""
    user = MagicMock()
    user.id = 1
    user.name = "Operator SAR"
    user.email = "operator@sar.go.id"
    user.phone = "+6281200000001"
    user.role = "Operator"
    user.hashed_password = "$2b$12$fakehashvalue"
    user.is_active = True
    user.is_verified = True
    user.reset_token = None
    user.photo_url = None
    user.created_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
    return user


# =====================================================================
# 4. Service / Engine Singleton Mock Fixtures
# =====================================================================

@pytest.fixture
def mock_chatbot_engine():
    """Patch the chatbot_engine singleton in app.engine.chatbot_engine.

    Returns the mock object so tests can configure return values, e.g.::

        mock_chatbot_engine.process_message.return_value = {"text": "OK"}
    """
    with patch("app.engine.chatbot_engine.chatbot_engine") as mock:
        mock.get_or_create_session = AsyncMock()
        mock.process_message = AsyncMock(return_value={"text": "mock response"})
        yield mock


@pytest.fixture
def mock_validator_router():
    """Patch ValidatorRouter.validate_extracted_data class method.

    Default: returns empty list (all data valid).
    """
    with patch(
        "app.engine.validator_router.ValidatorRouter.validate_extracted_data",
        return_value=[],
    ) as mock:
        yield mock


@pytest.fixture
def mock_state_manager():
    """Patch StateManager.get_next_state class method.

    Default: returns 'CONFIRMING' (all data complete).
    """
    with patch(
        "app.engine.state_manager.StateManager.get_next_state",
        return_value="CONFIRMING",
    ) as mock:
        yield mock


@pytest.fixture
def mock_message_formatter():
    """Patch the message_formatter singleton in app.services.message_formatter.

    Default: render() returns a placeholder string.
    """
    with patch("app.services.message_formatter.message_formatter") as mock:
        mock.render = MagicMock(return_value="[FORMATTED REPORT]")
        mock.format_korban = MagicMock(return_value="1. Nama: Budi | Umur: 35 | JK: L")
        yield mock


@pytest.fixture
def mock_nlp_extractor():
    """Patch the sar_nlp_extractor singleton in app.services.nlp_extractor.

    Default: extract() returns a complete dict with confidence 0.9.
    """
    with patch("app.services.nlp_extractor.sar_nlp_extractor") as mock:
        mock.extract = AsyncMock(return_value=(
            {
                "jenis_kejadian": "LAKA KAPAL",
                "waktu": "2026-05-24 08:30 WIB",
                "lokasi_teks": "Selat Makassar",
                "korban": "3 orang ABK",
                "data_korban": [],
            },
            0.9,
        ))
        yield mock


@pytest.fixture(autouse=True)
def mock_ai_provider_manager():
    """Patch the ai_provider_manager singleton in app.services.ai_providers.

    Defaults:
      - llm_generate()      → returns empty JSON string
      - get_embedding()      → returns 384-dim zero vector
      - transcribe_audio()   → returns empty string
    """
    with patch("app.services.ai_providers.ai_provider_manager") as mock:
        mock.llm_generate = AsyncMock(return_value="{}")
        mock.get_embedding = AsyncMock(return_value=[0.0] * 384)
        mock.transcribe_audio = AsyncMock(return_value="")
        mock.test_connection = AsyncMock(
            return_value={"connected": True, "message": "OK", "models": []}
        )
        with patch("app.services.llm_rag.ai_provider_manager", mock, create=True):
            with patch("app.services.transcription.ai_provider_manager", mock, create=True):
                yield mock


@pytest.fixture
def mock_reply_dispatcher():
    """Patch the reply_dispatcher singleton in app.services.reply_dispatcher.

    All send/forward methods return True (success) by default.
    """
    with patch("app.services.reply_dispatcher.reply_dispatcher") as mock:
        mock.send_telegram_reply = AsyncMock(return_value=True)
        mock.send_whatsapp_reply = AsyncMock(return_value=True)
        mock.forward_to_sar_group = AsyncMock(return_value=True)
        mock.forward_to_whatsapp_sar_group = AsyncMock(return_value=True)
        mock.forward_report_to_all_groups = AsyncMock(
            return_value={"telegram": True, "whatsapp": True}
        )
        mock.forward_file_to_telegram_sar_group = AsyncMock(return_value=True)
        mock.forward_file_to_whatsapp_sar_group = AsyncMock(return_value=True)
        yield mock


@pytest.fixture
def mock_storage_service():
    """Patch the storage_service singleton in app.services.storage_service.

    Defaults:
      - upload_file()       → returns a fake S3 object key
      - get_presigned_url() → returns a fake URL
      - download_file_bytes() → returns empty bytes
      - delete_file()       → returns True
      - is_available()      → returns True
    """
    with patch("app.services.storage_service.storage_service") as mock:
        mock.initialize = AsyncMock()
        mock.upload_file = AsyncMock(
            return_value="telegram/photos/2026/05/mock_upload.jpg"
        )
        mock.get_presigned_url = AsyncMock(
            return_value="http://minio:9000/laporsar-attachments/mock_key?signature=abc"
        )
        mock.download_file_bytes = AsyncMock(return_value=b"")
        mock.delete_file = AsyncMock(return_value=True)
        mock.is_available = MagicMock(return_value=True)
        yield mock
