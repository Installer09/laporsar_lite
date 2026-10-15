"""
Chat Session Model
==================
SQLite-backed session state for the chatbot state machine.
Replaces Redis-based sessions for simpler deployment (no Redis required).
Each user (identified by channel-prefixed ID) has exactly one active session.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)

    # Unique user identifier, prefixed by channel: "tg_123456" / "wa_628xxx"
    user_id = Column(String(100), unique=True, index=True, nullable=False)

    # Source channel: "telegram" / "whatsapp" / "web"
    channel = Column(String(20), default="web")

    # Current state machine position
    state = Column(String(50), default="MAIN_MENU")

    # JSON blob storing partially-extracted report fields
    # e.g. {"waktu": "tadi pagi", "lokasi_teks": "Tidak diketahui", ...}
    extracted_data = Column(Text, default="{}")

    # JSON blob storing chat history for LLM context
    # format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    conversation_history = Column(Text, default="[]")

    # Reporter identity (auto-captured from Telegram/WhatsApp profile)
    contact_name = Column(String(100), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    platform_username = Column(String(100), nullable=True)  # e.g. @telegram_user

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
