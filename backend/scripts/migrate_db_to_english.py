"""
Database Migration Script: Standardize reports Table Columns to Clean English
=============================================================================
Migrates existing PostgreSQL tables across master and all registered tenants
by renaming legacy Indonesian columns to their standardized English equivalents.
Safe to re-run (idempotent).
"""

import asyncio
import logging
from sqlalchemy import text
from app.db.session import master_engine, MasterSessionLocal, get_tenant_sessionmaker, tenant_engines
from app.models.master_models import Tenant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_migration")

COLUMN_RENAMES = {
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

async def migrate_engine(engine, db_label="Database"):
    logger.info(f"Checking migration for: {db_label}")
    async with engine.begin() as conn:
        # Check if table 'reports' exists
        table_exists_res = await conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'reports'"
        ))
        if not table_exists_res.scalar():
            logger.info(f"[{db_label}] Table 'reports' does not exist yet. Will be created fresh with new schema.")
            return

        # Fetch existing columns
        cols_res = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'reports'"
        ))
        existing_cols = {row[0] for row in cols_res.fetchall()}

        for old_col, new_col in COLUMN_RENAMES.items():
            if old_col in existing_cols and new_col not in existing_cols:
                logger.info(f"[{db_label}] Renaming column '{old_col}' -> '{new_col}'...")
                await conn.execute(text(f'ALTER TABLE reports RENAME COLUMN "{old_col}" TO "{new_col}";'))
            elif old_col in existing_cols and new_col in existing_cols:
                logger.warning(f"[{db_label}] Both '{old_col}' and '{new_col}' exist. Skipping rename.")
            else:
                pass # Already migrated or fresh

    logger.info(f"[{db_label}] Migration check completed.")

async def run_all_migrations():
    # 1. Migrate Master Database
    await migrate_engine(master_engine, "Master DB")

    # 2. Migrate Registered Tenants
    async with MasterSessionLocal() as session:
        result = await session.execute(text("SELECT slug, db_url FROM tenants WHERE is_active = true"))
        tenants = result.fetchall()
        for slug, db_url in tenants:
            if db_url:
                get_tenant_sessionmaker(db_url)
                # Correct asyncpg url format if needed
                clean_url = db_url.replace("postgresql://", "postgresql+asyncpg://") if db_url.startswith("postgresql://") else db_url
                tenant_eng = tenant_engines.get(clean_url) or tenant_engines.get(db_url)
                if tenant_eng:
                    await migrate_engine(tenant_eng, f"Tenant [{slug}]")

if __name__ == "__main__":
    asyncio.run(run_all_migrations())
