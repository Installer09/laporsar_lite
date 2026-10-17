import json
import logging
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.state_handlers.base import BaseStateHandler

if TYPE_CHECKING:
    from app.engine.chatbot_engine import ChatbotEngine
from app.engine.field_processors import get_field_processor

logger = logging.getLogger(__name__)

class AwaitingFieldStateHandler(BaseStateHandler):
    """Handles messages when the chatbot is awaiting a specific incident details field."""

    async def handle(
        self, engine: "ChatbotEngine", session: ChatSession, message: str, extracted_data: dict, db: AsyncSession, autopilot: bool
    ) -> dict:
        from app.engine.chatbot_engine import STATE_FIELD_MAP, SKIP_WORDS
        
        state = session.state
        field = STATE_FIELD_MAP.get(state)
        
        if not field:
            logger.warning(f"Could not resolve field for state '{state}', routing dynamically.")
            return await engine._validate_and_route(session, extracted_data, db, autopilot)
            
        answer_clean = message.strip()
        import re
        normalized_answer = re.sub(r'[.,;:!?]+$', '', answer_clean.lower()).strip()
        
        # General check for SKIP words (except reporter_location which has its own mandatory logic)
        if normalized_answer in SKIP_WORDS and field != "reporter_location":
            extracted_data[field] = ""
            extracted_data[f"_explicit_{field}"] = True
            
            session.extracted_data = json.dumps(extracted_data)
            await db.commit()
            
            return await engine._validate_and_route(session, extracted_data, db, autopilot)
            
        # Get processor
        processor = get_field_processor(field)
        
        # Validate and extract
        is_valid, res = await processor.validate_and_extract(message, session, extracted_data, db)
        
        if is_valid:
            # Run hybrid AI+Rule extractor on conversational replies (skip bare digits or skip words)
            if not answer_clean.isdigit() and normalized_answer not in SKIP_WORDS:
                try:
                    from app.services.incident_data_service import extract_incident_data
                    try:
                        history_list = json.loads(session.conversation_history)
                    except Exception:
                        history_list = []
                    # Run extraction with use_llm=True
                    extra_data = await extract_incident_data(message, db, session.user_id, history_list, use_llm=True)
                    
                    # Merge newly extracted fields into res if they are not already filled
                    for k, v in extra_data.items():
                        if k and not k.startswith("_") and v and v != "Nihil" and v != "Belum ada data" and v != "-":
                            # Only merge if the field is not already present or is empty
                            if not res.get(k):
                                res[k] = v
                except Exception as ex:
                    logger.warning(f"Background extraction failed during dialogue turn: {ex}")

            # Save and route to next question
            session.extracted_data = json.dumps(res)
            await db.commit()
            return await engine._validate_and_route(session, res, db, autopilot)
        else:
            # Validation error: return the prompt/warning directly
            if isinstance(res, dict):
                return res
            return {"text": res}
        
