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
        single_person_words = ["sendiri", "sendirian", "seorang", "seorang diri", "1 orang", "satu orang"]
        if any(sp in val_str for sp in single_person_words):
            extracted_data["korban"] = "1 orang"
            return True, extracted_data

        if re.search(r'\d+', val_str):
            has_number = True
        else:
            from app.services.rule_extractor import RuleExtractor
            num_words = ["satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "seorang", "seorang diri", "abk", "nelayan", "penumpang", "kru", "awak", "korban", "kakak", "adik", "ayah", "ibu", "suami", "istri", "anak", "teman", "rekan"]
            if RuleExtractor._dictionary_cache:
                db_num_words = []
                for cat in ["QUANTIFIER", "VICTIM_ROLE"]:
                    for item in RuleExtractor._dictionary_cache.get(cat, []):
                        db_num_words.append(item["word"].lower())
                if db_num_words:
                    num_words = list(set(num_words + db_num_words))
            if any(nw in val_str for nw in num_words):
                has_number = True
                
        from app.services.rule_extractor import RuleExtractor
        parsed = RuleExtractor.extract_victim_count(answer_clean)
        if parsed:
            extracted_data["korban"] = parsed
            return True, extracted_data

        # Try AI-First contextual extraction before rejecting or falling back to naive digit regex
        if not answer_clean.isdigit() and len(answer_clean.split()) >= 2:
            try:
                import json
                from app.services.incident_data_service import extract_incident_data
                try:
                    history_list = json.loads(session.conversation_history)
                except Exception:
                    history_list = []
                nlp_data = await extract_incident_data(message, db, session.user_id, history_list, use_llm=True)
                if nlp_data and nlp_data.get("korban") and str(nlp_data.get("korban")).strip() not in ("", "Nihil", "Belum ada data", "-"):
                    extracted_data["korban"] = str(nlp_data["korban"]).strip()
                    return True, extracted_data
            except Exception as ex:
                logger.warning(f"AI fallback in VictimFieldProcessor failed: {ex}")

        if not has_number:
            reply = (
                "*Format Jumlah Korban Tidak Valid*\n\n"
                "Mohon ketik jumlah korban berupa angka secara langsung (contoh: _1_ atau _3 orang_) atau pilih *Belum Tahu*."
            )
            return False, {"text": reply, "buttons": ["Belum Tahu"]}

        digit_m = re.search(r'\b(\d+)\b', answer_clean)
        if digit_m:
            extracted_data["korban"] = f"{digit_m.group(1)} orang"
        else:
            extracted_data["korban"] = "1 orang" if any(w in val_str for w in ["satu", "kakak", "adik", "ayah", "ibu", "suami", "istri", "anak"]) else answer_clean
        return True, extracted_data

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        q_text = (
            "*Berapa perkiraan jumlah korban dalam kejadian ini?*\n"
            "Ketik jumlah orangnya secara langsung (contoh: _1_ atau _3 orang_)."
        )
        return q_text, ["Belum Tahu"]


KorbanFieldProcessor = VictimFieldProcessor
