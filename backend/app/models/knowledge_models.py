from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, Boolean, Float
from sqlalchemy.sql import func
from app.db.session import Base
import enum


class DictionaryStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SOPDocStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class DictionaryWord(Base):
    __tablename__ = "dictionary_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), unique=True, index=True, nullable=False)
    definition = Column(Text, nullable=True)
    context_example = Column(Text, nullable=True)
    source_message = Column(Text, nullable=True)
    source_user = Column(String(100), nullable=True)
    status = Column(Enum(DictionaryStatus), default=DictionaryStatus.PENDING)
    frequency = Column(Integer, default=1)

    # Categorization
    word_type = Column(String(20), default="GENERAL")   # ABBREVIATION / JARGON / GENERAL
    is_auto_detected = Column(Boolean, default=False)

    # Sinonim & Typo / Slang Mapping
    synonym_target = Column(String(100), nullable=True)
    is_typo_or_slang = Column(Boolean, default=False)
    similarity_score = Column(Float, nullable=True)

    # KB-Driven NER fields — dipakai oleh nlp_extractor dan rule_extractor
    # ner_type:   peran kata dalam pipeline NLP
    #   INCIDENT_KEYWORD  → keyword jenis kejadian SAR (dipetakan ke ner_target)
    #   LOCATION          → nama lokasi/tempat untuk NER lokasi
    #   TIME_MARKER       → kata penanda waktu (tadi pagi, kemarin, dll)
    #   VICTIM_STATUS     → kata status korban (selamat, tenggelam, dalam pencarian)
    # ner_target: nilai yang dikembalikan saat keyword ini cocok
    #   Untuk INCIDENT_KEYWORD: nama kategori, e.g. "KMM", "LAKA KAPAL"
    #   Untuk lainnya: opsional, bisa kosong
    ner_type = Column(String(30), nullable=True, index=True)
    ner_target = Column(String(50), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SOPDocument(Base):
    __tablename__ = "sop_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, default=0)
    doc_type = Column(String(50), default="SOP")  # SOP / Panduan / Referensi
    status = Column(Enum(SOPDocStatus), default=SOPDocStatus.UPLOADED)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
