import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.models.chat_session import ChatSession
from app.engine.field_processors.korban_kondisi import KorbanKondisiFieldProcessor
from app.engine.field_processors.waktu import WaktuFieldProcessor
from app.engine.field_processors.reporter_location import ReporterLocationFieldProcessor


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def mock_db():
    db = MagicMock() # Use MagicMock for synchronous method compatibility in test environment
    db.commit = AsyncMock()
    return db

@pytest.fixture
def chat_session():
    session = MagicMock(spec=ChatSession)
    session.state = "AWAITING_KORBAN_KONDISI"
    session.extracted_data = json.dumps({})
    session.conversation_history = "[]"
    return session


# =====================================================================
# 1. Automated Tests untuk BUG-01 (Korban Kondisi)
# =====================================================================

class TestKorbanKondisiEdgeCases:
    """Menguji ketahanan pemrosesan kondisi korban terhadap variasi input bahasa alami."""

    @pytest.mark.asyncio
    async def test_natural_indonesian_order_extraction(self, mock_db, chat_session):
        """
        [TEST BUG-01] Memastikan input alami seperti '2 orang selamat, 1 hilang'
        berhasil diekstrak secara akurat (Selamat: 2, Hilang: 1).
        """
        processor = KorbanKondisiFieldProcessor()
        extracted_data = {}
        message = "2 orang selamat, 1 orang masih hilang dicari"

        is_valid, result = await processor.validate_and_extract(
            message, chat_session, extracted_data, mock_db
        )

        assert is_valid is True
        assert result["korban_s"] == "2"
        assert result["korban_dp"] == "1"
        assert result["korban_md"] == "0"

    @pytest.mark.asyncio
    async def test_numeric_breakdown_various_formats(self, mock_db, chat_session):
        """
        Menguji berbagai format penulisan angka kondisi korban.
        """
        processor = KorbanKondisiFieldProcessor()
        
        # Test Case A: Singkatan Resmi BASARNAS
        is_valid_a, res_a = await processor.validate_and_extract(
            "S: 5, MD: 1, DP: 0", chat_session, {}, mock_db
        )
        assert is_valid_a is True
        assert res_a["korban_s"] == "5"
        assert res_a["korban_md"] == "1"
        assert res_a["korban_dp"] == "0"

        # Test Case B: Format Kata Kerja Alami
        is_valid_b, res_b = await processor.validate_and_extract(
            "meninggal dunia 3 orang dan 2 orang selamat dievakuasi", chat_session, {}, mock_db
        )
        assert is_valid_b is True
        assert res_b["korban_md"] == "3"
        assert res_b["korban_s"] == "2"

    @pytest.mark.asyncio
    async def test_completely_invalid_condition_input_rejected(self, mock_db, chat_session):
        """
        Memastikan jawaban non-kondisi (seperti kronologi/curhatan) ditolak dengan elegan.
        """
        processor = KorbanKondisiFieldProcessor()
        message = "kondisi gelombang laut sangat tinggi sekali di lokasi kejadian"

        is_valid, result = await processor.validate_and_extract(
            message, chat_session, {}, mock_db
        )

        assert is_valid is False
        assert "Format Kondisi Korban Tidak Dikenali" in result["text"]


# =====================================================================
# 2. Automated Tests untuk BUG-02 (Bypass Waktu via Huruf 'g')
# =====================================================================

class TestWaktuValidationEdgeCases:
    """Menguji penolakan input sampah/non-waktu pada WaktuFieldProcessor."""

    def test_looks_like_time_strict_boundaries(self):
        """
        [TEST BUG-02] Memastikan kalimat umum mengandung huruf 'g'
        tidak disalahartikan sebagai input penanda waktu.
        """
        processor = WaktuFieldProcessor()

        # Input yang mengandung huruf 'g' tetapi BUKAN informasi waktu
        assert processor._looks_like_time_answer("tolong bantu segera") is False
        assert processor._looks_like_time_answer("kapal tenggelam di laut") is False
        assert processor._looks_like_time_answer("orang hanyut terbawa arus") is False
        
        # Input waktu asli yang WAJIB lolos
        assert processor._looks_like_time_answer("pukul 08.00 wib") is True
        assert processor._looks_like_time_answer("tadi pagi jam 7") is True
        assert processor._looks_like_time_answer("10 menit yang lalu") is True
        assert processor._looks_like_time_answer("Kejadian jam 15:30 G") is True


# =====================================================================
# 3. Automated Tests untuk BUG-03 (Bypass GPS Keamanan)
# =====================================================================

class TestReporterLocationValidationEdgeCases:
    """Menguji kerentanan bypass verifikasi GPS melalui injeksi teks."""

    @pytest.mark.asyncio
    async def test_gps_verification_text_injection_attempt(self, mock_db):
        """
        [TEST BUG-03] Memastikan ketik emoji '📍' atau teks 'google.com/maps'
        tanpa koordinat asli ditolak dan tidak dianggap 'terverifikasi'.
        """
        processor = ReporterLocationFieldProcessor()
        chat_session = MagicMock(spec=ChatSession)
        chat_session.state = "AWAITING_REPORTER_LOCATION"

        # Skenario A: Injeksi Emoji Jalan Pintas
        extracted_data_a = {"is_current_location_shared": False}
        is_valid_a, res_a = await processor.validate_and_extract(
            "📍 Lokasi saya di sini mas", chat_session, extracted_data_a, mock_db
        )
        assert is_valid_a is False  # Wajib ditolak jika payload GPS kosong
        assert "Share Location" in res_a["text"]

        # Skenario B: Tautan Google Maps Palsu
        extracted_data_b = {"is_current_location_shared": False}
        is_valid_b, res_b = await processor.validate_and_extract(
            "Ini link mapsnya: https://google.com/maps/place/Jakarta", chat_session, extracted_data_b, mock_db
        )
        assert is_valid_b is False  # Wajib ditolak karena bukan share GPS real-time

        # Skenario C: Lokasi GPS Asli Berhasil
        extracted_data_c = {"is_current_location_shared": False}
        is_valid_c, res_c = await processor.validate_and_extract(
            "Lokasi GPS: -3.391282, 106.241521", chat_session, extracted_data_c, mock_db
        )
        assert is_valid_c is True
        assert res_c["is_current_location_shared"] is True
        assert res_c["pelapor_lat"] == -3.391282
        assert res_c["pelapor_lng"] == 106.241521


# =====================================================================
# 4. Automated Tests untuk Perbaikan Ekstraksi Lokasi, Loop & Persistensi
# =====================================================================

class TestWaktuBypassAndSingleHour:
    """Menguji perbaikan WaktuFieldProcessor untuk input jam tunggal dan bypass 'tidak tahu'."""

    @pytest.mark.asyncio
    async def test_single_hour_input(self, mock_db, chat_session):
        processor = WaktuFieldProcessor()
        # Test input jam tunggal angka
        assert processor._looks_like_time_answer("8") is True
        assert processor._looks_like_time_answer("12") is True
        # Test input jam tunggal kata bahasa Indonesia
        assert processor._looks_like_time_answer("delapan") is True

    @pytest.mark.asyncio
    async def test_waktu_bypass_unknown(self, mock_db, chat_session):
        processor = WaktuFieldProcessor()
        extracted_data = {}
        is_valid, res = await processor.validate_and_extract(
            "tidak tahu jamnya", chat_session, extracted_data, mock_db
        )
        assert is_valid is True
        assert res["waktu"] == "Waktu Kejadian Tidak Diketahui"
        assert res["_explicit_waktu"] is True


class TestKorbanBypassUnknown:
    """Menguji perbaikan KorbanFieldProcessor untuk bypass 'tidak tahu'."""

    @pytest.mark.asyncio
    async def test_korban_bypass_unknown(self, mock_db, chat_session):
        from app.engine.field_processors.korban import KorbanFieldProcessor
        processor = KorbanFieldProcessor()
        extracted_data = {}
        is_valid, res = await processor.validate_and_extract(
            "saya tidak tahu", chat_session, extracted_data, mock_db
        )
        assert is_valid is True
        assert res["korban"] == "Belum Diketahui"
        assert res["_explicit_korban"] is True


class TestDefaultFieldProcessorProfileSave:
    """Menguji auto-writeback pelapor_hp dan pelapor_nama ke ChatSession."""

    @pytest.mark.asyncio
    async def test_pelapor_hp_save_to_session(self, mock_db):
        from app.engine.field_processors.default import DefaultFieldProcessor
        processor = DefaultFieldProcessor("pelapor_hp")
        chat_session = MagicMock(spec=ChatSession)
        chat_session.contact_phone = None
        extracted_data = {}
        
        is_valid, res = await processor.validate_and_extract(
            "081234567890", chat_session, extracted_data, mock_db
        )
        assert is_valid is True
        assert res["pelapor_hp"] == "081234567890"
        assert chat_session.contact_phone == "081234567890"

    @pytest.mark.asyncio
    async def test_pelapor_nama_save_to_session(self, mock_db):
        from app.engine.field_processors.default import DefaultFieldProcessor
        processor = DefaultFieldProcessor("pelapor_nama")
        chat_session = MagicMock(spec=ChatSession)
        chat_session.contact_name = None
        chat_session.conversation_history = "[]"
        chat_session.user_id = "test_user"
        extracted_data = {}
        
        # Mock extract_incident_data to return a name
        from unittest.mock import patch
        with patch("app.services.incident_data_service.extract_incident_data", return_value={"pelapor_nama": "Budi Santoso"}):
            is_valid, res = await processor.validate_and_extract(
                "Saya Budi Santoso", chat_session, extracted_data, mock_db
            )
            assert is_valid is True
            assert res["pelapor_nama"] == "Budi Santoso"
            assert chat_session.contact_name == "Budi Santoso"


# =====================================================================
# 5. Automated Tests untuk Koordinat Terbalik (Swapped Coordinates)
# =====================================================================

class TestSwappedCoordinatesParsing:
    """Menguji ketahanan parser koordinat terhadap format terbalik (longitude-first)."""

    def test_swapped_dms_coordinates(self):
        """
        Memverifikasi bahwa format DMS dengan Longitude terlebih dahulu
        berhasil dideteksi, ditukar kembali secara benar, dan tidak ditolak.
        """
        from app.services.rule_extractor import RuleExtractor
        
        # Longitude (BT) first, Latitude (LU) second
        msg = "Lokasi koordinat 106°13'51.78\"BT / 3°22'20.92\"LU"
        coords = RuleExtractor.extract_koordinat(msg)
        
        assert coords is not None
        # Latitude should be around 3.372478, Longitude should be 106.231050
        assert abs(coords[0] - 3.372478) < 1e-4
        assert abs(coords[1] - 106.231050) < 1e-4

    def test_swapped_decimal_coordinates(self):
        """
        Memverifikasi bahwa format desimal dengan Longitude terlebih dahulu
        (bernilai di luar range [-90, 90] tapi dalam [-180, 180])
        berhasil dideteksi dan ditukar kembali ke (latitude, longitude).
        """
        from app.services.rule_extractor import RuleExtractor
        
        # Longitude first (106.241521), Latitude second (-3.391282)
        msg = "Koordinat terbalik: 106.241521, -3.391282"
        coords = RuleExtractor.extract_koordinat(msg)
        
        assert coords is not None
        assert coords[0] == -3.391282
        assert coords[1] == 106.241521

    def test_standard_decimal_coordinates_not_swapped(self):
        """
        Memverifikasi bahwa format desimal standar (latitude, longitude)
        tidak salah ditukar.
        """
        from app.services.rule_extractor import RuleExtractor
        
        # Standard: Latitude first (-3.391282), Longitude second (106.241521)
        msg = "Koordinat standar: -3.391282, 106.241521"
        coords = RuleExtractor.extract_koordinat(msg)
        
        assert coords is not None
        assert coords[0] == -3.391282
        assert coords[1] == 106.241521
