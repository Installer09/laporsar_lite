"""
Attachments API Routes
=======================
REST API for managing file attachments stored in MinIO.
Provides endpoints to list, download (presigned URLs), link, and delete attachments.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.session import get_db
from app.models.attachment_model import Attachment
from app.schemas.attachment_schemas import AttachmentResponse, AttachmentLinkRequest
from app.services.storage_service import storage_service
from app.core.security import verify_jwt, verify_admin
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/report/{report_id}",
    response_model=List[AttachmentResponse],
)
async def get_report_attachments(
    report_id: int,
    payload: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    """List all attachments linked to a specific report."""
    result = await db.execute(
        select(Attachment)
        .where(Attachment.report_id == report_id)
        .order_by(Attachment.created_at.desc())
    )
    attachments = result.scalars().all()

    # Filter attachments for non-operator/non-admin users (mobile reporters)
    user_role = payload.get("role")
    if user_role not in ("admin", "Super Admin", "Operator"):
        contact_id = payload.get("contact_id")
        phone = payload.get("sub", "")
        clean_phone = "".join(c for c in phone if c.isdigit())
        allowed_user_ids = {
            f"mobile_{contact_id}",
            phone,
            f"wa_{phone}",
            f"wa_{clean_phone}"
        }
        attachments = [a for a in attachments if a.user_id in allowed_user_ids]

    # Generate presigned URLs for each attachment
    response = []
    for att in attachments:
        att_dict = AttachmentResponse.model_validate(att)
        att_dict.download_url = await storage_service.get_presigned_url(att.file_key)
        response.append(att_dict)

    return response


@router.get(
    "/user/{user_id}",
    response_model=List[AttachmentResponse],
)
async def get_user_attachments(
    user_id: str, 
    payload: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    """List all attachments uploaded by a specific user."""
    if payload.get("sub") != user_id and payload.get("role") not in ("admin", "Super Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Forbidden: You can only view your own attachments"
        )
    result = await db.execute(
        select(Attachment)
        .where(Attachment.user_id == user_id)
        .order_by(Attachment.created_at.desc())
    )
    attachments = result.scalars().all()

    response = []
    for att in attachments:
        att_dict = AttachmentResponse.model_validate(att)
        att_dict.download_url = await storage_service.get_presigned_url(att.file_key)
        response.append(att_dict)

    return response


@router.get(
    "/download/{attachment_id}",
)
async def get_attachment_download_url(
    attachment_id: int,
    payload: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    """Get a presigned download URL for a specific attachment."""
    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id)
    )
    att = result.scalar_one_or_none()

    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # Ownership check: If not admin/operator, verify reporter ownership
    user_role = payload.get("role")
    if user_role not in ("admin", "Super Admin", "Operator"):
        contact_id = payload.get("contact_id")
        phone = payload.get("sub", "")
        clean_phone = "".join(c for c in phone if c.isdigit())
        allowed_user_ids = {
            f"mobile_{contact_id}",
            phone,
            f"wa_{phone}",
            f"wa_{clean_phone}"
        }
        if att.user_id not in allowed_user_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You can only download your own attachments"
            )

    url = await storage_service.get_presigned_url(att.file_key)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
        )

    return {
        "id": att.id,
        "original_filename": att.original_filename,
        "mime_type": att.mime_type,
        "download_url": url,
    }


@router.put(
    "/{attachment_id}/link",
    response_model=AttachmentResponse,
)
async def link_attachment_to_report(
    attachment_id: int,
    body: AttachmentLinkRequest,
    payload: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db),
):
    """Link an unlinked attachment to a report."""
    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id)
    )
    att = result.scalar_one_or_none()

    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # Ownership check: Only owner of attachment or admin can link it
    if att.user_id != payload.get("sub") and payload.get("role") not in ("admin", "Super Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only link your own attachments"
        )

    att.report_id = body.report_id
    try:
        await db.commit()
        await db.refresh(att)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to link attachment: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

    att_resp = AttachmentResponse.model_validate(att)
    att_resp.download_url = await storage_service.get_presigned_url(att.file_key)
    return att_resp


@router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_admin)],
)
async def delete_attachment(
    attachment_id: int, db: AsyncSession = Depends(get_db)
):
    """Delete an attachment from both MinIO and the database."""
    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id)
    )
    att = result.scalar_one_or_none()

    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # Delete from MinIO
    await storage_service.delete_file(att.file_key)

    # Delete from database
    await db.delete(att)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete attachment: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

    logger.info(f"Deleted attachment {attachment_id} (key: {att.file_key})")


@router.get(
    "/unlinked/{user_id}",
    response_model=List[AttachmentResponse],
)
async def get_unlinked_attachments(
    user_id: str, 
    payload: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    """List attachments not yet linked to any report (for linking during report creation)."""
    if payload.get("sub") != user_id and payload.get("role") not in ("admin", "Super Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Forbidden: You can only view your own unlinked attachments"
        )
    result = await db.execute(
        select(Attachment)
        .where(Attachment.user_id == user_id, Attachment.report_id == None)
        .order_by(Attachment.created_at.desc())
    )
    attachments = result.scalars().all()

    response = []
    for att in attachments:
        att_dict = AttachmentResponse.model_validate(att)
        att_dict.download_url = await storage_service.get_presigned_url(att.file_key)
        response.append(att_dict)

    return response
