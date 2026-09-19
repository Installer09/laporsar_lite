from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.settings_models import SystemSetting
from app.core.config import settings as global_settings

class TenantSettings:
    """
    Representation of tenant-specific settings merged with global fallbacks.
    Reads setting overrides from the tenant's database 'system_settings' table.
    """
    def __init__(self, db_settings: dict):
        self.db_settings = db_settings

    def __getattr__(self, name: str):
        # Map class attribute to DB key
        db_key = _ATTR_TO_DB_KEY_MAP.get(name)
        if db_key and db_key in self.db_settings:
            val = self.db_settings[db_key]
            if val is not None and str(val).strip() != "":
                return val
        
        # Fallback to global settings (.env)
        return getattr(global_settings, name)

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

async def get_tenant_settings(db: AsyncSession) -> TenantSettings:
    """Fetch all settings from the tenant DB and return a TenantSettings instance."""
    result = await db.execute(select(SystemSetting))
    rows = result.scalars().all()
    db_settings = {row.key: row.value for row in rows if row.value is not None}
    return TenantSettings(db_settings)
