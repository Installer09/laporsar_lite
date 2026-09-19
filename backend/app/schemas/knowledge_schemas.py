from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from html import escape

def sanitize_html(v):
    if v is None:
        return v
    return escape(v.strip()) if isinstance(v, str) else v

from datetime import datetime


# --- Dictionary Schemas ---

class DictionaryWordCreate(BaseModel):
    word: str = Field(..., min_length=1, max_length=100, description="Kata/istilah yang tidak dikenal")
    definition: Optional[str] = Field(None, description="Definisi/arti kata")
    context_example: Optional[str] = Field(None, description="Contoh penggunaan dalam kalimat")
    word_type: Optional[str] = Field("GENERAL", description="Tipe kata: ABBREVIATION / JARGON / GENERAL")
    ner_type: Optional[str] = Field(None, description="Peran NER: INCIDENT_KEYWORD / LOCATION / TIME_MARKER / VICTIM_STATUS")
    ner_target: Optional[str] = Field(None, description="Target kategori, e.g. 'KMM', 'LAKA KAPAL' (untuk INCIDENT_KEYWORD)")
    synonym_target: Optional[str] = Field(None, description="Kata standar tujuan pemetaan")
    is_typo_or_slang: Optional[bool] = Field(False, description="Flag penanda kata salah ketik atau slang")
    similarity_score: Optional[float] = Field(None, description="Nilai kemiripan string")
    is_global: Optional[bool] = Field(False, description="Simpan sebagai Kamus Dasar Nasional (Hanya Admin Pusat/Super Admin)")

    @field_validator("word", "definition", "context_example")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)


class DictionaryWordUpdate(BaseModel):
    definition: Optional[str] = None
    context_example: Optional[str] = None
    status: Optional[str] = None  # PENDING, APPROVED, REJECTED
    word_type: Optional[str] = None
    ner_type: Optional[str] = None
    ner_target: Optional[str] = None
    synonym_target: Optional[str] = None
    is_typo_or_slang: Optional[bool] = None
    similarity_score: Optional[float] = None

    @field_validator("definition", "context_example")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)


class DictionaryWordResponse(BaseModel):
    id: int
    word: str
    definition: Optional[str] = None
    context_example: Optional[str] = None
    source_message: Optional[str] = None
    source_user: Optional[str] = None
    status: str
    frequency: Optional[int] = 1
    word_type: Optional[str] = "GENERAL"
    is_auto_detected: Optional[bool] = False
    ner_type: Optional[str] = None
    ner_target: Optional[str] = None
    synonym_target: Optional[str] = None
    is_typo_or_slang: Optional[bool] = False
    similarity_score: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_global: bool = False

    model_config = ConfigDict(from_attributes=True)

    @field_validator("frequency", mode="before")
    @classmethod
    def default_frequency(cls, v):
        return v if v is not None else 1


class DictionaryBulkAction(BaseModel):
    ids: list[int]
    action: str  # "approve", "reject", "delete"


# --- SOP Document Schemas ---

class SOPDocumentResponse(BaseModel):
    id: int
    title: str
    filename: str
    file_size: int
    doc_type: str
    status: str
    created_at: Optional[datetime] = None
    is_global: bool = False

    model_config = ConfigDict(from_attributes=True)
