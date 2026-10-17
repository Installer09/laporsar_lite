from pydantic import BaseModel, Field, field_validator, ConfigDict, AliasChoices, computed_field
from typing import Optional, Dict, Any
from datetime import datetime
import re
import json
from html import escape

class ReportCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reporter_name: str = Field(
        ..., min_length=2, max_length=100, 
        validation_alias=AliasChoices("reporter_name", "pelapor_nama"),
        description="Name of the reporter"
    )
    reporter_phone: str = Field(
        ..., 
        validation_alias=AliasChoices("reporter_phone", "pelapor_nomor"),
        description="Phone number of the reporter"
    )
    reporter_lat: Optional[float] = Field(None, ge=-90, le=90, validation_alias=AliasChoices("reporter_lat", "pelapor_lat"))
    reporter_lng: Optional[float] = Field(None, ge=-180, le=180, validation_alias=AliasChoices("reporter_lng", "pelapor_lng"))
    
    incident_type: str = Field(..., max_length=50, validation_alias=AliasChoices("incident_type", "jenis_kejadian"))
    incident_time: str = Field(..., max_length=50, validation_alias=AliasChoices("incident_time", "waktu"))
    location_text: str = Field(..., max_length=255, validation_alias=AliasChoices("location_text", "lokasi_teks"))
    
    latitude: Optional[float] = Field(None, ge=-90, le=90, validation_alias=AliasChoices("latitude", "koordinat_lat"))
    longitude: Optional[float] = Field(None, ge=-180, le=180, validation_alias=AliasChoices("longitude", "koordinat_lng"))
    search_radius_km: Optional[float] = Field(2.0, ge=0.0, validation_alias=AliasChoices("search_radius_km", "radius_pencarian"))
    
    victim_summary: str = Field(..., max_length=255, validation_alias=AliasChoices("victim_summary", "korban"))
    total_victims: Optional[int] = Field(None, validation_alias=AliasChoices("total_victims", "korban_total"))
    survived_victims: Optional[int] = Field(None, validation_alias=AliasChoices("survived_victims", "korban_selamat"))
    deceased_victims: Optional[int] = Field(None, validation_alias=AliasChoices("deceased_victims", "korban_meninggal"))
    missing_victims: Optional[int] = Field(None, validation_alias=AliasChoices("missing_victims", "korban_hilang"))
    victim_data: Optional[Any] = Field(None, validation_alias=AliasChoices("victim_data", "data_korban"))
    incident_metadata: Optional[Any] = Field(None, validation_alias=AliasChoices("incident_metadata", "metadata_kejadian"))
    resources_deployed: Optional[Any] = Field(None, validation_alias=AliasChoices("resources_deployed", "unsur_alut"))

    chronology: str = Field(..., validation_alias=AliasChoices("chronology", "kronologi"))
    evidence_id: Optional[str] = Field(None, max_length=100, validation_alias=AliasChoices("evidence_id", "eviden_id"))

    @field_validator("reporter_phone")
    @classmethod
    def validate_phone(cls, v):
        if not v or not re.match(r'^[\+\d\-\s]{8,20}$', v):
            raise ValueError("Nomor telepon tidak valid")
        return v
        
    @field_validator(
        "chronology", "reporter_name", "location_text", "incident_type", "incident_time", 
        "victim_summary", "evidence_id"
    )
    @classmethod
    def sanitize_text(cls, v):
        if v is None:
            return v
        return escape(v.strip())

    @field_validator("resources_deployed", "victim_data", "incident_metadata", mode="before")
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
    report_number: str = Field(..., validation_alias=AliasChoices("report_number", "no_laporan"))
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    gmaps_link: Optional[str] = None
    initial_report_text: Optional[str] = Field(None, validation_alias=AliasChoices("initial_report_text", "info_awal_text"))

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # ── Computed Fields for Backward Compatibility in API Response ──
    @computed_field
    def no_laporan(self) -> str:
        return self.report_number

    @computed_field
    def pelapor_nama(self) -> str:
        return self.reporter_name

    @computed_field
    def pelapor_nomor(self) -> str:
        return self.reporter_phone

    @computed_field
    def jenis_kejadian(self) -> str:
        return self.incident_type

    @computed_field
    def waktu(self) -> str:
        return self.incident_time

    @computed_field
    def lokasi_teks(self) -> str:
        return self.location_text

    @computed_field
    def koordinat_lat(self) -> Optional[float]:
        return self.latitude

    @computed_field
    def koordinat_lng(self) -> Optional[float]:
        return self.longitude

    @computed_field
    def korban(self) -> str:
        return self.victim_summary

    @computed_field
    def korban_total(self) -> Optional[int]:
        return self.total_victims

    @computed_field
    def korban_selamat(self) -> Optional[int]:
        return self.survived_victims

    @computed_field
    def korban_meninggal(self) -> Optional[int]:
        return self.deceased_victims

    @computed_field
    def korban_hilang(self) -> Optional[int]:
        return self.missing_victims

    @computed_field
    def data_korban(self) -> Optional[Any]:
        return self.victim_data

    @computed_field
    def metadata_kejadian(self) -> Optional[Any]:
        return self.incident_metadata

    @computed_field
    def unsur_alut(self) -> Optional[Any]:
        return self.resources_deployed

    @computed_field
    def kronologi(self) -> str:
        return self.chronology

    @computed_field
    def eviden_id(self) -> Optional[str]:
        return self.evidence_id

    @computed_field
    def info_awal_text(self) -> Optional[str]:
        return self.initial_report_text


class ReportUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reporter_name: Optional[str] = Field(None, min_length=2, max_length=100, validation_alias=AliasChoices("reporter_name", "pelapor_nama"))
    reporter_phone: Optional[str] = Field(None, validation_alias=AliasChoices("reporter_phone", "pelapor_nomor"))
    reporter_lat: Optional[float] = Field(None, ge=-90, le=90, validation_alias=AliasChoices("reporter_lat", "pelapor_lat"))
    reporter_lng: Optional[float] = Field(None, ge=-180, le=180, validation_alias=AliasChoices("reporter_lng", "pelapor_lng"))
    incident_type: Optional[str] = Field(None, max_length=50, validation_alias=AliasChoices("incident_type", "jenis_kejadian"))
    incident_time: Optional[str] = Field(None, max_length=50, validation_alias=AliasChoices("incident_time", "waktu"))
    location_text: Optional[str] = Field(None, max_length=255, validation_alias=AliasChoices("location_text", "lokasi_teks"))
    latitude: Optional[float] = Field(None, ge=-90, le=90, validation_alias=AliasChoices("latitude", "koordinat_lat"))
    longitude: Optional[float] = Field(None, ge=-180, le=180, validation_alias=AliasChoices("longitude", "koordinat_lng"))
    search_radius_km: Optional[float] = Field(None, ge=0.0, validation_alias=AliasChoices("search_radius_km", "radius_pencarian"))
    victim_summary: Optional[str] = Field(None, max_length=255, validation_alias=AliasChoices("victim_summary", "korban"))
    total_victims: Optional[int] = Field(None, validation_alias=AliasChoices("total_victims", "korban_total"))
    survived_victims: Optional[int] = Field(None, validation_alias=AliasChoices("survived_victims", "korban_selamat"))
    deceased_victims: Optional[int] = Field(None, validation_alias=AliasChoices("deceased_victims", "korban_meninggal"))
    missing_victims: Optional[int] = Field(None, validation_alias=AliasChoices("missing_victims", "korban_hilang"))
    victim_data: Optional[Any] = Field(None, validation_alias=AliasChoices("victim_data", "data_korban"))
    incident_metadata: Optional[Any] = Field(None, validation_alias=AliasChoices("incident_metadata", "metadata_kejadian"))
    resources_deployed: Optional[Any] = Field(None, validation_alias=AliasChoices("resources_deployed", "unsur_alut"))
    chronology: Optional[str] = Field(None, validation_alias=AliasChoices("chronology", "kronologi"))
    status: Optional[str] = Field(None)
    initial_report_text: Optional[str] = Field(None, validation_alias=AliasChoices("initial_report_text", "info_awal_text"))

    @field_validator(
        "reporter_name", "location_text", "incident_type", "incident_time", 
        "victim_summary", "chronology"
    )
    @classmethod
    def sanitize_text(cls, v):
        if v is None:
            return v
        return escape(v.strip())

class BroadcastPayload(BaseModel):
    text: str = Field(..., min_length=1)

