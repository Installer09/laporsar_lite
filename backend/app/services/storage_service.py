"""
Storage Service (Local Storage Edition for Lapor SAR Lite)
===========================================================
High-performance local filesystem storage service replacing MinIO.
Handles file uploads, streaming downloads, file stats, and disk cleanup.
Maintains 100% backward-compatible interface with MinIO StorageService.
"""

import os
import io
import uuid
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Local filesystem-backed storage engine with management and reporting capabilities."""

    def __init__(self):
        self._initialized = False
        self._base_dir: Path = Path(settings.LOCAL_STORAGE_DIR).resolve()

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    # ----------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------

    async def initialize(self):
        """Ensure base storage directories exist."""
        if self._initialized:
            return

        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            for sub in ["photos", "audios", "videos", "documents"]:
                (self._base_dir / "web" / sub).mkdir(parents=True, exist_ok=True)
                (self._base_dir / "telegram" / sub).mkdir(parents=True, exist_ok=True)
                (self._base_dir / "whatsapp" / sub).mkdir(parents=True, exist_ok=True)

            self._initialized = True
            logger.info(f"StorageService (Local) initialized at: {self._base_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize local StorageService: {e}")
            self._initialized = False

    # ----------------------------------------------------------------
    # Upload
    # ----------------------------------------------------------------

    async def upload_file(
        self,
        file_data: bytes,
        original_filename: str,
        mime_type: str = "application/octet-stream",
        file_type: str = "document",
        user_id: str = "",
        channel: str = "web",
        bucket_name: str = None,
    ) -> Optional[str]:
        """
        Save file data to local storage directory.
        Returns the relative object_key (e.g. 'web/photos/2026/09/uuid_image.jpg').
        """
        try:
            now = datetime.now()
            ext = os.path.splitext(original_filename)[1] if original_filename else ""
            unique_name = f"{uuid.uuid4().hex[:12]}{ext}"
            rel_folder = Path(channel) / f"{file_type}s" / now.strftime("%Y/%m")
            target_dir = self._base_dir / rel_folder
            target_dir.mkdir(parents=True, exist_ok=True)

            target_path = target_dir / unique_name
            with open(target_path, "wb") as f:
                f.write(file_data)

            # Store standard POSIX-like relative key
            object_key = str(rel_folder / unique_name).replace("\\", "/")
            logger.info(f"Saved local file: {object_key} ({len(file_data)} bytes)")
            return object_key
        except Exception as e:
            logger.error(f"Failed to upload local file '{original_filename}': {e}")
            return None

    # ----------------------------------------------------------------
    # Download / URL Generation
    # ----------------------------------------------------------------

    async def get_presigned_url(
        self, object_key: str, expires: int = 3600, bucket_name: str = None
    ) -> Optional[str]:
        """
        In local mode, returns direct API streaming path (/api/storage/files/<object_key>).
        """
        if not object_key:
            return None
        clean_key = object_key.lstrip("/")
        return f"/api/storage/files/{clean_key}"

    async def download_file_bytes(
        self, object_key: str, bucket_name: str = None
    ) -> Optional[bytes]:
        """Read file directly from local storage."""
        if not object_key:
            return None
        file_path = self._resolve_path(object_key)
        if not file_path or not file_path.is_file():
            logger.warning(f"File not found on local disk: {object_key}")
            return None
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {object_key}: {e}")
            return None

    # ----------------------------------------------------------------
    # Delete
    # ----------------------------------------------------------------

    async def delete_file(self, object_key: str, bucket_name: str = None) -> bool:
        """Delete file from local disk."""
        file_path = self._resolve_path(object_key)
        if not file_path or not file_path.is_file():
            logger.warning(f"File to delete does not exist: {object_key}")
            return False
        try:
            file_path.unlink()
            logger.info(f"Deleted local file: {object_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete local file {object_key}: {e}")
            return False

    # ----------------------------------------------------------------
    # Compatibility & Helper Methods
    # ----------------------------------------------------------------

    async def create_bucket_if_not_exists(self, bucket_name: str) -> None:
        """No-op in local storage mode."""
        pass

    def is_available(self) -> bool:
        return self._initialized or self._base_dir.exists()

    def _resolve_path(self, object_key: str) -> Optional[Path]:
        """Safely resolve object key to prevent path traversal."""
        try:
            clean_key = Path(object_key.lstrip("/\\"))
            full_path = (self._base_dir / clean_key).resolve()
            if not str(full_path).startswith(str(self._base_dir)):
                logger.error(f"Path traversal attempt blocked: {object_key}")
                return None
            return full_path
        except Exception as e:
            logger.error(f"Invalid file path {object_key}: {e}")
            return None

    # ----------------------------------------------------------------
    # Storage Management UI APIs
    # ----------------------------------------------------------------

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Calculate disk usage and file breakdown by type."""
        total_size = 0
        total_files = 0
        category_stats = {
            "photos": {"count": 0, "size_bytes": 0},
            "audios": {"count": 0, "size_bytes": 0},
            "videos": {"count": 0, "size_bytes": 0},
            "documents": {"count": 0, "size_bytes": 0},
            "others": {"count": 0, "size_bytes": 0},
        }

        if self._base_dir.exists():
            for root, _, files in os.walk(self._base_dir):
                for f in files:
                    file_path = Path(root) / f
                    try:
                        size = file_path.stat().st_size
                        total_size += size
                        total_files += 1

                        # Determine category from path or extension
                        rel_str = str(file_path.relative_to(self._base_dir)).lower()
                        ext = file_path.suffix.lower()

                        if "photo" in rel_str or ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                            category_stats["photos"]["count"] += 1
                            category_stats["photos"]["size_bytes"] += size
                        elif "audio" in rel_str or ext in [".ogg", ".mp3", ".wav", ".m4a", ".aac"]:
                            category_stats["audios"]["count"] += 1
                            category_stats["audios"]["size_bytes"] += size
                        elif "video" in rel_str or ext in [".mp4", ".mov", ".avi", ".mkv"]:
                            category_stats["videos"]["count"] += 1
                            category_stats["videos"]["size_bytes"] += size
                        elif "document" in rel_str or ext in [".pdf", ".docx", ".doc", ".txt", ".kml"]:
                            category_stats["documents"]["count"] += 1
                            category_stats["documents"]["size_bytes"] += size
                        else:
                            category_stats["others"]["count"] += 1
                            category_stats["others"]["size_bytes"] += size
                    except Exception:
                        pass

        # Check free disk space
        try:
            total_disk, used_disk, free_disk = shutil.disk_usage(self._base_dir)
        except Exception:
            total_disk, used_disk, free_disk = 0, 0, 0

        return {
            "storage_type": "local",
            "storage_path": str(self._base_dir),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "disk_free_gb": round(free_disk / (1024 * 1024 * 1024), 2),
            "categories": category_stats,
        }

    async def list_files(
        self, category: Optional[str] = None, limit: int = 100, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """List stored files with metadata for the management UI."""
        items = []
        if not self._base_dir.exists():
            return items

        for root, _, files in os.walk(self._base_dir):
            for f in files:
                file_path = Path(root) / f
                try:
                    rel_path = file_path.relative_to(self._base_dir)
                    object_key = str(rel_path).replace("\\", "/")
                    stat = file_path.stat()

                    # Determine category
                    rel_str = object_key.lower()
                    ext = file_path.suffix.lower()
                    detected_cat = "other"
                    if "photo" in rel_str or ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                        detected_cat = "photo"
                    elif "audio" in rel_str or ext in [".ogg", ".mp3", ".wav", ".m4a", ".aac"]:
                        detected_cat = "audio"
                    elif "video" in rel_str or ext in [".mp4", ".mov", ".avi", ".mkv"]:
                        detected_cat = "video"
                    elif "document" in rel_str or ext in [".pdf", ".docx", ".doc", ".txt", ".kml"]:
                        detected_cat = "document"

                    if category and category.lower() != "all" and detected_cat != category.lower().rstrip("s"):
                        continue

                    items.append({
                        "key": object_key,
                        "filename": f,
                        "category": detected_cat,
                        "size_bytes": stat.st_size,
                        "size_formatted": self._format_size(stat.st_size),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "url": f"/api/storage/files/{object_key}",
                    })
                except Exception:
                    pass

        # Sort newest first
        items.sort(key=lambda x: x["modified_at"], reverse=True)
        return items[skip : skip + limit]

    async def cleanup_all_test_files(self) -> Dict[str, Any]:
        """Clean all files in uploads directory (useful for resetting demo state)."""
        deleted_count = 0
        deleted_bytes = 0
        if self._base_dir.exists():
            for root, dirs, files in os.walk(self._base_dir, topdown=False):
                for f in files:
                    fp = Path(root) / f
                    try:
                        deleted_bytes += fp.stat().st_size
                        fp.unlink()
                        deleted_count += 1
                    except Exception:
                        pass
                for d in dirs:
                    dp = Path(root) / d
                    try:
                        dp.rmdir()
                    except Exception:
                        pass
        await self.initialize()
        return {"deleted_files": deleted_count, "freed_bytes": deleted_bytes}

    @staticmethod
    def _format_size(num_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if num_bytes < 1024.0:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} TB"


# Singleton instance
storage_service = StorageService()
