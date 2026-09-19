import pytest
from unittest.mock import AsyncMock, patch
from app.engine.action_handler import ActionHandler
from app.models.chat_session import ChatSession

from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def db_session():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    return db

@pytest.fixture
def action_handler():
    handler = ActionHandler()
    mock_report = MagicMock()
    mock_report.id = 1
    mock_report.no_laporan = "SAR-202605-001"
    mock_report.jenis_kejadian = "KMM"
    mock_report.lokasi_teks = "Jakarta"
    mock_report.koordinat_lat = None # Default to None so KML generator doesn't trigger unless tested
    mock_report.koordinat_lng = None
    mock_report.pos_sar_terdekat = "Pos SAR Jakarta"
    mock_report.jarak_ke_lokasi = "5.2 Nm"
    mock_report.heading_ke_lokasi = "180°"
    mock_report.pelapor_nama = "Pelapor SARBot"
    mock_report.pelapor_nomor = "08123456789"
    mock_report.waktu = "sekarang"
    mock_report.kronologi = "Tidak diketahui"
    mock_report.korban_total = 1
    mock_report.created_at = datetime(2026, 5, 24, 0, 0, 0)
    
    handler.report_service = AsyncMock()
    handler.report_service.create_report.return_value = mock_report
    return handler

@pytest.mark.asyncio
class TestActionHandler:
    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_complete_report_valid_data(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        mock_message_formatter.render.return_value = "Formatted Info Awal"
        
        session_data = {
            "user_id": "user123",
            "extracted_data": {"waktu": "sekarang"}
        }
        
        result = await action_handler.complete_report(session_data, db_session)
        info_awal_text, saved_report = result
        
        assert info_awal_text == "Formatted Info Awal"
        mock_message_formatter.render.assert_called_once()
        mock_reply_dispatcher.forward_report_to_all_groups.assert_awaited_once()
        assert mock_reply_dispatcher.forward_report_to_all_groups.await_args[0][0] == "Formatted Info Awal"

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_complete_report_empty_extracted_data(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        mock_message_formatter.render.return_value = "Formatted Info Awal"
        
        session_data = {
            "user_id": "user123",
            "extracted_data": {}
        }
        
        await action_handler.complete_report(session_data, db_session)
        mock_message_formatter.render.assert_called_once()

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_complete_report_none_extracted_data(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        mock_message_formatter.render.return_value = "Formatted Info Awal"
        
        session_data = {
            "user_id": "user123",
            "extracted_data": None
        }
        
        await action_handler.complete_report(session_data, db_session)
        # Should default to {} if we use get("extracted_data", {})
        mock_message_formatter.render.assert_called_once()

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_complete_report_empty_session_data(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        mock_message_formatter.render.return_value = "Formatted Info Awal"
        
        await action_handler.complete_report({}, db_session)
        mock_message_formatter.render.assert_called_once()

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_reply_dispatcher_exception(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        mock_message_formatter.render.return_value = "Formatted Info Awal"
        mock_reply_dispatcher.forward_report_to_all_groups.side_effect = Exception("Dispatcher failed")
        
        session_data = {"user_id": "user123"}
        
        with pytest.raises(Exception) as exc:
            await action_handler.complete_report(session_data, db_session)
        
        assert "Dispatcher failed" in str(exc.value)

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_formatter_returns_empty(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        mock_message_formatter.render.return_value = ""
        
        session_data = {"user_id": "user123"}
        
        result = await action_handler.complete_report(session_data, db_session)
        info_awal_text, saved_report = result
        assert info_awal_text == ""
        mock_reply_dispatcher.forward_report_to_all_groups.assert_awaited_once()
        assert mock_reply_dispatcher.forward_report_to_all_groups.await_args[0][0] == ""

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_complete_report_timezone_wib(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        # WIB: Longitude = 100.0, Expected offset = +7 hours, Label = "G"
        action_handler.report_service.create_report.return_value.koordinat_lng = 100.0
        action_handler.report_service.create_report.return_value.created_at = datetime(2026, 5, 24, 0, 0, 0)
        
        session_data = {
            "user_id": "user123",
            "extracted_data": {
                "koordinat_lng": 100.0,
                "koordinat_lat": -6.0
            }
        }
        
        await action_handler.complete_report(session_data, db_session)
        
        assert mock_message_formatter.render.called
        call_args = mock_message_formatter.render.call_args[0]
        template_data = call_args[1]
        assert template_data["WAKTU_INFO_DITERIMA"] == "0524 0700 G"

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_complete_report_timezone_wita(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        # WITA: Longitude = 120.0, Expected offset = +8 hours, Label = "H"
        action_handler.report_service.create_report.return_value.koordinat_lng = 120.0
        action_handler.report_service.create_report.return_value.created_at = datetime(2026, 5, 24, 0, 0, 0)
        
        session_data = {
            "user_id": "user123",
            "extracted_data": {
                "koordinat_lng": 120.0,
                "koordinat_lat": -5.0
            }
        }
        
        await action_handler.complete_report(session_data, db_session)
        
        assert mock_message_formatter.render.called
        call_args = mock_message_formatter.render.call_args[0]
        template_data = call_args[1]
        assert template_data["WAKTU_INFO_DITERIMA"] == "0524 0800 H"

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_complete_report_timezone_wit(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        # WIT: Longitude = 140.0, Expected offset = +9 hours, Label = "J"
        action_handler.report_service.create_report.return_value.koordinat_lng = 140.0
        action_handler.report_service.create_report.return_value.created_at = datetime(2026, 5, 24, 0, 0, 0)
        
        session_data = {
            "user_id": "user123",
            "extracted_data": {
                "koordinat_lng": 140.0,
                "koordinat_lat": -2.0
            }
        }
        
        await action_handler.complete_report(session_data, db_session)
        
        assert mock_message_formatter.render.called
        call_args = mock_message_formatter.render.call_args[0]
        template_data = call_args[1]
        assert template_data["WAKTU_INFO_DITERIMA"] == "0524 0900 J"

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    async def test_complete_report_timezone_fallback(self, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        # Fallback to WIB (G) if koordinat_lng is None or invalid
        action_handler.report_service.create_report.return_value.koordinat_lng = None
        action_handler.report_service.create_report.return_value.created_at = datetime(2026, 5, 24, 0, 0, 0)
        
        session_data = {
            "user_id": "user123",
            "extracted_data": {
                "koordinat_lng": None,
                "koordinat_lat": None
            }
        }
        
        await action_handler.complete_report(session_data, db_session)
        
        assert mock_message_formatter.render.called
        call_args = mock_message_formatter.render.call_args[0]
        template_data = call_args[1]
        assert template_data["WAKTU_INFO_DITERIMA"] == "0524 0700 G"

    @patch('app.engine.action_handler.message_formatter')
    @patch('app.engine.action_handler.reply_dispatcher', new_callable=AsyncMock)
    @patch('app.services.storage_service.storage_service.download_file_bytes', new_callable=AsyncMock)
    async def test_complete_report_with_attachments(self, mock_download_bytes, mock_reply_dispatcher, mock_message_formatter, action_handler, db_session):
        mock_message_formatter.render.return_value = "Formatted Info Awal"
        
        # Mock Attachment objects
        mock_att = MagicMock()
        mock_att.user_id = "tg_123"
        mock_att.report_id = None
        mock_att.file_key = "some_key"
        mock_att.original_filename = "photo.jpg"
        mock_att.mime_type = "image/jpeg"
        
        # Mock DB execute result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_att]
        db_session.execute = AsyncMock(return_value=mock_result)
        
        mock_download_bytes.return_value = b"filebytes"
        
        session_data = {
            "user_id": "tg_123",
            "extracted_data": {}
        }
        
        await action_handler.complete_report(session_data, db_session)
        
        # Verify attachments were linked
        assert mock_att.report_id == 1
        db_session.add.assert_called_with(mock_att)
        db_session.flush.assert_called()
        
        # Verify files were forwarded to SAR groups
        mock_download_bytes.assert_called_once()
        assert mock_download_bytes.call_args[0][0] == "some_key"
        mock_reply_dispatcher.forward_file_to_telegram_sar_group.assert_awaited_once()
        mock_reply_dispatcher.forward_file_to_whatsapp_sar_group.assert_awaited_once()

