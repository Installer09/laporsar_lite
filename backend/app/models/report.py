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
    report_number = Column(String(50), unique=True, index=True, nullable=False)
    
    reporter_name = Column(String(100), nullable=False)
    reporter_phone = Column(String(20), nullable=False, index=True)
    reporter_lat = Column(Float, nullable=True)
    reporter_lng = Column(Float, nullable=True)
    
    incident_type = Column(String(50), index=True)
    incident_time = Column(String(50))
    location_text = Column(String(255))
    
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_geom = Column(GeometryType, nullable=True)
    
    nearest_sar_post = Column(String(100))
    distance_nm = Column(String(50))
    heading_degree = Column(Float, nullable=True)
    gmaps_link = Column(String(255))
    search_radius_km = Column(Float, nullable=True, default=2.0)
    
    victim_summary = Column(String(255))
    total_victims = Column(Integer, nullable=True)
    survived_victims = Column(Integer, nullable=True)
    deceased_victims = Column(Integer, nullable=True)
    missing_victims = Column(Integer, nullable=True)
    victim_data = Column(JSONB, nullable=True)
    
    incident_metadata = Column(JSONB, nullable=True)
    resources_deployed = Column(JSONB, nullable=True)

    chronology = Column(Text)
    evidence_id = Column(String(100))
    initial_report_text = Column(Text, nullable=True)
    
    status = Column(Enum(ReportStatus), default=ReportStatus.PENDING, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    version_id = Column(Integer, nullable=False, default=1)

    __mapper_args__ = {
        "version_id_col": version_id
    }

    def __init__(self, **kwargs):
        # Zero-downtime translation from legacy Indonesian keys to English attributes
        legacy_map = {
            "no_laporan": "report_number",
            "pelapor_nama": "reporter_name",
            "pelapor_nomor": "reporter_phone",
            "pelapor_lat": "reporter_lat",
            "pelapor_lng": "reporter_lng",
            "jenis_kejadian": "incident_type",
            "waktu": "incident_time",
            "lokasi_teks": "location_text",
            "koordinat_lat": "latitude",
            "koordinat_lng": "longitude",
            "pos_sar_terdekat": "nearest_sar_post",
            "jarak_ke_lokasi": "distance_nm",
            "heading_ke_lokasi": "heading_degree",
            "radius_pencarian": "search_radius_km",
            "korban": "victim_summary",
            "korban_total": "total_victims",
            "korban_selamat": "survived_victims",
            "korban_meninggal": "deceased_victims",
            "korban_hilang": "missing_victims",
            "data_korban": "victim_data",
            "metadata_kejadian": "incident_metadata",
            "unsur_alut": "resources_deployed",
            "kronologi": "chronology",
            "eviden_id": "evidence_id",
            "info_awal_text": "initial_report_text"
        }
        for old_k, new_k in legacy_map.items():
            if old_k in kwargs and new_k not in kwargs:
                kwargs[new_k] = kwargs.pop(old_k)
        super().__init__(**kwargs)

    # ── Backward Compatibility Property Getters & Setters ──
    @property
    def no_laporan(self):
        return self.report_number
    @no_laporan.setter
    def no_laporan(self, val):
        self.report_number = val

    @property
    def pelapor_nama(self):
        return self.reporter_name
    @pelapor_nama.setter
    def pelapor_nama(self, val):
        self.reporter_name = val

    @property
    def pelapor_nomor(self):
        return self.reporter_phone
    @pelapor_nomor.setter
    def pelapor_nomor(self, val):
        self.reporter_phone = val

    @property
    def pelapor_lat(self):
        return self.reporter_lat
    @pelapor_lat.setter
    def pelapor_lat(self, val):
        self.reporter_lat = val

    @property
    def pelapor_lng(self):
        return self.reporter_lng
    @pelapor_lng.setter
    def pelapor_lng(self, val):
        self.reporter_lng = val

    @property
    def jenis_kejadian(self):
        return self.incident_type
    @jenis_kejadian.setter
    def jenis_kejadian(self, val):
        self.incident_type = val

    @property
    def waktu(self):
        return self.incident_time
    @waktu.setter
    def waktu(self, val):
        self.incident_time = val

    @property
    def lokasi_teks(self):
        return self.location_text
    @lokasi_teks.setter
    def lokasi_teks(self, val):
        self.location_text = val

    @property
    def koordinat_lat(self):
        return self.latitude
    @koordinat_lat.setter
    def koordinat_lat(self, val):
        self.latitude = val

    @property
    def koordinat_lng(self):
        return self.longitude
    @koordinat_lng.setter
    def koordinat_lng(self, val):
        self.longitude = val

    @property
    def pos_sar_terdekat(self):
        return self.nearest_sar_post
    @pos_sar_terdekat.setter
    def pos_sar_terdekat(self, val):
        self.nearest_sar_post = val

    @property
    def jarak_ke_lokasi(self):
        return self.distance_nm
    @jarak_ke_lokasi.setter
    def jarak_ke_lokasi(self, val):
        self.distance_nm = val

    @property
    def heading_ke_lokasi(self):
        return self.heading_degree
    @heading_ke_lokasi.setter
    def heading_ke_lokasi(self, val):
        self.heading_degree = val

    @property
    def radius_pencarian(self):
        return self.search_radius_km
    @radius_pencarian.setter
    def radius_pencarian(self, val):
        self.search_radius_km = val

    @property
    def korban(self):
        return self.victim_summary
    @korban.setter
    def korban(self, val):
        self.victim_summary = val

    @property
    def korban_total(self):
        return self.total_victims
    @korban_total.setter
    def korban_total(self, val):
        self.total_victims = val

    @property
    def korban_selamat(self):
        return self.survived_victims
    @korban_selamat.setter
    def korban_selamat(self, val):
        self.survived_victims = val

    @property
    def korban_meninggal(self):
        return self.deceased_victims
    @korban_meninggal.setter
    def korban_meninggal(self, val):
        self.deceased_victims = val

    @property
    def korban_hilang(self):
        return self.missing_victims
    @korban_hilang.setter
    def korban_hilang(self, val):
        self.missing_victims = val

    @property
    def data_korban(self):
        return self.victim_data
    @data_korban.setter
    def data_korban(self, val):
        self.victim_data = val

    @property
    def metadata_kejadian(self):
        return self.incident_metadata
    @metadata_kejadian.setter
    def metadata_kejadian(self, val):
        self.incident_metadata = val

    @property
    def unsur_alut(self):
        return self.resources_deployed
    @unsur_alut.setter
    def unsur_alut(self, val):
        self.resources_deployed = val

    @property
    def kronologi(self):
        return self.chronology
    @kronologi.setter
    def kronologi(self, val):
        self.chronology = val

    @property
    def eviden_id(self):
        return self.evidence_id
    @eviden_id.setter
    def eviden_id(self, val):
        self.evidence_id = val

    @property
    def info_awal_text(self):
        return self.initial_report_text
    @info_awal_text.setter
    def info_awal_text(self, val):
        self.initial_report_text = val


class ReportSequence(Base):
    __tablename__ = "report_sequences"
    
    year_month = Column(String(6), primary_key=True) # e.g. "202605"
    last_seq = Column(Integer, default=0)
