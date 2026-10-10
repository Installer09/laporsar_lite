from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text
from typing import List, Optional
import os
import time
import sys
import subprocess
import logging
from pydantic import BaseModel, Field

from app.db.session import get_master_db, get_tenant_sessionmaker
from app.models.master_models import Tenant, UserTenantMapping
from app.core.security import verify_jwt, verify_super_admin

logger = logging.getLogger(__name__)

router = APIRouter(redirect_slashes=False)

class TenantCreate(BaseModel):
    name: str = Field(..., description="Nama Instansi, e.g. Kantor SAR Jakarta")
    slug: str = Field(..., description="Slug unik, e.g. jakarta")
    db_url: str = Field(..., description="Database connection URL, e.g. postgresql://postgres:postgres@db:5432/laporsar_jakarta")
    s3_bucket: str = Field(..., description="S3 Bucket name, e.g. laporsar-jakarta")
    admin_name: str = Field(..., description="Nama administrator instansi")
    admin_email: str = Field(..., description="Email/Username administrator")
    admin_password: str = Field(..., description="Password administrator")
    admin_phone: Optional[str] = Field(None, description="Nomor telepon administrator")

class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    db_url: str
    s3_bucket: str
    is_active: bool
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    admin_phone: Optional[str] = None

    class Config:
        from_attributes = True

async def create_database_if_not_exists(db_url: str):
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    
    # Ensure correct asyncpg prefix for SQLAlchemy connection
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    url = make_url(db_url)
    db_name = url.database
    
    import re
    if not db_name or not re.match(r"^[a-zA-Z0-9_]+$", db_name):
        logger.error(f"Invalid database name parsed from URL: '{db_name}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nama database tidak valid (hanya diperbolehkan huruf, angka, dan underscore)."
        )

    # Connect to standard 'postgres' database on the same host to run CREATE DATABASE
    postgres_url = url.set(database="postgres").render_as_string(hide_password=False)
    
    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        try:
            # Check if database already exists using bound parameters
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name}
            )
            exists = result.scalar()
            if not exists:
                await conn.execute(text(f"CREATE DATABASE {db_name}"))
                logger.info(f"Database '{db_name}' created successfully.")
            else:
                logger.info(f"Database '{db_name}' already exists.")
        except Exception as e:
            logger.error(f"Error checking/creating database '{db_name}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Gagal membuat database penyewa: {str(e)}"
            )
    await engine.dispose()

def run_tenant_migrations(db_url: str):
    # Ensure correct asyncpg prefix is passed for Alembic (which now uses async engine)
    raw_db_url = db_url
    if raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+asyncpg://"):
        raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://")

    # Go up 4 levels to reach the backend root containing alembic.ini (/app)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    cmd = [
        sys.executable, "-m", "alembic",
        "-x", f"db_url={raw_db_url}",
        "upgrade", "head"
    ]
    try:
        result = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True, check=True)
        logger.info(f"Migrations ran successfully for tenant DB. Output:\n{result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run migrations for tenant DB. stdout:\n{e.stdout}\nstderr:\n{e.stderr}")
        raise RuntimeError(f"Gagal menjalankan migrasi Alembic: {e.stderr or e.stdout}")

async def seed_tenant_data(db_url: str):
    session_maker = get_tenant_sessionmaker(db_url)
    async with session_maker() as db:
        # 1. Seed Dictionary Words
        from app.db.seed_dictionary import seed_default_dictionary
        try:
            await seed_default_dictionary(db)
        except Exception as e:
            logger.error(f"Failed to seed dictionary: {e}")

        # 2. Seed Default Settings
        from app.models.settings_models import SystemSetting
        from app.api.routes.identitas import DEFAULT_IDENTITAS
        try:
            for key, val in DEFAULT_IDENTITAS.items():
                # check if exists
                res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
                if not res.scalar_one_or_none():
                    db.add(SystemSetting(key=key, value=val))
            await db.commit()
            logger.info("Successfully seeded default settings for tenant.")
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to seed default settings: {e}")

        # 3. Seed/Sync Classifications
        from app.db.seed_classifications import sync_classifications_from_center
        try:
            await sync_classifications_from_center(db)
        except Exception as e:
            logger.error(f"Failed to sync classifications: {e}")

@router.post("/tenants", response_model=TenantResponse, dependencies=[Depends(verify_super_admin)])
async def create_tenant(tenant_in: TenantCreate, background_tasks: BackgroundTasks, db_master: AsyncSession = Depends(get_master_db)):
    slug_clean = tenant_in.slug.lower().strip()
    db_url_clean = tenant_in.db_url.strip()
    s3_bucket_clean = tenant_in.s3_bucket.lower().strip()
    admin_email_clean = tenant_in.admin_email.lower().strip()

    # 1. Check if slug or db_url or s3_bucket already exists in master registry
    res = await db_master.execute(
        select(Tenant).where(
            (Tenant.slug == slug_clean) |
            (Tenant.db_url == db_url_clean) |
            (Tenant.s3_bucket == s3_bucket_clean)
        )
    )
    existing = res.scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant dengan slug, db_url, atau s3_bucket tersebut sudah terdaftar."
        )

    # Check globally registered emails
    res_map = await db_master.execute(
        select(UserTenantMapping).where(UserTenantMapping.email == admin_email_clean)
    )
    if res_map.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email administrator sudah terdaftar secara global."
        )

    # 2. Create the tenant database
    await create_database_if_not_exists(db_url_clean)

    # 3. Register tenant in master registry
    new_tenant = Tenant(
        name=tenant_in.name,
        slug=slug_clean,
        db_url=db_url_clean,
        s3_bucket=s3_bucket_clean,
        admin_name=tenant_in.admin_name.strip(),
        admin_email=admin_email_clean,
        admin_phone=tenant_in.admin_phone.strip() if tenant_in.admin_phone else None
    )
    db_master.add(new_tenant)
    try:
        await db_master.commit()
        await db_master.refresh(new_tenant)
    except Exception as e:
        await db_master.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mendaftarkan tenant di database master: {str(e)}"
        )

    # 4. Fully provision tenant schema, seed data, and admin account
    try:
        from app.db.provision_tenant import provision_tenant_db
        await provision_tenant_db(new_tenant, admin_password=tenant_in.admin_password, db_master=db_master)
    except Exception as e:
        logger.error(f"Post-creation setup failed for tenant {new_tenant.slug}: {e}")
        # Non-fatal to registration, but logged

    # 5. Create storage directories / bucket for Tenant
    try:
        from app.services.storage_service import storage_service
        if hasattr(storage_service, "create_bucket_if_not_exists"):
            background_tasks.add_task(storage_service.create_bucket_if_not_exists, new_tenant.s3_bucket)
    except Exception as e:
        logger.warning(f"Could not queue bucket creation task: {e}")

    return new_tenant

@router.get("/tenants", response_model=List[TenantResponse], dependencies=[Depends(verify_super_admin)])
async def list_tenants(db_master: AsyncSession = Depends(get_master_db)):
    res = await db_master.execute(select(Tenant).order_by(Tenant.id.asc()))
    return res.scalars().all()

@router.put("/tenants/{tenant_id}", response_model=TenantResponse, dependencies=[Depends(verify_super_admin)])
async def update_tenant(tenant_id: int, payload: dict, db_master: AsyncSession = Depends(get_master_db)):
    res = await db_master.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")
    
    old_admin_email = tenant.admin_email

    if "admin_email" in payload and payload["admin_email"]:
        new_email_clean = payload["admin_email"].lower().strip()
        if new_email_clean != old_admin_email:
            res_map = await db_master.execute(
                select(UserTenantMapping).where(UserTenantMapping.email == new_email_clean)
            )
            if res_map.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email administrator sudah terdaftar secara global.")
            
            if old_admin_email:
                res_map_old = await db_master.execute(
                    select(UserTenantMapping).where(UserTenantMapping.email == old_admin_email)
                )
                old_map = res_map_old.scalar_one_or_none()
                if old_map:
                    old_map.email = new_email_clean
                    db_master.add(old_map)
                else:
                    db_master.add(UserTenantMapping(email=new_email_clean, tenant_slug=tenant.slug))
            else:
                db_master.add(UserTenantMapping(email=new_email_clean, tenant_slug=tenant.slug))

    try:
        from app.models.settings_models import User
        from app.core.security import get_password_hash

        tenant_sessionmaker = get_tenant_sessionmaker(tenant.db_url if "db_url" not in payload else payload["db_url"])
        async with tenant_sessionmaker() as tenant_db:
            local_user = None
            if old_admin_email:
                res_user = await tenant_db.execute(select(User).where(User.email == old_admin_email))
                local_user = res_user.scalar_one_or_none()
            
            if not local_user:
                res_user = await tenant_db.execute(select(User).where(User.role.in_(["Admin", "admin", "Super Admin"])))
                local_user = res_user.scalar_one_or_none()

            if local_user:
                if "admin_name" in payload:
                    local_user.name = payload["admin_name"].strip()
                if "admin_email" in payload:
                    local_user.email = payload["admin_email"].lower().strip()
                if "admin_phone" in payload:
                    local_user.phone = payload["admin_phone"].strip() if payload["admin_phone"] else None
                if "admin_password" in payload and payload["admin_password"]:
                    local_user.hashed_password = get_password_hash(payload["admin_password"])
                tenant_db.add(local_user)
            else:
                admin_name_val = payload.get("admin_name", tenant.name + " Admin").strip()
                admin_email_val = payload.get("admin_email", tenant.admin_email or "").lower().strip()
                admin_phone_val = payload.get("admin_phone", tenant.admin_phone or "").strip() if payload.get("admin_phone") else None
                password_val = payload.get("admin_password", "admin123")

                hashed_pwd = get_password_hash(password_val)
                new_user = User(
                    name=admin_name_val,
                    email=admin_email_val,
                    phone=admin_phone_val,
                    role="Admin",
                    hashed_password=hashed_pwd,
                    is_active=True,
                    is_verified=True
                )
                tenant_db.add(new_user)
            await tenant_db.commit()
    except Exception as e:
        logger.error(f"Failed to synchronize tenant admin user profile in regional DB: {e}")

    if "name" in payload:
        tenant.name = payload["name"]
    if "db_url" in payload:
        tenant.db_url = payload["db_url"]
    if "s3_bucket" in payload:
        tenant.s3_bucket = payload["s3_bucket"]
    if "is_active" in payload:
        tenant.is_active = bool(payload["is_active"])
    if "admin_name" in payload:
        tenant.admin_name = payload["admin_name"].strip()
    if "admin_email" in payload:
        tenant.admin_email = payload["admin_email"].lower().strip()
    if "admin_phone" in payload:
        tenant.admin_phone = payload["admin_phone"].strip() if payload["admin_phone"] else None

    try:
        await db_master.commit()
        await db_master.refresh(tenant)
        return tenant
    except Exception as e:
        await db_master.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui tenant: {str(e)}")

@router.delete("/tenants/{tenant_id}", dependencies=[Depends(verify_super_admin)])
async def delete_tenant(tenant_id: int, db_master: AsyncSession = Depends(get_master_db)):
    res = await db_master.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")
    
    # Delete user-tenant mappings for this tenant's slug
    await db_master.execute(
        text("DELETE FROM user_tenant_mappings WHERE tenant_slug = :slug"),
        {"slug": tenant.slug}
    )
    
    # Delete mirrored global reports
    await db_master.execute(
        text("DELETE FROM global_reports WHERE tenant_slug = :slug"),
        {"slug": tenant.slug}
    )
    
    # Dispose and remove connection pool from cache
    try:
        from app.db.session import tenant_engines, tenant_sessionmakers
        clean_url = tenant.db_url
        if clean_url.startswith("postgresql://"):
            clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://")
        if clean_url in tenant_engines:
            await tenant_engines[clean_url].dispose()
            tenant_engines.pop(clean_url, None)
            tenant_sessionmakers.pop(clean_url, None)
    except Exception as pool_err:
        logger.warning(f"Engine disposal note during tenant deletion: {pool_err}")

    # Delete tenant record from master registry
    await db_master.delete(tenant)
    
    try:
        await db_master.commit()
        return {"status": "success", "detail": "Tenant unregistered successfully"}
    except Exception as e:
        await db_master.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus instansi: {str(e)}")

@router.get("/reports", dependencies=[Depends(verify_super_admin)])
async def get_global_reports(db_master: AsyncSession = Depends(get_master_db)):
    """Fetch and aggregate report data from all active regional tenant databases concurrently."""
    res = await db_master.execute(select(Tenant).where(Tenant.is_active == True))
    tenants = res.scalars().all()
    
    import asyncio
    
    async def query_tenant_reports(tenant):
        reports_list = []
        try:
            session_maker = get_tenant_sessionmaker(tenant.db_url)
            # Query the tenant's reports table with a 3.0 second timeout to prevent hanging connections
            async with session_maker() as session:
                from app.models.report import Report
                from sqlalchemy.future import select
                
                result = await asyncio.wait_for(
                    session.execute(select(Report).order_by(Report.created_at.desc())),
                    timeout=3.0
                )
                db_reports = result.scalars().all()
                for r in db_reports:
                    # Mask reporter phone number for privacy
                    masked_nomor = "********"
                    if r.pelapor_nomor and len(r.pelapor_nomor) > 4:
                        masked_nomor = "*" * (len(r.pelapor_nomor) - 4) + r.pelapor_nomor[-4:]
                    
                    reports_list.append({
                        "id": r.id,
                        "no_laporan": r.no_laporan,
                        "pelapor_nama": r.pelapor_nama,
                        "pelapor_nomor": masked_nomor,
                        "jenis_kejadian": r.jenis_kejadian,
                        "waktu": r.waktu,
                        "lokasi_teks": r.lokasi_teks,
                        "koordinat_lat": r.koordinat_lat,
                        "koordinat_lng": r.koordinat_lng,
                        "pos_sar_terdekat": r.pos_sar_terdekat,
                        "jarak_ke_lokasi": r.jarak_ke_lokasi,
                        "status": r.status,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "tenant_slug": tenant.slug,
                        "tenant_name": tenant.name
                    })
        except asyncio.TimeoutError:
            logger.warning(f"Timeout querying database for tenant {tenant.slug}")
        except Exception as e:
            logger.error(f"Error querying database for tenant {tenant.slug}: {e}")
        return reports_list

    # Run queries concurrently
    tasks = [query_tenant_reports(t) for t in tenants]
    results = await asyncio.gather(*tasks)
    
    # Flatten the list of lists
    all_reports = [report for sublist in results for report in sublist]
    
    # Sort by created_at desc globally
    all_reports.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return all_reports


class ConnectionTestResponse(BaseModel):
    db_status: str
    db_latency_ms: Optional[float]
    db_error: Optional[str]
    s3_status: str
    s3_latency_ms: Optional[float]
    s3_error: Optional[str]

@router.post("/tenants/{tenant_id}/test", response_model=ConnectionTestResponse, dependencies=[Depends(verify_super_admin)])
async def test_tenant_connection(tenant_id: int, db_master: AsyncSession = Depends(get_master_db)):
    res = await db_master.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")

    db_status = "success"
    db_latency = None
    db_error = None
    
    # Test DB connection
    db_url = tenant.db_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    from sqlalchemy.ext.asyncio import create_async_engine
    start_time = time.perf_counter()
    engine = None
    try:
        engine = create_async_engine(db_url, connect_args={"timeout": 5})
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_latency = (time.perf_counter() - start_time) * 1000.0
    except Exception as e:
        db_status = "error"
        db_error = str(e)
    finally:
        if engine:
            await engine.dispose()

    # Test S3 / Local Storage connection
    s3_status = "success"
    s3_latency = None
    s3_error = None

    from app.services.storage_service import storage_service
    if hasattr(storage_service, "_client") and storage_service._client:
        start_time = time.perf_counter()
        try:
            exists = storage_service._client.bucket_exists(tenant.s3_bucket)
            s3_latency = (time.perf_counter() - start_time) * 1000.0
            if not exists:
                s3_status = "error"
                s3_error = f"Bucket '{tenant.s3_bucket}' not found."
        except Exception as e:
            s3_status = "error"
            s3_error = str(e)
    else:
        # Local storage mode (Lapor SAR Lite)
        start_time = time.perf_counter()
        try:
            if storage_service.is_available():
                s3_latency = (time.perf_counter() - start_time) * 1000.0
                s3_status = "success"
            else:
                s3_status = "error"
                s3_error = "Direktori penyimpanan lokal tidak dapat diakses."
        except Exception as e:
            s3_status = "error"
            s3_error = str(e)

    return ConnectionTestResponse(
        db_status=db_status,
        db_latency_ms=db_latency,
        db_error=db_error,
        s3_status=s3_status,
        s3_latency_ms=s3_latency,
        s3_error=s3_error
    )
