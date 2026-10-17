import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class VictimDataFieldProcessor(BaseFieldProcessor):
    """Processes and validates individual/multiple victim details ('data_korban') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        
        # Check if the input indicates unknown or missing victim details
        unknown_markers = [
            "belum tahu", "tidak tahu", "belum diketahui", "tidak diketahui",
            "identitas belum diketahui", "belum ada data", "belum ada",
            "tidak ada", "tidak ada data", "nihil", "-", "n/a", "unknown", "belum ada data."
        ]
        if answer_clean.lower().strip(".,;:!?") in unknown_markers:
            extracted_data["data_korban"] = []
            return True, extracted_data
        
        # Save the raw victim details text directly.
        # This will be parsed and formatted into structured JSON by the final LLM compilation pass.
        extracted_data["data_korban"] = answer_clean
        return True, extracted_data

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        count_str = extracted_data.get("korban") or extracted_data.get("korban_total") or "1"
        digits = re.findall(r'\d+', str(count_str))
        
        is_unknown = not digits or "belum tahu" in str(count_str).lower() or "belum diketahui" in str(count_str).lower()
        
        if is_unknown or int(digits[0]) <= 1:
            q_text = (
                "*Siapa nama atau ciri-ciri korban?*\n"
                "Sebutkan nama, jenis kelamin, umur, atau ciri korban jika diketahui (contoh: _Budi, Laki-laki, 40 thn_)."
            )
            return q_text, ["Belum Tahu"]
            
        count = int(digits[0])
        try:
            from app.services.message_formatter import message_formatter
            count_word = message_formatter.number_to_words(count).title()
        except Exception:
            count_word = str(count)
            
        q_text = (
            f"*Siapa saja nama atau identitas {count} ({count_word}) orang korban tersebut?*\n"
            "Sebutkan nama, jenis kelamin, atau umur korban yang Anda ketahui dalam satu pesan (contoh: _Andi 25th Laki, Ani 20th Perempuan_)."
        )
        return q_text, ["Belum Tahu"]


DataKorbanFieldProcessor = VictimDataFieldProcessor
