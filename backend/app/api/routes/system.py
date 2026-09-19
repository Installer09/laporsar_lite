from fastapi import APIRouter, Depends, HTTPException, status, Response, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.security import verify_jwt, verify_admin, verify_operator_or_admin
from app.services.session_cleanup import cleanup_inactive_sessions
from app.services.system_backup import system_backup_service
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(redirect_slashes=False)

@router.get("/backup", dependencies=[Depends(verify_admin)])
async def get_system_backup(db: AsyncSession = Depends(get_db)):
    """
    Download a full database backup as a compressed ZIP file.
    Only accessible by system administrators.
    """
    try:
        backup_bytes = await system_backup_service.export_backup(db)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sarbot_backup_{timestamp}.zip"
        
        return Response(
            content=backup_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Failed to generate database backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membuat cadangan database: {str(e)}"
        )

@router.post("/restore", dependencies=[Depends(verify_admin)])
async def restore_system_database(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Restore system database from an uploaded ZIP backup.
    Only accessible by system administrators.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File cadangan harus berformat .zip"
        )
    try:
        file_bytes = await file.read()
        result = await system_backup_service.import_restore(file_bytes, db)
        return result
    except Exception as e:
        logger.error(f"Failed to restore database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memulihkan database: {str(e)}"
        )

@router.post("/cleanup-sessions", dependencies=[Depends(verify_admin)])
async def trigger_session_cleanup(hours_inactive: int = 24, db: AsyncSession = Depends(get_db)):
    """
    Admin endpoint to trigger cleanup of inactive chat sessions.
    This prevents the chat_sessions table from growing indefinitely and causing write amplification.
    """
    try:
        deleted_count = await cleanup_inactive_sessions(db, hours_inactive=hours_inactive)
        return {"status": "success", "message": f"Cleaned up {deleted_count} inactive sessions."}
    except Exception as e:
        logger.error(f"Failed to trigger session cleanup: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cleanup failed")

from sqlalchemy.future import select
from sqlalchemy import or_
from app.models.report import Report
from app.models.contact import Contact

@router.get("/search", dependencies=[Depends(verify_operator_or_admin)])
async def global_search(q: str = "", db: AsyncSession = Depends(get_db)):
    """Global search across reports and contacts."""
    if not q or len(q) < 2:
        return {"reports": [], "contacts": []}
    
    # Search reports
    report_query = select(Report).where(
        or_(
            Report.no_laporan.ilike(f"%{q}%"),
            Report.pelapor_nama.ilike(f"%{q}%"),
            Report.jenis_kejadian.ilike(f"%{q}%"),
            Report.lokasi_teks.ilike(f"%{q}%")
        )
    ).limit(5)
    report_res = await db.execute(report_query)
    reports = report_res.scalars().all()

    # Search contacts
    contact_query = select(Contact).where(
        or_(
            Contact.name.ilike(f"%{q}%"),
            Contact.phone_number.ilike(f"%{q}%")
        )
    ).limit(5)
    contact_res = await db.execute(contact_query)
    contacts = contact_res.scalars().all()

    return {
        "reports": [
            {
                "id": r.id, 
                "title": r.no_laporan, 
                "subtitle": f"{r.pelapor_nama} - {r.jenis_kejadian}",
                "type": "report",
                "link": f"/reports?id={r.id}"
            } for r in reports
        ],
        "contacts": [
            {
                "id": c.id, 
                "title": c.name or "Unknown", 
                "subtitle": c.phone_number,
                "type": "contact",
                "link": "/contacts"
            } for c in contacts
        ]
    }
