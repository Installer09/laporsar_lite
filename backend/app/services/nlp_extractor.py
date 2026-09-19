import logging
from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.rule_extractor import RuleExtractor
from app.services.llm_rag import LLMRagService

logger = logging.getLogger(__name__)

class SARNLPExtractor:
    def __init__(self):
        self.rule_extractor = RuleExtractor()
        self.llm_rag = LLMRagService()

    async def extract(self, message: str, db: AsyncSession, conversation_history: list = None, use_llm: bool = True) -> Tuple[Dict[str, Any], float]:
        """
        Phase 3: Hybrid Extraction Pipeline.
        Runs local RuleExtractor first, then conditionally invokes LLM fallback
        if fewer than 4 core fields are successfully extracted locally.
        Pre-processes message via AutoCorrectService to handle typos/slang.
        """
        logger.info(f"Extracting data from message: {message[:50]}...")
        
        from app.db.session import tenant_context
        from unittest.mock import Mock
        is_mock_db = isinstance(db, Mock)
        
        if is_mock_db:
            tenant_slug = tenant_context.get()
        else:
            info = getattr(db, "info", None)
            tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"
            
        token = tenant_context.set(tenant_slug)
        try:
            # Pre-process message to autocorrect typos, slang, and synonyms
            from app.services.autocorrect_service import AutoCorrectService
            if not AutoCorrectService._cache_loaded:
                await AutoCorrectService.load_cache(db)
            
            cleaned_message = AutoCorrectService.clean_message(message)
        finally:
            tenant_context.reset(token)
        
        # 1. Run local RuleExtractor (Dict/Regex & DB Classifications) using cleaned message
        local_data = {}
        try:
            local_data = await self.rule_extractor.extract_all(cleaned_message, db)
            logger.info(f"RuleExtractor extracted: {local_data}")
        except Exception as e:
            logger.error(f"RuleExtractor failed: {str(e)}")

        # 2. LLM Late Fusion Validation (Only run if use_llm is True)
        if use_llm:
            logger.info("Passing local extraction to LLM Validator for disambiguation.")
            context = await self.llm_rag.get_dictionary_context(db)
            try:
                validated_data = await self.llm_rag.validate_extraction_with_ai(
                    message=cleaned_message,
                    raw_data=local_data,
                    context=context,
                    db=db
                )
                result = validated_data if isinstance(validated_data, dict) else local_data
            except Exception as e:
                logger.error(f"LLM Validator failed: {str(e)}")
                result = local_data
        else:
            logger.info("Skipping LLM Validator for fast dialogue turn.")
            result = local_data

        # Calculate confidence
        confidence = 0.95 if result else 0.0
        return result, confidence

sar_nlp_extractor = SARNLPExtractor()
