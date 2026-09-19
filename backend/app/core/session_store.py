from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json
from app.models.chat_session import ChatSession

class BaseSessionStore(ABC):
    """
    Abstract interface for managing chatbot sessions.
    Allows easy toggling between SQLite, Redis, or other backends.
    """
    
    @abstractmethod
    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data for a user."""
        pass
        
    @abstractmethod
    async def save_session(self, user_id: str, session_data: Dict[str, Any]):
        """Save or update session data for a user."""
        pass
        
    @abstractmethod
    async def clear_session(self, user_id: str):
        """Clear a user's session."""
        pass


class SQLiteSessionStore(BaseSessionStore):
    """
    SQLite/SQLAlchemy implementation of the session store.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.user_id == user_id).with_for_update()
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
            
        return {
            "id": session.id,
            "user_id": session.user_id,
            "channel": session.channel,
            "state": session.state,
            "extracted_data": json.loads(session.extracted_data) if session.extracted_data else {},
            "contact_name": session.contact_name,
            "contact_phone": session.contact_phone,
            "platform_username": session.platform_username
        }
        
    async def save_session(self, user_id: str, session_data: Dict[str, Any]):
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.user_id == user_id).with_for_update()
        )
        session = result.scalar_one_or_none()
        
        if not session:
            session = ChatSession(user_id=user_id)
            self.db.add(session)
            
        if "channel" in session_data:
            session.channel = session_data["channel"]
        if "state" in session_data:
            session.state = session_data["state"]
        if "extracted_data" in session_data:
            session.extracted_data = json.dumps(session_data["extracted_data"])
        if "contact_name" in session_data:
            session.contact_name = session_data["contact_name"]
        if "contact_phone" in session_data:
            session.contact_phone = session_data["contact_phone"]
        if "platform_username" in session_data:
            session.platform_username = session_data["platform_username"]
            
        await self.db.commit()

    async def clear_session(self, user_id: str):
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.user_id == user_id).with_for_update()
        )
        session = result.scalar_one_or_none()
        if session:
            await self.db.delete(session)
            await self.db.commit()
