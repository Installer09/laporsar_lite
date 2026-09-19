"""
Classification Service — Auto-match Incident Type to Classification
=====================================================================
Matches the extracted `jenis_kejadian` from a report against the
`classifications` table keywords to determine the formal SAR
classification category.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.settings_models import Classification

logger = logging.getLogger(__name__)


async def match_classification(jenis_kejadian: str, db: AsyncSession) -> Optional[str]:
    """
    Match the incident type string against classification keywords.
    Returns the classification category name (e.g. "LAKA KAPAL"),
    or None if no match found.

    Matching logic:
    - For each classification, check if ANY of its keywords appear
      in the jenis_kejadian string (case-insensitive).
    - Return the first matching classification category.
    """
    if not jenis_kejadian:
        return None

    jenis_lower = jenis_kejadian.lower()

    try:
        result = await db.execute(select(Classification))
        classifications = result.scalars().all()

        for cls in classifications:
            if not cls.keywords:
                continue
            keywords = [kw.strip().lower() for kw in cls.keywords.split(",") if kw.strip()]
            for keyword in keywords:
                if keyword in jenis_lower:
                    logger.info(
                        f"Classification matched: '{jenis_kejadian}' → "
                        f"'{cls.category}' (keyword: '{keyword}')"
                    )
                    return cls.category.upper()

        # No keyword match found — try matching category name directly
        for cls in classifications:
            if cls.category.lower() in jenis_lower:
                return cls.category.upper()

    except Exception as e:
        logger.error(f"Failed to match classification: {e}")

    return None
