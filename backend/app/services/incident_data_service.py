import logging
import json
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.nlp_extractor import sar_nlp_extractor
from app.services.term_extractor import extract_terms, resolve_and_save_terms

logger = logging.getLogger(__name__)

async def _detect_unknown_terms_side_effect(
    message: str,
    user_id: str,
    db_url: str,
) -> None:
    """
    Find unrecognized words/jargon via LLM and save them as PENDING.
    This is a non-blocking side-effect.
    """
    try:
        if not isinstance(db_url, str):
            logger.info("[KB Learning] Skipping background learning task for non-string DB URL.")
            return

        from app.services.llm_rag import LLMRagService
        from app.db.session import get_tenant_sessionmaker
        
        llm_rag = LLMRagService()
        unrecognized = await llm_rag.detect_unknown_words(message)
        if unrecognized:
            logger.info(f"[KB Learning] Found {len(unrecognized)} unrecognized terms via LLM")
            session_maker = get_tenant_sessionmaker(db_url)
            async with session_maker() as bg_db:
                await llm_rag.save_unknown_words(
                    unrecognized[:5], message, user_id, bg_db, word_type="JARGON"
                )
    except Exception as e:
        logger.warning(f"[KB Learning] Unknown term detection non-critical: {e}")

async def extract_incident_data(
    message: str, 
    db: AsyncSession, 
    user_id: str,
    conversation_history: list = None,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Main extraction pipeline for SAR-BOT V3.
    """
    # 1. Run Hybrid Schema Extraction (Local Regex + DB Classifications + LLM Fallback)
    extracted_data, confidence = await sar_nlp_extractor.extract(message, db, conversation_history, use_llm=use_llm)
    
    # 2. Side Effect: Deterministic Unknown/Colloquial Word Logging (PENDING for Operator Review)
    try:
        from app.services.autocorrect_service import AutoCorrectService
        unknown_terms = await AutoCorrectService.detect_and_log_unknown_terms(
            message=message, db=db, user_id=user_id
        )
        if unknown_terms and isinstance(extracted_data, dict):
            existing = extracted_data.get("unknown_terms", [])
            merged_terms = list(dict.fromkeys((existing or []) + unknown_terms))
            extracted_data["unknown_terms"] = merged_terms
    except Exception as e:
        logger.warning(f"Deterministic unknown word logging failed: {str(e)}")

    # 3. Side Effect: Regex KB Learning (Detect uppercase abbreviations)
    try:
        detected_terms = extract_terms(message)
        if detected_terms:
            await resolve_and_save_terms(detected_terms, message, user_id, db)
    except Exception as e:
        logger.error(f"KB Learning failed: {str(e)}")

    # 4. Side Effect: LLM KB Learning (Only if message is long enough and LLM was active)
    if use_llm and len(message.strip()) > 30:
        import asyncio
        try:
            db_url = db.bind.url.render_as_string(hide_password=False)
            asyncio.create_task(_detect_unknown_terms_side_effect(message, user_id, db_url))
        except Exception as e:
            logger.warning(f"[KB Learning] Failed to initiate background vocabulary learning: {e}")
        
    return extracted_data
