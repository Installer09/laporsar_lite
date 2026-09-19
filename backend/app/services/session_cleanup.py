from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from datetime import timedelta
from sqlalchemy.sql import func
import logging

from app.models.chat_session import ChatSession

logger = logging.getLogger(__name__)

async def cleanup_inactive_sessions(db: AsyncSession, hours_inactive: int = 24) -> int:
    """
    Deletes ChatSessions that have not been updated for the specified number of hours.
    Returns the number of deleted sessions.
    """
    try:
        # Calculate the threshold datetime using DB server time or Python time.
        # It's safer to let the DB compute it if possible, but SQLAlchemy core has text()
        # For cross-compatibility (SQLite/PostgreSQL), it's often easiest to compute in Python
        from datetime import datetime, timezone
        threshold_time = datetime.now(timezone.utc) - timedelta(hours=hours_inactive)
        
        # In SQLite, timezone handling can be tricky, so we rely on simple comparison
        stmt = delete(ChatSession).where(ChatSession.updated_at < threshold_time)
        result = await db.execute(stmt)
        await db.commit()
        
        deleted_count = result.rowcount
        logger.info(f"Cleaned up {deleted_count} inactive chat sessions.")
        return deleted_count
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to cleanup chat sessions: {e}")
        return 0
