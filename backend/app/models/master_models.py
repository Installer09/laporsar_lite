from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.sql import func
from app.db.base_class import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, index=True, nullable=False)
    db_url = Column(String(255), unique=True, nullable=False)
    s3_bucket = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Tenant administrator details
    admin_name = Column(String(100), nullable=True)
    admin_email = Column(String(100), nullable=True)
    admin_phone = Column(String(50), nullable=True)

class UserTenantMapping(Base):
    __tablename__ = "user_tenant_mappings"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    tenant_slug = Column(String(50), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class GlobalReport(Base):
    __tablename__ = "global_reports"

    id = Column(Integer, primary_key=True, index=True)
    tenant_slug = Column(String(50), index=True, nullable=False)
    local_report_id = Column(Integer, index=True, nullable=False)
    no_laporan = Column(String(50), index=True, nullable=False)
    
    pelapor_nama = Column(String(100), nullable=False)
    pelapor_nomor = Column(String(20), nullable=False)
    
    jenis_kejadian = Column(String(50), index=True)
    waktu = Column(String(50))
    lokasi_teks = Column(String(255))
    koordinat_lat = Column(Float, nullable=True)
    koordinat_lng = Column(Float, nullable=True)
    
    korban_total = Column(Integer, nullable=True)
    korban_selamat = Column(Integer, nullable=True)
    korban_meninggal = Column(Integer, nullable=True)
    korban_hilang = Column(Integer, nullable=True)
    
    status = Column(String(30), index=True)
    created_at = Column(DateTime(timezone=True), index=True)
    updated_at = Column(DateTime(timezone=True))


