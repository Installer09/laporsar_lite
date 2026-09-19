from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

class KorbanDetail(BaseModel):
    nama: Optional[str] = Field(default=None, description="Nama korban, contoh: Budi, Nelayan 1.")
    umur: Optional[str] = Field(default=None, description="Umur korban dalam tahun, contoh: 25, 40 tahun.")
    jenis_kelamin: Optional[str] = Field(default=None, description="Laki-laki atau Perempuan.")
    alamat: Optional[str] = Field(default=None, description="Alamat korban.")
    no_hp: Optional[str] = Field(default=None, description="Nomor HP atau nomor telepon korban, contoh: 08123456789.")
    kondisi: Optional[str] = Field(default="Dalam Pencarian", description="Kondisi korban: Selamat, Meninggal Dunia, atau Dalam Pencarian.")

class SARExtractedFields(BaseModel):
    jenis_kejadian: Optional[str] = Field(default=None, description="Kategori kejadian SAR (misal: LAKA KAPAL, KONDISI MEMBAHAYAKAN MANUSIA)")
    waktu: Optional[str] = Field(default=None, description="Waktu spesifik kejadian (tanggal/jam)")
    lokasi_teks: Optional[str] = Field(default=None, description="Nama tempat atau deskripsi lokasi kejadian")
    korban: Optional[str] = Field(default=None, description="Ringkasan jumlah dan kondisi korban secara umum")
    data_korban: Optional[List[KorbanDetail]] = Field(default=[], description="Daftar rincian identitas masing-masing korban")
    kronologi: Optional[str] = Field(default=None, description="Kronologi atau uraian singkat kejadian")

    @field_validator('*', mode='before')
    def clean_unknown(cls, v, info):
        if info.field_name != 'data_korban' and isinstance(v, (list, dict)):
            v = str(v)
        if info.field_name != 'data_korban' and isinstance(v, (bool, int, float)):
            v = str(v)
            
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ["belum diketahui", "tidak diketahui", "unknown", "none", "null", "-", "n/a", "na", "tbd"]:
                return None
            return v.strip() if v_lower != "" else v
        return v
