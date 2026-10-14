import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class ReporterLocationFieldProcessor(BaseFieldProcessor):
    """Processes and validates the mandatory reporter GPS location verification ('reporter_location') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        answer_lower = answer_clean.lower()
        
        # Check if they skipped/denied security check
        from app.engine.chatbot_engine import SKIP_WORDS
        if answer_lower in SKIP_WORDS:
            reply = (
                "*Lokasi GPS Wajib Dibagikan*\n\n"
                "Kami memerlukan lokasi GPS Anda untuk memetakan titik penyelamatan. Silakan ketuk tombol **Share Location**."
            )
            return False, {"text": reply, "buttons": self._get_buttons()}

        # Look for real location shared via backend/webhook or formatted text
        has_coords = False
        
        # 1. Check if reporter coordinates are already in extracted_data
        if extracted_data.get("pelapor_lat") is not None and extracted_data.get("pelapor_lng") is not None:
            has_coords = True
            
        # 2. Check if message starts with Lokasi GPS:
        elif message.startswith("Lokasi GPS:"):
            from app.services.rule_extractor import RuleExtractor
            coords = RuleExtractor.extract_koordinat(message)
            if coords:
                extracted_data["pelapor_lat"] = coords[0]
                extracted_data["pelapor_lng"] = coords[1]
                
                # Sinkronisasi balik: Jika pelapor adalah korban, otomatis isi koordinat kejadian
                if extracted_data.get("pelapor_hubungan") == "Korban":
                    extracted_data["koordinat_lat"] = coords[0]
                    extracted_data["koordinat_lng"] = coords[1]
                    extracted_data["_explicit_koordinat"] = True
                has_coords = True

        if has_coords:
            extracted_data["is_current_location_shared"] = True
            extracted_data["reporter_location"] = "Sudah terverifikasi"
            if extracted_data.get("pelapor_hubungan") == "Korban":
                extracted_data["_explicit_koordinat"] = True
            return True, extracted_data
        else:
            reply = "Harap ketuk tombol **Share Location** di bawah untuk membagikan lokasi Anda saat ini."
            return False, {"text": reply, "buttons": self._get_buttons()}

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        q_text = (
            "*Bagikan Lokasi GPS Anda (Wajib)*\n\n"
            "Kami membutuhkan lokasi GPS aktif Anda untuk mengarahkan tim penyelamat ke tempat Anda dengan tepat. Silakan ketuk tombol **Share Location** di bawah."
        )
        return q_text, self._get_buttons()

    def _get_buttons(self) -> list:
        return [{"text": "Share Location", "request_location": True}]
