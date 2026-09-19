import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.routes.reports import delete_report
from app.models.report import Report
from app.models.attachment_model import Attachment

@pytest.mark.asyncio
async def test_delete_report_with_attachments():
    # Setup mock database session.
    mock_db = AsyncMock()
    mock_report = Report(id=1, no_laporan="SAR-202606-008")
    mock_attachments = [
        Attachment(id=10, report_id=1, file_key="file10"),
        Attachment(id=11, report_id=1, file_key="file11"),
    ]
    
    # Mock database queries.
    mock_report_res = MagicMock()
    mock_report_res.scalar_one_or_none.return_value = mock_report
    
    mock_att_res = MagicMock()
    mock_att_scalars = MagicMock()
    mock_att_scalars.all.return_value = mock_attachments
    mock_att_res.scalars.return_value = mock_att_scalars
    
    mock_db.execute.side_effect = [mock_report_res, mock_att_res]
    
    with patch("app.api.routes.reports.storage_service") as mock_storage, \
         patch("app.api.routes.reports.manager") as mock_manager:
         
        mock_storage.delete_file = AsyncMock()
        mock_manager.broadcast = AsyncMock()
        
        # Call the delete_report route handler.
        await delete_report(report_id=1, db=mock_db)
        
        # Verify db queries.
        assert mock_db.execute.call_count == 2
        
        # Verify storage delete was called for each attachment file key.
        assert mock_storage.delete_file.call_count == 2
        mock_storage.delete_file.assert_any_call("file10")
        mock_storage.delete_file.assert_any_call("file11")
        
        # Verify db.delete was called for the attachments and the report.
        assert mock_db.delete.call_count == 3
        mock_db.delete.assert_any_call(mock_report)
        mock_db.delete.assert_any_call(mock_attachments[0])
        mock_db.delete.assert_any_call(mock_attachments[1])
        
        # Verify transaction commit and websocket notification broadcast.
        mock_db.commit.assert_awaited_once()
        mock_manager.broadcast.assert_awaited_once_with({"event": "report_deleted", "report_id": 1}, db=mock_db)

