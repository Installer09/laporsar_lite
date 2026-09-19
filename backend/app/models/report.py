from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
try:
    from geoalchemy2 import Geometry
    GeometryType = Geometry('POINT', srid=4326)
except ImportError:
    GeometryType = Text

from app.db.session import Base
import enum

class ReportStatus(str, enum.Enum):
    PENDING = "PENDING"
    AKTIF = "AKTIF"
    TIDAK_AKTIF = "TIDAK_AKTIF"
    SALAH_LAPORAN = "SALAH_LAPORAN"

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    no_laporan = Column(String(50), unique=True, index=True, nullable=False)
    
    pelapor_nama = Column(String(100), nullable=False)
    pelapor_nomor = Column(String(20), nullable=False, index=True)
    pelapor_lat = Column(Float, nullable=True)
    pelapor_lng = Column(Float, nullable=True)
    
    jenis_kejadian = Column(String(50), index=True)
    waktu = Column(String(50))
    lokasi_teks = Column(String(255))
    
    koordinat_lat = Column(Float, nullable=True)
    koordinat_lng = Column(Float, nullable=True)
    location_geom = Column(GeometryType, nullable=True)
    
    pos_sar_terdekat = Column(String(100))
    jarak_ke_lokasi = Column(String(50))
    heading_ke_lokasi = Column(Float, nullable=True)
    gmaps_link = Column(String(255))
    radius_pencarian = Column(Float, nullable=True, default=2.0)
    
    korban = Column(String(255))
    korban_total = Column(Integer, nullable=True)
    korban_selamat = Column(Integer, nullable=True)
    korban_meninggal = Column(Integer, nullable=True)
    korban_hilang = Column(Integer, nullable=True)
    data_korban = Column(JSONB, nullable=True)  # JSONB
    
    metadata_kejadian = Column(JSONB, nullable=True) # Polymorphic metadata (replacing kapal_*)
    
    unsur_alut = Column(JSONB, nullable=True)

    kronologi = Column(Text)
    eviden_id = Column(String(100))
    info_awal_text = Column(Text, nullable=True)
    
    status = Column(Enum(ReportStatus), default=ReportStatus.PENDING, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    version_id = Column(Integer, nullable=False, default=1)

    __mapper_args__ = {
        "version_id_col": version_id
    }

class ReportSequence(Base):
    __tablename__ = "report_sequences"
    
    year_month = Column(String(6), primary_key=True) # e.g. "202605"
    last_seq = Column(Integer, default=0)
