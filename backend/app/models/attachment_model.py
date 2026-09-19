"""
Attachment Model
================
SQLite-backed metadata for files stored in MinIO S3-compatible storage.
Each attachment is linked to a chat session user and optionally to a report.
"""

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)

    # Link to the report (nullable — attachment may exist before report is completed)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True, index=True)

    # Who sent this attachment
    user_id = Column(String(100), index=True, nullable=False)
    channel = Column(String(20), default="telegram")  # telegram / whatsapp / web

    # S3 storage info
    file_key = Column(String(500), unique=True, nullable=False)  # S3 object key
    bucket = Column(String(100), nullable=False)

    # File metadata
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(BigInteger, nullable=True)  # Size in bytes
    file_type = Column(String(20), nullable=False, default="document")  # photo / audio / video / document

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
