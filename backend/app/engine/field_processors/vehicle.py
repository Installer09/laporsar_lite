import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class VehicleFieldProcessor(BaseFieldProcessor):
    """Processes and validates incident vehicle conditional fields ('data_kapal', 'data_pesawat', 'data_alat')."""

    def __init__(self, field_name: str):
        self.field_name = field_name

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        
        lower_ans = answer_clean.lower()
        negative_names = [
            "tidak ada nama", "tidak ada namanya", "tanpa nama", "belum ada nama",
            "tidak tahu namanya", "gak tau namanya", "nggak tahu namanya"
        ]
        is_negative = any(neg in lower_ans for neg in negative_names)

        if self.field_name == "data_kapal":
            from app.services.rule_extractor import RuleExtractor
            kapal = RuleExtractor.extract_data_kapal(answer_clean)
            if kapal and not is_negative:
                extracted_data["data_kapal"] = kapal
            elif is_negative:
                extracted_data["data_kapal"] = kapal if (kapal and "tanpa nama" in kapal.lower()) else "Kapal Tanpa Nama"
            else:
                extracted_data["data_kapal"] = answer_clean
        else:
            extracted_data[self.field_name] = "Tanpa Keterangan" if is_negative else answer_clean
            
        extracted_data[f"_explicit_{self.field_name}"] = True
        return True, extracted_data

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        from app.engine.chatbot_engine import FIELD_QUESTIONS
        question = FIELD_QUESTIONS.get(self.field_name, {})
        q_text = question.get("text", "")
        buttons = question.get("buttons", ["Belum Tahu"])
        return q_text, buttons
