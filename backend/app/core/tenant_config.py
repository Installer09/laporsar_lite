import time
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.settings_models import SystemSetting
from app.core.config import settings as global_settings

logger = logging.getLogger(__name__)

# Cache for pusat (Super Admin) settings to avoid cross-database overhead on every query
_PUSAT_SETTINGS_CACHE: Dict[str, Any] = {
    "settings": {},
    "timestamp": 0.0,
}
_CACHE_TTL_SECONDS = 60.0  # 1 minute TTL

AI_SETTING_KEYS = {
    "ai_llm_provider",
    "ai_llm_model",
    "ai_llm_base_url",
    "ai_llm_api_key",
    "ai_embed_provider",
    "ai_embed_model",
    "ai_embed_api_key",
    "ai_stt_provider",
    "ai_stt_model",
    "ai_stt_api_key",
    "ai_stt_base_url",
    "ollama_host",
}

def invalidate_pusat_settings_cache():
    """Invalidate the cached Super Admin settings when settings are updated."""
    _PUSAT_SETTINGS_CACHE["timestamp"] = 0.0
    _PUSAT_SETTINGS_CACHE["settings"] = {}

async def get_pusat_settings() -> Dict[str, str]:
    """Fetch settings from 'pusat' (Super Admin) tenant database with caching."""
    now = time.time()
    if _PUSAT_SETTINGS_CACHE["settings"] and (now - _PUSAT_SETTINGS_CACHE["timestamp"] < _CACHE_TTL_SECONDS):
        return _PUSAT_SETTINGS_CACHE["settings"]

    try:
        from app.db.session import MasterSessionLocal, get_tenant_sessionmaker
        from app.models.master_models import Tenant

        async with MasterSessionLocal() as db_master:
            res = await db_master.execute(
                select(Tenant).where(Tenant.slug == "pusat", Tenant.is_active == True)
            )
            pusat_tenant = res.scalar_one_or_none()
            if not pusat_tenant:
                return {}

            session_maker = get_tenant_sessionmaker(pusat_tenant.db_url)
            async with session_maker() as session:
                result = await session.execute(select(SystemSetting))
                rows = result.scalars().all()
                settings_dict = {row.key: row.value for row in rows if row.value is not None}
                _PUSAT_SETTINGS_CACHE["settings"] = settings_dict
                _PUSAT_SETTINGS_CACHE["timestamp"] = now
                return settings_dict
    except Exception as e:
        logger.warning(f"Failed to fetch pusat settings for AI inheritance: {e}")
        return _PUSAT_SETTINGS_CACHE.get("settings", {})

class TenantSettings:
    """
    Representation of tenant-specific settings merged with global fallbacks.
    - AI settings: Inherited centrally from Super Admin ('pusat') unless explicitly set locally.
    - Chatbot (Telegram/WhatsApp) and Identity: Strictly isolated per tenant.
    """
    def __init__(self, db_settings: dict, pusat_settings: dict = None, tenant_slug: str = "pusat"):
        self.db_settings = db_settings
        self.pusat_settings = pusat_settings or {}
        self.tenant_slug = tenant_slug

    def __getattr__(self, name: str):
        # Map class attribute to DB key
        db_key = _ATTR_TO_DB_KEY_MAP.get(name)
        if db_key:
            # 1. AI settings: Always inherit from Super Admin (pusat)
            if db_key in AI_SETTING_KEYS:
                # Check local tenant override first
                val = self.db_settings.get(db_key)
                if val is not None and str(val).strip() != "":
                    return val
                # Inherit from Super Admin (pusat)
                pusat_val = self.pusat_settings.get(db_key)
                if pusat_val is not None and str(pusat_val).strip() != "":
                    return pusat_val

            # 2. Tenant-specific settings (Chatbot tokens, groups, identity, etc.):
            # Strictly use tenant's own DB. Do NOT fall back to pusat!
            elif db_key in self.db_settings:
                val = self.db_settings[db_key]
                if val is not None and str(val).strip() != "":
                    return val

        # Fallback to global settings (.env)
        return getattr(global_settings, name, None)

_ATTR_TO_DB_KEY_MAP = {
    "TELEGRAM_BOT_TOKEN": "telegram_token",
    "TELEGRAM_SAR_GROUP_ID": "telegram_group",
    "WHATSAPP_API_TOKEN": "wa_token",
    "WHATSAPP_PHONE_NUMBER_ID": "wa_phone_id",
    "WHATSAPP_SAR_GROUP_ID": "wa_group",
    "WHATSAPP_VERIFY_TOKEN": "wa_verify_token",
    "AI_LLM_PROVIDER": "ai_llm_provider",
    "AI_LLM_MODEL": "ai_llm_model",
    "AI_LLM_BASE_URL": "ai_llm_base_url",
    "AI_LLM_API_KEY": "ai_llm_api_key",
    "AI_EMBED_PROVIDER": "ai_embed_provider",
    "AI_EMBED_MODEL": "ai_embed_model",
    "AI_EMBED_API_KEY": "ai_embed_api_key",
    "AI_STT_PROVIDER": "ai_stt_provider",
    "AI_STT_MODEL": "ai_stt_model",
    "AI_STT_API_KEY": "ai_stt_api_key",
    "AI_STT_BASE_URL": "ai_stt_base_url",
}

async def get_tenant_settings(db: Optional[AsyncSession] = None) -> TenantSettings:
    """
    Fetch all settings from the tenant DB and return a TenantSettings instance.
    Automatically inherits central AI configuration from 'pusat' (Super Admin).
    """
    if db is None:
        pusat_settings = await get_pusat_settings()
        return TenantSettings({}, pusat_settings, tenant_slug="pusat")

    result = await db.execute(select(SystemSetting))
    rows = result.scalars().all()
    db_settings = {row.key: row.value for row in rows if row.value is not None}

    tenant_slug = db.info.get("tenant_slug")
    if not tenant_slug:
        from app.db.session import tenant_context
        tenant_slug = tenant_context.get() or "pusat"

    if tenant_slug == "pusat":
        _PUSAT_SETTINGS_CACHE["settings"] = db_settings
        _PUSAT_SETTINGS_CACHE["timestamp"] = time.time()
        return TenantSettings(db_settings, db_settings, tenant_slug="pusat")
    else:
        pusat_settings = await get_pusat_settings()
        return TenantSettings(db_settings, pusat_settings, tenant_slug=tenant_slug)
