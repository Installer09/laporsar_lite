import io
import json
import zipfile
import logging
import datetime
from typing import Dict, List, Any
from sqlalchemy import select, delete, Column, DateTime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings_models import SystemSetting, Location, Classification
from app.models.knowledge_models import DictionaryWord, SOPDocument
from app.models.contact import Contact
from app.models.report import Report, ReportSequence
from app.models.vector_memory import VectorMemory
from app.models.attachment_model import Attachment

logger = logging.getLogger(__name__)

# Ordered list of models to define dependencies for safe deletions and insertions
MODELS_BACKUP_ORDER = [
    ("system_settings", SystemSetting),
    ("locations", Location),
    ("classifications", Classification),
    ("contacts", Contact),
    ("sop_documents", SOPDocument),
    ("dictionary_words", DictionaryWord),
    ("reports", Report),
    ("report_sequences", ReportSequence),
    ("attachments", Attachment),
    ("vector_memory", VectorMemory),
]

# Helper to serialize values
def _serialize_val(val: Any) -> Any:
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.isoformat()
    return val

# Helper to deserialize values based on column type
def _deserialize_val(c: Column, val: Any) -> Any:
    if val is None:
        return None
    if isinstance(c.type, DateTime) and isinstance(val, str):
        try:
            return datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return val
    return val

class SystemBackupService:
    """Service to handle database backup (export ZIP/JSON) and restore (import ZIP/JSON)."""

    @staticmethod
    async def export_backup(db: AsyncSession) -> bytes:
        """
        Export all relevant system tables into a single in-memory ZIP archive.
        Contains modular JSON files for each table.
        """
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for table_name, model_class in MODELS_BACKUP_ORDER:
                try:
                    # Query all rows in table
                    result = await db.execute(select(model_class))
                    instances = result.scalars().all()

                    # Convert instances to list of dicts
                    rows_dict = []
                    for inst in instances:
                        row = {
                            c.name: _serialize_val(getattr(inst, c.name))
                            for c in model_class.__table__.columns
                        }
                        rows_dict.append(row)

                    # Write to ZIP as JSON
                    json_data = json.dumps(rows_dict, indent=2, ensure_ascii=False)
                    zip_file.writestr(f"{table_name}.json", json_data)
                    logger.info(f"Backed up {len(rows_dict)} rows from table {table_name}")

                except Exception as e:
                    logger.error(f"Failed to backup table {table_name}: {e}")
                    raise Exception(f"Failed to export {table_name}: {str(e)}")

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    @staticmethod
    async def import_restore(backup_bytes: bytes, db: AsyncSession) -> dict:
        """
        Restore the database from an uploaded ZIP archive containing modular JSON files.
        Wraps everything in a single database transaction with automatic rollback if failed.
        """
        try:
            zip_buffer = io.BytesIO(backup_bytes)
            uploaded_data: Dict[str, List[Dict[str, Any]]] = {}

            # 1. Read and parse ZIP contents in memory
            with zipfile.ZipFile(zip_buffer, "r") as zip_file:
                file_list = zip_file.namelist()
                for table_name, _ in MODELS_BACKUP_ORDER:
                    filename = f"{table_name}.json"
                    if filename in file_list:
                        try:
                            json_bytes = zip_file.read(filename)
                            uploaded_data[table_name] = json.loads(json_bytes.decode("utf-8"))
                        except Exception as parse_err:
                            raise Exception(f"Format JSON pada file {filename} tidak valid: {parse_err}")
                    else:
                        uploaded_data[table_name] = []

            # 2. Execute transactional database restore
            # Open nested transaction (so rollback works atomically)
            async with db.begin_nested():
                # --- Step A: Delete children first, then parent tables in reverse order ---
                for table_name, model_class in reversed(MODELS_BACKUP_ORDER):
                    await db.execute(delete(model_class))
                await db.flush()

                restore_counts = {}

                # --- Step B: Insert records in forward order ---
                for table_name, model_class in MODELS_BACKUP_ORDER:
                    rows = uploaded_data.get(table_name, [])
                    logger.info(f"Restoring {len(rows)} rows into {table_name}")
                    
                    for idx, row in enumerate(rows):
                        # Construct a new model instance
                        instance_data = {}
                        for c in model_class.__table__.columns:
                            if c.name in row:
                                instance_data[c.name] = _deserialize_val(c, row[c.name])
                        
                        new_instance = model_class(**instance_data)
                        db.add(new_instance)
                    
                    restore_counts[table_name] = len(rows)
                
                await db.flush()

            # Commit the outer transaction
            await db.commit()
            logger.info("Database restore committed successfully")

            # 3. Post-Restore action: Pre-warm caches
            try:
                from app.services.rule_extractor import RuleExtractor
                from app.services.autocorrect_service import AutoCorrectService
                await RuleExtractor.load_cache(db)
                await AutoCorrectService.load_cache(db)
                logger.info("RuleExtractor and AutoCorrectService caches re-warmed successfully after restore")
            except Exception as cache_err:
                logger.warning(f"Failed to pre-warm dictionary caches after restore (non-fatal): {cache_err}")

            return {
                "status": "success",
                "message": "Database berhasil direstore secara penuh",
                "counts": restore_counts,
            }

        except Exception as restore_err:
            await db.rollback()
            logger.error(f"Database restore aborted & rolled back: {restore_err}")
            raise Exception(f"Restorasi gagal: {str(restore_err)}")

# Singleton instance
system_backup_service = SystemBackupService()
