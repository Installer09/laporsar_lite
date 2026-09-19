"""
Storage API Routes (Lapor SAR Lite)
===================================
Provides endpoints for:
1. File Streaming with proper MIME types & audio byte range requests.
2. Storage statistics (Disk usage, file counts).
3. File listing and deletion for the Storage Manager UI.
4. Demo cleanup reset.
"""

import os
import mimetypes
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse

from app.services.storage_service import storage_service
from app.core.security import verify_jwt, verify_admin
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
async def get_storage_stats(
    payload: dict = Depends(verify_jwt),
):
    """Get storage statistics (disk space, breakdown by type)."""
    stats = await storage_service.get_storage_stats()
    return stats


@router.get("/files")
async def list_storage_files(
    category: Optional[str] = Query(None, description="Filter: all, photo, audio, video, document"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    payload: dict = Depends(verify_jwt),
):
    """List stored files for the Storage Manager UI."""
    files = await storage_service.list_files(category=category, limit=limit, skip=skip)
    return {
        "total": len(files),
        "items": files
    }


@router.get("/files/{filepath:path}")
async def stream_storage_file(filepath: str):
    """
    Stream a stored file to client.
    Publicly accessible so frontend audio players and image tags can load directly.
    """
    full_path = storage_service._resolve_path(filepath)
    if not full_path or not full_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filepath}"
        )

    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(full_path))
    if not mime_type:
        ext = full_path.suffix.lower()
        if ext in [".ogg"]:
            mime_type = "audio/ogg"
        elif ext in [".mp3"]:
            mime_type = "audio/mpeg"
        elif ext in [".wav"]:
            mime_type = "audio/wav"
        elif ext in [".m4a"]:
            mime_type = "audio/mp4"
        elif ext in [".webp"]:
            mime_type = "image/webp"
        else:
            mime_type = "application/octet-stream"

    return FileResponse(
        path=str(full_path),
        media_type=mime_type,
        filename=full_path.name,
    )


@router.delete("/files/{filepath:path}")
async def delete_storage_file(
    filepath: str,
    payload: dict = Depends(verify_admin),
):
    """Delete a file from storage (Admin only)."""
    success = await storage_service.delete_file(filepath)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File could not be deleted or does not exist."
        )
    return {"message": "File deleted successfully", "filepath": filepath}


@router.post("/cleanup")
async def cleanup_test_files(
    payload: dict = Depends(verify_admin),
):
    """Reset / cleanup all demo uploads (Admin only)."""
    result = await storage_service.cleanup_all_test_files()
    return {
        "message": "Storage cleaned successfully",
        **result
    }
