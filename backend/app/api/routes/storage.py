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
from app.db.session import get_db, get_tenant
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
async def get_storage_stats(
    payload: dict = Depends(verify_jwt),
    tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get storage statistics isolated for the active tenant."""
    tenant_slug = tenant.slug if tenant else payload.get("tenant_slug", "pusat")
    stats = await storage_service.get_storage_stats(tenant_slug=tenant_slug, db=db)
    return stats


@router.get("/files")
async def list_storage_files(
    category: Optional[str] = Query(None, description="Filter: all, photo, audio, video, document"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    payload: dict = Depends(verify_jwt),
    tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List stored files isolated for the active tenant."""
    tenant_slug = tenant.slug if tenant else payload.get("tenant_slug", "pusat")
    files = await storage_service.list_files(
        category=category,
        limit=limit,
        skip=skip,
        tenant_slug=tenant_slug,
        db=db
    )
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
    tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a file from storage with tenant boundary verification (Admin only)."""
    tenant_slug = tenant.slug if tenant else payload.get("tenant_slug", "pusat")
    is_super_admin = payload.get("role") == "Super Admin" and tenant_slug in (None, "pusat")
    
    success = await storage_service.delete_file(
        filepath,
        tenant_slug=tenant_slug,
        is_super_admin=is_super_admin,
        db=db
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas tidak ditemukan atau Anda tidak memiliki izin untuk menghapusnya."
        )
    return {"message": "File deleted successfully", "filepath": filepath}


@router.post("/cleanup")
async def cleanup_test_files(
    payload: dict = Depends(verify_admin),
    tenant = Depends(get_tenant),
):
    """Reset / cleanup demo uploads strictly for the active tenant (Admin only)."""
    tenant_slug = tenant.slug if tenant else payload.get("tenant_slug", "pusat")
    is_super_admin = payload.get("role") == "Super Admin" and tenant_slug in (None, "pusat")
    
    result = await storage_service.cleanup_all_test_files(
        tenant_slug=tenant_slug,
        is_super_admin=is_super_admin
    )
    return {
        "message": f"Penyimpanan berkas untuk instansi '{tenant_slug}' berhasil dibersihkan",
        **result
    }
