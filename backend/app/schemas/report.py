from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
import re
import json
from html import escape

class ReportCreate(BaseModel):
    pelapor_nama: str = Field(..., min_length=2, max_length=100, description="Name of the reporter")
    pelapor_nomor: str = Field(..., description="Phone number of the reporter")
    pelapor_lat: Optional[float] = Field(None, ge=-90, le=90)
    pelapor_lng: Optional[float] = Field(None, ge=-180, le=180)
    jenis_kejadian: str = Field(..., max_length=50)
    waktu: str = Field(..., max_length=50)
    lokasi_teks: str = Field(..., max_length=255)
    koordinat_lat: Optional[float] = Field(None, ge=-90, le=90)
    koordinat_lng: Optional[float] = Field(None, ge=-180, le=180)
    radius_pencarian: Optional[float] = Field(2.0, ge=0.0, description="Search radius in kilometers")
    korban: str = Field(..., max_length=255)
    korban_total: Optional[int] = Field(None)
    korban_selamat: Optional[int] = Field(None)
    korban_meninggal: Optional[int] = Field(None)
    korban_hilang: Optional[int] = Field(None)
    data_korban: Optional[Any] = Field(None)
    metadata_kejadian: Optional[Any] = Field(None)
    unsur_alut: Optional[Any] = Field(None)

    kronologi: str = Field(...)
    eviden_id: Optional[str] = Field(None, max_length=100)

    @field_validator("pelapor_nomor")
    @classmethod
    def validate_phone(cls, v):
        # Strict Zero-Trust validation for phone number
        if not v or not re.match(r'^[\+\d\-\s]{8,20}$', v):
            raise ValueError("Nomor telepon tidak valid")
        return v
        
    @field_validator(
        "kronologi", "pelapor_nama", "lokasi_teks", "jenis_kejadian", "waktu", 
        "korban", "eviden_id"
    )
    @classmethod
    def sanitize_text(cls, v):
        # Zero-Trust: Escape HTML to prevent XSS if data is ever rendered raw
        if v is None:
            return v
        return escape(v.strip())

    @field_validator("unsur_alut", "data_korban", "metadata_kejadian", mode="before")
    @classmethod
    def parse_json_string(cls, v):
        if isinstance(v, str) and v.strip():
            try:
                return json.loads(v)
            except Exception:
                return v
        return v

class ReportResponse(ReportCreate):
    id: int
    no_laporan: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    gmaps_link: Optional[str] = None
    info_awal_text: Optional[str] = Field(None)

    model_config = ConfigDict(from_attributes=True)

class ReportUpdate(BaseModel):
    pelapor_nama: Optional[str] = Field(None, min_length=2, max_length=100)
    pelapor_nomor: Optional[str] = Field(None)
    pelapor_lat: Optional[float] = Field(None, ge=-90, le=90)
    pelapor_lng: Optional[float] = Field(None, ge=-180, le=180)
    jenis_kejadian: Optional[str] = Field(None, max_length=50)
    waktu: Optional[str] = Field(None, max_length=50)
    lokasi_teks: Optional[str] = Field(None, max_length=255)
    koordinat_lat: Optional[float] = Field(None, ge=-90, le=90)
    koordinat_lng: Optional[float] = Field(None, ge=-180, le=180)
    radius_pencarian: Optional[float] = Field(None, ge=0.0)
    korban: Optional[str] = Field(None, max_length=255)
    korban_total: Optional[int] = Field(None)
    korban_selamat: Optional[int] = Field(None)
    korban_meninggal: Optional[int] = Field(None)
    korban_hilang: Optional[int] = Field(None)
    data_korban: Optional[Any] = Field(None)
    metadata_kejadian: Optional[Any] = Field(None)
    unsur_alut: Optional[Any] = Field(None)
    kronologi: Optional[str] = Field(None)
    status: Optional[str] = Field(None)
    info_awal_text: Optional[str] = Field(None)

    @field_validator(
        "pelapor_nama", "lokasi_teks", "jenis_kejadian", "waktu", 
        "korban", "kronologi"
    )
    @classmethod
    def sanitize_text(cls, v):
        if v is None:
            return v
        return escape(v.strip())
class BroadcastPayload(BaseModel):
    text: str = Field(..., min_length=1)

class ChatMessagePayload(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=50)
    message: str = Field(..., min_length=1, max_length=2000)
    channel: Optional[str] = Field("web", max_length=20)  # "telegram" / "whatsapp" / "web"

