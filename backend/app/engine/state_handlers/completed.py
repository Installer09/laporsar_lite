import logging
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.state_handlers.base import BaseStateHandler

if TYPE_CHECKING:
    from app.engine.chatbot_engine import ChatbotEngine

logger = logging.getLogger(__name__)

class CompletedStateHandler(BaseStateHandler):
    """Handles messages when the report is already completed (COMPLETED state)."""

    async def handle(
        self, engine: "ChatbotEngine", session: ChatSession, message: str, extracted_data: dict, db: AsyncSession, autopilot: bool
    ) -> dict:
        await engine._reset_session(session, db, autopilot)
        reply = "✅ *Sesi Laporan Telah Selesai.*\n\nTerima kasih atas laporan Anda. Tim SAR telah dikerahkan. Untuk membuat laporan baru, silakan ketik /start."
        return {"text": reply}
