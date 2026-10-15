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
        is_public_url = base_url.startswith("https://") or (not any(h in base_url for h in [".lan", "localhost", "127.0.0.1"]))
        webview_url = f"{base_url}/location-picker?session_id={session.id}"
        
        map_link_line = f"• Atau buka [Peta Titik Darurat SAR]({webview_url}) untuk menandai posisi kejadian.\n" if is_public_url else ""
        
        q_text = (
            "*Apakah Anda memiliki titik koordinat GPS kejadian?*\n\n"
            "Anda dapat memberikan titik lokasi kejadian dengan cara:\n"
            "1. Ketuk tombol *Bagikan Lokasi Kejadian* di bawah (jika Anda berada di lokasi kejadian).\n"
            "2. Atau kirim via menu lampiran pesan -> *Lokasi* (bisa geser pin ke posisi musibah).\n"
            "3. Atau ketik angka koordinat / tautan Google Maps (contoh: _-3.391282, 106.241521_).\n"
            f"{map_link_line}"
            "4. Jika tidak tahu titik koordinatnya, pilih tombol *Belum Tahu* (cukup nama perairan/tempat yang sudah Anda sebutkan)."
        )
        buttons = [{"text": "Bagikan Lokasi Kejadian", "request_location": True}, "Belum Tahu"]
        return q_text, buttons
