import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class KoordinatFieldProcessor(BaseFieldProcessor):
    """Processes and validates the GPS coordinates ('koordinat') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        
        from app.services.rule_extractor import RuleExtractor
        coords = RuleExtractor.extract_koordinat(answer_clean)
        
        if coords:
            extracted_data["koordinat_lat"] = coords[0]
            extracted_data["koordinat_lng"] = coords[1]
            extracted_data["koordinat"] = answer_clean
        else:
            extracted_data["koordinat"] = answer_clean
            
        extracted_data["_explicit_koordinat"] = True
        return True, extracted_data

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        from app.core.config import settings
        base_url = settings.FRONTEND_URL.rstrip('/')
        webview_url = f"{base_url}/location-picker?session_id={session.id}"
        
        q_text = (
            "*Apakah Anda memiliki koordinat GPS lokasi kejadian?*\n"
            f"Kirimkan koordinatnya, bagikan lokasi GPS Anda, atau gunakan [Peta Lapor SAR]({webview_url}) untuk menandai lokasi kejadian secara presisi."
        )
        buttons = [{"text": "Share Location", "request_location": True}, "Belum Tahu"]
        return q_text, buttons
