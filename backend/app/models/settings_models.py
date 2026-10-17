from sqlalchemy import Column, Integer, String, Float, Text, Enum, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base
import enum

class SettingKey(str, enum.Enum):
    TELEGRAM_TOKEN = "telegram_token"
    TELEGRAM_GROUP = "telegram_group"
    WA_TOKEN = "wa_token"
    WA_GROUP = "wa_group"
    # AI Engine — LLM
    AI_LLM_PROVIDER = "ai_llm_provider"
    AI_LLM_MODEL = "ai_llm_model"
    AI_LLM_BASE_URL = "ai_llm_base_url"
    AI_LLM_API_KEY = "ai_llm_api_key"
    # AI Engine — Embedding (RAG)
    AI_EMBED_PROVIDER = "ai_embed_provider"
    AI_EMBED_MODEL = "ai_embed_model"
    AI_EMBED_API_KEY = "ai_embed_api_key"
    AI_RAG_URL = "ai_rag_url"
    # AI Engine — STT (Audio Whisper)
    AI_STT_PROVIDER = "ai_stt_provider"
    AI_STT_MODEL = "ai_stt_model"
    AI_STT_API_KEY = "ai_stt_api_key"
    AI_STT_BASE_URL = "ai_stt_base_url"
    # Format
    INFO_FORMAT = "info_format"
    INFO_FORMAT_TEMPLATE = "info_format_template"
    # Operasional
    WILAYAH_KERJA = "wilayah_kerja"
    FALLBACK_PHONE = "fallback_phone"


class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text, nullable=True)

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String) # Kantor, Pos, Unit
    lat = Column(Float)
    lng = Column(Float)
    address = Column(Text)
    unsur = Column(Text, nullable=True) # Daftar personil/tim
    alut = Column(Text, nullable=True)  # Daftar peralatan/alut
    icon = Column(String(50), nullable=True)

class Classification(Base):
    __tablename__ = "classifications"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True)
    keywords = Column(Text) # Comma separated keywords
    sop_document_id = Column(Integer, ForeignKey("sop_documents.id"), nullable=True)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String, nullable=True)
    nip = Column(String(50), nullable=True)
    jabatan = Column(String(100), nullable=True)
    role = Column(String) # Super Admin, Operator, User
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    reset_token = Column(String, nullable=True)
    photo_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class FormatVariable(Base):
    __tablename__ = "format_variables"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    description = Column(String)
    group = Column(String)
    value = Column(Text, nullable=True)

class AlutPalsarTemplate(Base):
    __tablename__ = "alut_palsar_templates"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True) # E.g., 'KMM', 'Laka Air', 'Gunung'
    recommended_alut = Column(Text) # Comma-separated list of recommended equipment


class WidgetIntegrationRequest(Base):
    __tablename__ = "widget_integration_requests"
    id = Column(Integer, primary_key=True, index=True)
    partner_name = Column(String, index=True)
    website_url = Column(String, index=True)
    official_email = Column(String)
    official_phone = Column(String)
    api_key = Column(String, unique=True, index=True, nullable=True)
    status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
