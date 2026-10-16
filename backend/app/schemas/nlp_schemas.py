from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict, AliasChoices, computed_field


class VictimDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("name", "nama"),
        description="Victim name, e.g., Budi, Nelayan 1."
    )
    age: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("age", "umur"),
        description="Victim age in years, e.g., 25, 40 tahun."
    )
    gender: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("gender", "jenis_kelamin"),
        description="Laki-laki or Perempuan."
    )
    address: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("address", "alamat"),
        description="Victim address."
    )
    phone: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("phone", "no_hp"),
        description="Victim phone number, e.g., 08123456789."
    )
    condition: Optional[str] = Field(
        default="Dalam Pencarian",
        validation_alias=AliasChoices("condition", "kondisi"),
        description="Victim condition: Selamat, Meninggal Dunia, or Dalam Pencarian."
    )

    @computed_field
    def nama(self) -> Optional[str]:
        return self.name

    @computed_field
    def umur(self) -> Optional[str]:
        return self.age

    @computed_field
    def jenis_kelamin(self) -> Optional[str]:
        return self.gender

    @computed_field
    def alamat(self) -> Optional[str]:
        return self.address

    @computed_field
    def no_hp(self) -> Optional[str]:
        return self.phone

    @computed_field
    def kondisi(self) -> Optional[str]:
        return self.condition


# Backward compatibility alias
KorbanDetail = VictimDetail


class SARExtractedFields(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    incident_type: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("incident_type", "jenis_kejadian"),
        description="SAR incident category (e.g., Laka Kapal, KMM)"
    )
    sub_incident_type: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("sub_incident_type", "sub_jenis_kejadian"),
        description="Specific sub-incident type (e.g., Pompong Mati Mesin)"
    )
    incident_time: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("incident_time", "waktu", "waktu_kejadian"),
        description="Specific time of incident (date/hour)"
    )
    location_text: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("location_text", "lokasi_teks", "lokasi"),
        description="Place name or incident location description"
    )
    victim_summary: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("victim_summary", "korban", "jumlah_korban"),
        description="Summary of victim count and condition"
    )
    victim_condition: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("victim_condition", "kondisi_korban"),
        description="Condition of victims or incident status"
    )
    victim_data: Optional[List[VictimDetail]] = Field(
        default=[],
        validation_alias=AliasChoices("victim_data", "data_korban"),
        description="Detailed identity list for each victim"
    )
    uses_vessel: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("uses_vessel", "pakai_kapal"),
        description="Whether a vessel/boat is involved (Ya/Tidak)"
    )
    vessel_data: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("vessel_data", "data_kapal"),
        description="Vessel type, name, or characteristics"
    )
    reporter_relation: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("reporter_relation", "pelapor_hubungan", "hubungan_pelapor"),
        description="Relationship between reporter and victim (e.g., Keluarga Korban (Kakak))"
    )
    coordinates: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("coordinates", "koordinat"),
        description="GPS coordinates if available"
    )
    chronology: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("chronology", "kronologi", "kronologi_singkat"),
        description="Short chronology or description of the incident"
    )

    @field_validator('*', mode='before')
    @classmethod
    def clean_unknown(cls, v: Any, info):
        if info.field_name not in ('victim_data', 'data_korban') and isinstance(v, (list, dict)):
            v = str(v)
        if info.field_name not in ('victim_data', 'data_korban') and isinstance(v, (bool, int, float)):
            v = str(v)

        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ["belum diketahui", "tidak diketahui", "unknown", "none", "null", "-", "n/a", "na", "tbd"]:
                return None
            return v.strip() if v_lower != "" else v
        return v

    # ── Backward Compatibility Computed Fields ──
    @computed_field
    def jenis_kejadian(self) -> Optional[str]:
        return self.incident_type

    @computed_field
    def sub_jenis_kejadian(self) -> Optional[str]:
        return self.sub_incident_type

    @computed_field
    def waktu(self) -> Optional[str]:
        return self.incident_time

    @computed_field
    def lokasi_teks(self) -> Optional[str]:
        return self.location_text

    @computed_field
    def korban(self) -> Optional[str]:
        return self.victim_summary

    @computed_field
    def kondisi_korban(self) -> Optional[str]:
        return self.victim_condition

    @computed_field
    def data_korban(self) -> Optional[List[VictimDetail]]:
        return self.victim_data

    @computed_field
    def pakai_kapal(self) -> Optional[str]:
        return self.uses_vessel

    @computed_field
    def data_kapal(self) -> Optional[str]:
        return self.vessel_data

    @computed_field
    def pelapor_hubungan(self) -> Optional[str]:
        return self.reporter_relation

    @computed_field
    def koordinat(self) -> Optional[str]:
        return self.coordinates

    @computed_field
    def kronologi(self) -> Optional[str]:
        return self.chronology

