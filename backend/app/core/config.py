from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Lapor SAR API"
    VERSION: str = "3.1.0-lite"
    
    # Security
    SECRET_KEY: str = "laporsar-dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Global Super Admin Fallback (platform-wide access, non-tenant)
    # Disabled by default for production security. Can be enabled via .env during local development.
    DEV_SUPERADMIN_ENABLED: bool = False
    DEV_SUPERADMIN_USERNAME: str = "superadmin"
    DEV_SUPERADMIN_PASSWORD: str = "superadmin"

    # Tenant Admin Fallback (scoped to Basarnas Pusat Command Center)
    # Disabled by default for production security. Can be enabled via .env during local development.
    DEV_ADMIN_ENABLED: bool = False
    DEV_ADMIN_USERNAME: str = "admin"
    DEV_ADMIN_PASSWORD: str = "admin"
    
    # Database & Cache
    DATABASE_URL: str = "postgresql+asyncpg://laporsar_admin:laporsar_admin@db:5432/laporsar_master"
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Integrations — Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_SAR_GROUP_ID: str = ""  # Numeric ID of the SAR command group
    TELEGRAM_SECRET_TOKEN: str = ""  # Secret token sent by Telegram in header

    # Integrations — WhatsApp (Meta Cloud API)
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""  # Phone Number ID from Meta Business
    WHATSAPP_VERIFY_TOKEN: str = "LAPORSAR_VERIFY_TOKEN"  # Webhook verification token
    WHATSAPP_APP_SECRET: str = ""  # Meta App Secret for validating webhook signature
    WHATSAPP_SAR_GROUP_ID: str = ""  # WA Group ID / phone number for SAR report forwarding
    
    # AI Services — LLM Engine (Default: Gemini Flash or Groq)
    AI_LLM_PROVIDER: str = "gemini"           # gemini | groq | openai | ollama | claude
    AI_LLM_MODEL: str = "gemini-1.5-flash"    # Model name per provider
    AI_LLM_BASE_URL: str = ""                 # Base URL (for custom/local endpoint if needed)
    AI_LLM_API_KEY: str = ""                   # API key for cloud providers

    # AI Services — Embedding Engine (RAG)
    AI_EMBED_PROVIDER: str = "gemini"          # gemini | openai | ollama
    AI_EMBED_MODEL: str = "text-embedding-004" # Embedding model name
    AI_EMBED_API_KEY: str = ""                 # API key for cloud embedding

    # AI Services — Audio/Whisper Engine (STT) (Default: Groq Whisper for sub-second latency)
    AI_STT_PROVIDER: str = "groq"              # groq | openai | gemini | ollama | local_whisper
    AI_STT_MODEL: str = "whisper-large-v3"     # STT model name
    AI_STT_API_KEY: str = ""                   # API key for cloud STT
    AI_STT_BASE_URL: str = ""                  # Optional base URL override
    
    # Local Storage Configuration (Replacing MinIO for lightweight local prototype)
    STORAGE_TYPE: str = "local"                # "local"
    LOCAL_STORAGE_DIR: str = "uploads"         # Base folder relative to backend root or absolute
    
    # Weather is handled via Open-Meteo API (No API key required)
    
    # SMTP Email Settings
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@laporsar.id"
    EMAILS_FROM_NAME: str = "Lapor SAR System"
    FRONTEND_URL: str = "http://localhost:3000"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def reload(self):
        from dotenv import dotenv_values
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        root_env = os.path.join(os.path.dirname(base_dir), '.env')
        backend_env = os.path.join(base_dir, '.env')
        env_path = root_env if os.path.exists(root_env) else backend_env

        # Critical security and connection keys that must never be dynamically mutated at runtime
        PROTECTED_KEYS = {
            "SECRET_KEY", 
            "ALGORITHM", 
            "DATABASE_URL", 
            "REDIS_URL", 
            "DEV_ADMIN_USERNAME", 
            "DEV_ADMIN_PASSWORD",
            "DEV_SUPERADMIN_USERNAME",
            "DEV_SUPERADMIN_PASSWORD",
            "ACCESS_TOKEN_EXPIRE_MINUTES"
        }

        if os.path.exists(env_path):
            env_vals = dotenv_values(env_path)
            for k, v in env_vals.items():
                if k not in PROTECTED_KEYS and hasattr(self, k):
                    setattr(self, k, v)

settings = Settings()
