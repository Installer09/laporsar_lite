"""
Attachment Schemas
==================
Pydantic schemas for attachment API responses.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class AttachmentResponse(BaseModel):
    """Response schema for a single attachment."""
    id: int
    report_id: Optional[int] = None
    user_id: str
    channel: str
    file_key: str
    bucket: str
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    file_type: str
    created_at: Optional[datetime] = None
    download_url: Optional[str] = None  # Presigned URL, populated on demand

    model_config = ConfigDict(from_attributes=True)


class AttachmentLinkRequest(BaseModel):
    """Request to link an attachment to a report."""
    report_id: int
