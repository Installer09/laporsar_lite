from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat_session import ChatSession

if TYPE_CHECKING:
    from app.engine.chatbot_engine import ChatbotEngine

class BaseStateHandler:
    """Abstract base class for state-specific message handling in ChatbotEngine."""
    
    async def handle(
        self, engine: "ChatbotEngine", session: ChatSession, message: str, extracted_data: dict, db: AsyncSession, autopilot: bool
    ) -> dict:
        """
        Handles the message based on the current state.
        
        Returns:
            dict response containing keys like 'text', 'buttons', etc.
        """
        raise NotImplementedError()
