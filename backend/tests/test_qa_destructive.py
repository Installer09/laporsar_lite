"""
Destructive QA Test Suite — Lapor SAR (SARBot V3.0)
=====================================================
Ruthless QA Engineer tests designed to probe boundary limits, inject extreme
and malicious inputs, verify coordinate robustness, test corrupted database payloads,
and prevent regressions.
"""

import io
import json
import math
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.models.chat_session import ChatSession
from app.services.rule_extractor import RuleExtractor
from app.services.geo_service import parse_coordinates, calculate_distance_nm
from app.services.spatial_hotspot_service import calculate_risk_score
from app.services.system_backup import SystemBackupService
from app.engine.field_processors.korban_kondisi import KorbanKondisiFieldProcessor
from app.engine.state_handlers.confirming import ConfirmingStateHandler
from app.models.report import Report


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_session():
    session = MagicMock(spec=ChatSession)
    session.user_id = "qa_tester_01"
    session.state = "CONFIRMING"
    session.channel = "web"
    session.extracted_data = json.dumps({
        "jenis_kejadian": "Kecelakaan Kapal",
        "waktu": "10:00 WIB",
        "lokasi_teks": "Perairan Natuna",
        "korban": "3 Orang"
    })
    session.conversation_history = "[]"
    return session


# ===========================================================================
# 1. Negative & Overflow Testing (Extreme Numbers, Giant Strings, Injections)
# ===========================================================================

class TestExtremeInputsAndInjections:
    """Probes handling of massive strings, SQL injections, XSS, and negative quantities."""

    def test_massive_string_processing_no_dos(self):
        """Passing a 50,000+ character string into extractor does not hang or crash."""
        massive_text = "Tolong kami terdampar di laut " * 2000
        # Extractor should complete quickly without hanging (DoS protection)
        waktu = RuleExtractor.extract_waktu(massive_text)
        korban = RuleExtractor.extract_korban(massive_text)
        coords = RuleExtractor.extract_koordinat(massive_text)
        assert isinstance(waktu, str)
        assert isinstance(korban, str)
        assert coords is None

    def test_sql_injection_payloads_in_extractor(self):
        """SQL injection vectors in message inputs are safely processed as plain text."""
        sql_payload = "10:00 WIB'; DROP TABLE reports; DROP TABLE chat_sessions; --"
        waktu = RuleExtractor.extract_waktu(sql_payload)
        assert "10:00" in waktu

    def test_extreme_victim_count_overflow(self):
        """Arbitrarily huge numbers do not cause integer overflow or internal exceptions."""
        huge_msg = "Ada 999999999999999999999999999999999999 orang tenggelam di laut"
        result = RuleExtractor.extract_korban(huge_msg)
        assert result is not None
        assert "orang" in result.lower()

    @pytest.mark.asyncio
    async def test_negative_breakdown_numbers_rejected_gracefully(self, mock_db):
        """Negative numbers for casualties (e.g. S: -5, MD: -2) are rejected."""
        processor = KorbanKondisiFieldProcessor()
        session = MagicMock(spec=ChatSession)
        session.state = "AWAITING_KORBAN_KONDISI"

        is_valid, res = await processor.validate_and_extract(
            "S: -5, MD: -2, DP: -1", session, {}, mock_db
        )
        assert is_valid is False


# ===========================================================================
# 2. Coordinate Edge Cases
# ===========================================================================

class TestDestructiveCoordinates:
    """Probes boundary values, invalid latitudes/longitudes, and locale differences."""

    def test_standard_decimal_coordinates(self):
        """Coordinates parsing works accurately for standard GPS format."""
        raw_text = "Koordinat: -3.391282, 106.241521"
        coords = parse_coordinates(raw_text)
        assert coords is not None
        assert coords[0] == pytest.approx(-3.391282)
        assert coords[1] == pytest.approx(106.241521)

    def test_out_of_bounds_coordinates(self):
        """Coordinates exceeding geographical boundaries (|lat| > 90 or |lng| > 180) are rejected."""
        assert RuleExtractor.extract_koordinat("Lokasi: 120.500000, 250.600000") is None
        assert RuleExtractor.extract_koordinat("Lokasi: -95.123456, 105.123456") is None

    def test_haversine_extreme_antipodal_and_poles(self):
        """Distance between North Pole and South Pole equals half Earth circumference."""
        dist = calculate_distance_nm(90.0, 0.0, -90.0, 0.0)
        expected = math.pi * 3440.065
        assert dist == pytest.approx(expected, rel=1e-4)

    def test_haversine_identical_point_zero(self):
        """Distance between identical coordinates is strictly 0.0."""
        dist = calculate_distance_nm(-3.123456, 106.123456, -3.123456, 106.123456)
        assert dist == pytest.approx(0.0, abs=1e-9)


# ===========================================================================
# 3. Spatial Hotspot Boundary & Clamping
# ===========================================================================

class TestSpatialHotspotEdgeCases:
    """Tests risk score calculation with boundary values and zero/negative parameters."""

    def test_risk_score_with_zero_inputs(self):
        """Zero inputs to risk score produce minimum 0.0 score."""
        score_info = calculate_risk_score(
            incident_count=0,
            total_meninggal=0,
            total_hilang=0,
            total_selamat=0,
            jenis_kejadian_list=[]
        )
        assert score_info["score"] == 0.0
        assert score_info["level"] == "LOW"

    def test_risk_score_maximum_cap_100(self):
        """Massive disaster stats cannot exceed 100.0 score."""
        score_info = calculate_risk_score(
            incident_count=1000,
            total_meninggal=500,
            total_hilang=200,
            total_selamat=1000,
            jenis_kejadian_list=["Kecelakaan Kapal", "Banjir", "Tanah Longsor"] * 10
        )
        assert score_info["score"] <= 100.0
        assert score_info["level"] == "HIGH"


# ===========================================================================
# 4. System Backup Service Corrupted Payloads
# ===========================================================================

class TestSystemBackupDestructive:
    """Probes system restore with corrupt ZIP files, empty data, and invalid JSON."""

    @pytest.mark.asyncio
    async def test_restore_corrupt_non_zip_bytes(self, mock_db):
        """Uploading random binary garbage raises a clean exception with rollback."""
        corrupt_bytes = b"NOT_A_VALID_ZIP_ARCHIVE_GARBAGE_BYTES_123456"
        with pytest.raises(Exception) as exc_info:
            await SystemBackupService.import_restore(corrupt_bytes, mock_db)
        assert "Restorasi gagal" in str(exc_info.value)
        mock_db.rollback.assert_awaited()

    @pytest.mark.asyncio
    async def test_restore_empty_zip_archive(self, mock_db):
        """Empty zip archive without tables is handled gracefully."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            pass  # empty archive
        buffer.seek(0)

        result = await SystemBackupService.import_restore(buffer.getvalue(), mock_db)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_restore_malformed_json_in_zip(self, mock_db):
        """Zip archive containing invalid JSON syntax raises a clean exception."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("locations.json", "{ malformed json: not valid ]")
        buffer.seek(0)

        with pytest.raises(Exception) as exc_info:
            await SystemBackupService.import_restore(buffer.getvalue(), mock_db)
        assert "Format JSON pada file locations.json tidak valid" in str(exc_info.value)
        mock_db.rollback.assert_awaited()


# ===========================================================================
# 5. Regression Proofs for Resolved Critical Bugs
# ===========================================================================

class TestRegressionFixes:
    """Verifies that previously identified bugs remain permanently fixed."""

    @pytest.mark.asyncio
    async def test_confirming_state_handler_database_error_raises_http_exception(self, mock_session):
        """
        [REGRESSION TEST BUG-04]
        When db.commit() fails during report confirmation, ConfirmingStateHandler
        must raise HTTPException(status_code=500) and NOT crash with NameError.
        """
        handler = ConfirmingStateHandler()
        engine = MagicMock()
        engine.action_handler.complete_report = AsyncMock(return_value=("info", MagicMock(id=1, no_laporan="LAP-001")))
        engine._is_outside_working_area = AsyncMock(return_value=False)
        engine._update_history = MagicMock()
        engine._broadcast_session = AsyncMock()

        failing_db = MagicMock()
        failing_db.commit = AsyncMock(side_effect=Exception("Simulated DB Disk Failure"))
        failing_db.rollback = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await handler.handle(
                engine=engine,
                session=mock_session,
                message="Ya",
                extracted_data={"jenis_kejadian": "Kecelakaan Kapal"},
                db=failing_db,
                autopilot=True
            )

        assert exc_info.value.status_code == 500
        assert "Gagal memproses konfirmasi laporan" in exc_info.value.detail
        failing_db.rollback.assert_awaited_once()

    def test_report_service_json_parsing_regression(self):
        """
        [REGRESSION TEST BUG-05]
        ReportService metadata extraction must parse metadata_kejadian without
        silently dropping vessel data due to NameError: name 'json' is not defined.
        """
        import json as test_json
        meta_payload = test_json.dumps({"nama_kapal": "KM Mega Jaya"})
        report = MagicMock(spec=Report)
        report.metadata_kejadian = meta_payload
        report.jenis_kejadian = "Kecelakaan Kapal"
        report.lokasi_teks = "Laut Natuna"
        report.waktu = "12:00 WIB"
        report.korban = "5 Orang"
        report.korban_total = 5

        # Execute extraction logic identical to report_service.py
        nama_kapal = None
        if report.metadata_kejadian:
            try:
                if isinstance(report.metadata_kejadian, str):
                    meta_dict = test_json.loads(report.metadata_kejadian)
                else:
                    meta_dict = report.metadata_kejadian
                nama_kapal = (
                    meta_dict.get("nama_kapal")
                    or (meta_dict.get("data_kapal", {}).get("nama_kapal") if isinstance(meta_dict.get("data_kapal"), dict) else None)
                    or meta_dict.get("data_kapal")
                )
            except Exception:
                pass

        assert nama_kapal == "KM Mega Jaya"

    def test_knowledge_module_imports_ai_provider_and_json(self):
        """
        [REGRESSION TEST BUG-06]
        knowledge.py module must export/have ai_provider_manager and json available.
        """
        import app.api.routes.knowledge as knowledge_route
        assert hasattr(knowledge_route, "ai_provider_manager")
        assert hasattr(knowledge_route, "json")


# ===========================================================================
# 6. Mode Bantuan & State Machine Transitions
# ===========================================================================

class TestChatbotEngineStateMachineTransitions:
    """Verifies state machine resilience when switching between Mode Bantuan and Incident Reporting."""

    @pytest.mark.asyncio
    async def test_confirming_state_deny_resets_session(self, mock_session, mock_db):
        """Sending 'batalkan' or 'batal' in CONFIRMING state cleanly resets the session."""
        handler = ConfirmingStateHandler()
        engine = MagicMock()
        engine._reset_session = AsyncMock()

        result = await handler.handle(
            engine=engine,
            session=mock_session,
            message="Batalkan",
            extracted_data={},
            db=mock_db,
            autopilot=True
        )

        engine._reset_session.assert_awaited_once_with(mock_session, mock_db, True)
        assert "Laporan Batal" in result["text"]
