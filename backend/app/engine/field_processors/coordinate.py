import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class CoordinateFieldProcessor(BaseFieldProcessor):
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
        is_public_url = base_url.startswith("https://") or (not any(h in base_url for h in [".lan", "localhost", "127.0.0.1"]))
        webview_url = f"{base_url}/location-picker?session_id={session.id}"
        
        map_link_line = f"\nAtau tandai titiknya melalui [Peta Titik Darurat SAR]({webview_url})." if is_public_url else ""
        
        q_text = (
            "*Apakah Anda mengetahui titik koordinat lokasi kejadian?*\n"
            "Kirimkan titik GPS / tautan Google Maps jika ada, atau pilih *Belum Tahu* jika hanya mengetahui nama tempatnya."
            f"{map_link_line}"
        )
        buttons = [{"text": "Bagikan Lokasi Kejadian", "request_location": True}, "Belum Tahu"]
        return q_text, buttons


KoordinatFieldProcessor = CoordinateFieldProcessor
