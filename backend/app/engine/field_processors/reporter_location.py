import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class ReporterLocationFieldProcessor(BaseFieldProcessor):
    """Processes and validates the reporter GPS location verification ('reporter_location') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        answer_lower = answer_clean.lower()
        
        # Check if they skipped or are not at location
        from app.engine.chatbot_engine import SKIP_WORDS
        not_at_location_words = [
            "tidak di lokasi", "bukan di lokasi", "di rumah", "posisi di rumah", 
            "jauh dari lokasi", "tidak berada di lokasi", "bukan korban", "keluarga"
        ]
        is_skip = (
            answer_lower in SKIP_WORDS 
            or any(w in answer_lower for w in not_at_location_words)
            or answer_lower in ("saya tidak di lokasi", "lewati", "skip", "tidak ada")
        )

        if is_skip:
            extracted_data["is_current_location_shared"] = True
            extracted_data["reporter_location"] = "Pelapor tidak berada di lokasi kejadian"
            return True, extracted_data

        # Look for real location shared via backend/webhook or formatted text
        has_coords = False
        
        # 1. Check if reporter coordinates are already in extracted_data
        if extracted_data.get("pelapor_lat") is not None and extracted_data.get("pelapor_lng") is not None:
            has_coords = True
            
        # 2. Check if message starts with Lokasi GPS: or has coordinates
        else:
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
            reply = (
                "*Verifikasi Lokasi Pelapor*\n\n"
                "Silakan ketuk tombol **Share Location** (*📍 Bagikan Lokasi Saya*) jika Anda berada di lokasi kejadian, "
                "atau pilih tombol *Saya Tidak di Lokasi* jika Anda melapor dari rumah/darat."
            )
            return False, {"text": reply, "buttons": self._get_buttons()}

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        q_text = (
            "*Verifikasi Posisi Pelapor*\n\n"
            "Apakah Anda saat ini berada di lokasi kejadian?\n"
            "• Jika *Ya*, silakan bagikan titik lokasi GPS perangkat Anda.\n"
            "• Jika *Tidak* (misal melapor dari darat/rumah), pilih tombol *Saya Tidak di Lokasi*."
        )
        return q_text, self._get_buttons()

    def _get_buttons(self) -> list:
        return [
            {"text": "📍 Bagikan Lokasi Saya", "request_location": True},
            "Saya Tidak di Lokasi",
            "Lewati"
        ]
