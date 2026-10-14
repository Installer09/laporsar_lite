import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.knowledge_models import DictionaryWord, DictionaryStatus
from app.db.session import (
    tenant_context,
    TenantPartitionedCache,
    MultitenantServiceMeta,
)

logger = logging.getLogger(__name__)

class AutoCorrectService(metaclass=MultitenantServiceMeta):
    """
    Service to handle auto-correction of reporter messages.
    Replaces approved typos, slang, and informal synonyms with standard SAR vocabulary
    prior to running the extraction pipeline.
    """
    _synonym_mappings = TenantPartitionedCache()

    @classmethod
    async def load_cache(cls, db: AsyncSession):
        """
        Pre-warm autocorrect synonym mappings from database.
        Loads all APPROVED words with a valid synonym_target by merging
        global approved synonyms (Master DB) and regional approved synonyms (Tenant DB).
        """
        info = getattr(db, "info", None)
        tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else (tenant_context.get() or "global")
        
        # 1. Fetch approved synonyms from Master DB
        master_synonyms = []
        try:
            if tenant_slug == "global":
                result = await db.execute(
                    select(DictionaryWord).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED,
                        DictionaryWord.synonym_target != None,
                        DictionaryWord.synonym_target != ""
                    )
                )
                master_synonyms = result.scalars().all()
            else:
                from app.db.session import MasterSessionLocal
                async with MasterSessionLocal() as master_db:
                    result = await master_db.execute(
                        select(DictionaryWord).where(
                            DictionaryWord.status == DictionaryStatus.APPROVED,
                            DictionaryWord.synonym_target != None,
                            DictionaryWord.synonym_target != ""
                        )
                    )
                    master_synonyms = result.scalars().all()
        except Exception as e:
            logger.warning(f"[AutoCorrectService] Failed to load global synonyms: {e}")

        # 2. Fetch approved synonyms from Tenant DB (if not global)
        tenant_synonyms = []
        if tenant_slug != "global":
            try:
                result = await db.execute(
                    select(DictionaryWord).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED,
                        DictionaryWord.synonym_target != None,
                        DictionaryWord.synonym_target != ""
                    )
                )
                tenant_synonyms = result.scalars().all()
            except Exception as e:
                logger.warning(f"[AutoCorrectService] Failed to load tenant synonyms: {e}")

        # 3. Merge them. Tenant synonyms override master synonyms.
        mappings = {}
        for w in master_synonyms:
            if w.word and w.synonym_target:
                mappings[w.word.lower().strip()] = w.synonym_target.strip()
        for w in tenant_synonyms:
            if w.word and w.synonym_target:
                mappings[w.word.lower().strip()] = w.synonym_target.strip()

        cls._synonym_mappings[tenant_slug] = mappings
        cls._cache_loaded[tenant_slug] = True
        logger.info(f"[AutoCorrectService] Cache loaded for tenant '{tenant_slug}' with {len(mappings)} synonym mappings.")

    @classmethod
    def clean_message(cls, message: str) -> str:
        """
        Replace known typos/slangs with their standard approved synonym targets.
        Uses word boundaries to prevent partial word replacements.
        """
        if not message or not cls._synonym_mappings:
            return message

        # Extract sorted keys by length descending to match longer phrases first
        sorted_keys = sorted(cls._synonym_mappings.keys(), key=len, reverse=True)
        if not sorted_keys:
            return message

        # Compile regex with word boundaries
        # Note: we use boundary checking, but handle special characters if any
        pattern = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in sorted_keys) + r')\b',
            re.IGNORECASE
        )

        def replace_match(match):
            matched_text = match.group(1).lower().strip()
            # Return target synonym, preserving surrounding case by simply inserting target
            return cls._synonym_mappings.get(matched_text, match.group(0))

        cleaned = pattern.sub(replace_match, message)
        
        # If any changes were made, log it
        if cleaned != message:
            logger.info(f"[AutoCorrectService] Cleaned message: '{message}' -> '{cleaned}'")
            
        return cleaned

# Singleton instance
autocorrect_service = AutoCorrectService()
