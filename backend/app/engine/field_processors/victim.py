import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class VictimFieldProcessor(BaseFieldProcessor):
    """Processes and validates the victim count ('korban') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        val_str = answer_clean.lower()
        
        # Check if the user says they don't know the victim count
        unknown_terms = ["belum tahu", "tidak tahu", "belum tau", "tidak tau", "ndak tahu", "ndak tau", "belum diketahui", "tidak diketahui", "kurang tahu", "belum jelas", "nihil", "n/a"]
        normalized_answer = re.sub(r'[.,;:!?]+$', '', val_str).strip()
        if normalized_answer in unknown_terms or any(t in normalized_answer for t in ["tidak tahu", "belum tahu", "tidak tau", "belum tau", "ndak tahu", "belum diketahui"]):
            extracted_data["korban"] = "Belum Diketahui"
            extracted_data["_explicit_korban"] = True
            return True, extracted_data
        
        # Check if the user selected one of our custom buttons
        range_mappings = {
            "kurang dari 3 orang": "Kurang dari 3 orang (Estimasi)",
            "3 - 5 orang": "3 - 5 orang (Estimasi)",
            "lebih dari 5 orang": "Lebih dari 5 orang (Estimasi)",
            "belum tahu": "Belum Diketahui"
        }
        
        if val_str in range_mappings:
            extracted_data["korban"] = range_mappings[val_str]
            if val_str == "belum tahu":
                extracted_data["_explicit_korban"] = True
            return True, extracted_data
            
        has_number = False
        if re.search(r'\d+', val_str):
            has_number = True
        else:
            from app.services.rule_extractor import RuleExtractor
            num_words = ["satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "seorang", "seorang diri", "abk", "nelayan", "penumpang", "kru", "awak", "korban"]
            if RuleExtractor._dictionary_cache:
                db_num_words = []
                for cat in ["QUANTIFIER", "VICTIM_ROLE"]:
                    for item in RuleExtractor._dictionary_cache.get(cat, []):
                        db_num_words.append(item["word"].lower())
                if db_num_words:
                    num_words = list(set(num_words + db_num_words))
            if any(nw in val_str for nw in num_words):
                has_number = True
                
        if not has_number:
            reply = (
                "*Format Jumlah Korban Tidak Valid*\n\n"
                "Mohon ketik jumlah korban berupa angka secara langsung (contoh: _3_) atau ketuk tombol **Belum Tahu**."
            )
            buttons = ["Kurang dari 3 orang", "3 - 5 orang", "Lebih dari 5 orang", "Belum Tahu"]
            return False, {"text": reply, "buttons": buttons}
            
        from app.services.rule_extractor import RuleExtractor
        parsed = RuleExtractor.extract_korban(answer_clean)
        extracted_data["korban"] = parsed if parsed else answer_clean
        return True, extracted_data

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        q_text = (
            "*Berapa perkiraan jumlah total korban?*\n"
            "Ketik jumlahnya secara langsung (contoh: _3 orang_) atau pilih tombol di bawah jika tidak tahu pasti."
        )
        buttons = ["Kurang dari 3 orang", "3 - 5 orang", "Lebih dari 5 orang", "Belum Tahu"]
        return q_text, buttons


KorbanFieldProcessor = VictimFieldProcessor
