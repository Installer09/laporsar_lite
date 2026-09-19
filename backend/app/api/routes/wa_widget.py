"""
WhatsApp Widget API
===================
Provides configuration for the web chat widget that redirects
users to WhatsApp for incident reporting.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models.settings_models import SystemSetting
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/config")
async def get_widget_config(db: AsyncSession = Depends(get_db)):
    """
    Return the WhatsApp click-to-chat URL and widget configuration.
    The frontend embeds a floating button that opens this link.
    """
    # Try to load phone number from database settings first
    phone_number = ""

    try:
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "wa_phone_number")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            phone_number = setting.value
    except Exception as e:
        logger.warning(f"Could not load WA phone from settings: {e}")

    # Fallback to env var
    if not phone_number:
        phone_number = settings.WHATSAPP_PHONE_NUMBER_ID  # reuse this field

    # Build WhatsApp click-to-chat link
    greeting_text = (
        "Halo SARBot, saya ingin melaporkan kejadian darurat."
    )

    if phone_number:
        wa_link = (
            f"https://wa.me/{phone_number}"
            f"?text={greeting_text.replace(' ', '%20')}"
        )
    else:
        wa_link = ""

    return {
        "enabled": bool(phone_number),
        "wa_link": wa_link,
        "phone_number": phone_number,
        "greeting": "Laporkan Kejadian Darurat via WhatsApp",
        "button_text": "Chat via WhatsApp",
        "description": (
            "Kirim laporan kejadian darurat melalui WhatsApp. "
            "Bot kami akan memandu Anda mengisi informasi yang diperlukan."
        ),
    }
