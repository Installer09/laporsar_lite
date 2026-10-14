import logging
import re
from typing import Optional
from sqlalchemy import text
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import make_url

from app.db.base_class import Base
from app.db.session import (
    get_tenant_sessionmaker,
    tenant_engines,
    MasterSessionLocal,
)
from app.models.master_models import Tenant, UserTenantMapping
from app.models.settings_models import User, SystemSetting
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


async def create_database_if_not_exists(db_url: str) -> None:
    """Create PostgreSQL database on the target host if it does not already exist."""
    clean_db_url = db_url
    if clean_db_url.startswith("postgresql://"):
        clean_db_url = clean_db_url.replace("postgresql://", "postgresql+asyncpg://")

    url = make_url(clean_db_url)
    db_name = url.database

    if not db_name or not re.match(r"^[a-zA-Z0-9_]+$", db_name):
        raise ValueError(f"Invalid database name '{db_name}' in connection URL.")

    # Connect to the default 'postgres' database on the same host to run CREATE DATABASE
    postgres_url = url.set(database="postgres").render_as_string(hide_password=False)
    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name}
            )
            exists = result.scalar()
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info(f"Database '{db_name}' created successfully.")
            else:
                logger.info(f"Database '{db_name}' already exists.")
    finally:
        await engine.dispose()


async def provision_tenant_db(
    tenant: Tenant,
    admin_password: str = "admin",
    db_master: Optional[any] = None
) -> bool:
    """
    Fully provisions a regional tenant database:
    1. Ensures the database exists in PostgreSQL.
    2. Enables PostGIS extension.
    3. Creates all operational tables using Base.metadata.create_all.
    4. Stamps Alembic revision head.
    5. Seeds default dictionary, identity settings, classifications, and locations.
    6. Creates/updates administrator user in the tenant database.
    7. Registers user-tenant mapping in the master database.
    """
    logger.info(f"Starting provisioning for tenant '{tenant.slug}' ({tenant.name})...")
    
    # Skip creating separate DB if tenant uses master DB (e.g. 'pusat')
    url = make_url(tenant.db_url)
    is_master_db = (url.database == "laporsar_master")

    if not is_master_db:
        # 1. Create database if not exists
        await create_database_if_not_exists(tenant.db_url)

    # 2. Initialize schema & extensions
    tenant_sessionmaker = get_tenant_sessionmaker(tenant.db_url)
    engine = tenant_sessionmaker.kw.get('bind')

    # 1. Safely probe extension availability without opening transaction
    has_vector = False
    has_postgis = False
    async with engine.connect() as check_conn:
        res_pg = await check_conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'postgis';"))
        if res_pg.scalar():
            has_postgis = True
        res_vec = await check_conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector';"))
        if res_vec.scalar():
            has_vector = True

    if not has_vector:
        from app.models.knowledge_models import DictionaryWord
        from app.models.vector_memory import VectorMemory
        from sqlalchemy import Text
        if "embedding" in DictionaryWord.__table__.columns:
            DictionaryWord.__table__.columns["embedding"].type = Text()
        if "embedding" in VectorMemory.__table__.columns:
            VectorMemory.__table__.columns["embedding"].type = Text()

    # 2. Run extensions and DDL in transaction
    async with engine.begin() as conn:
        if has_postgis:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            except Exception as e:
                logger.warning(f"PostGIS extension enabling note for {tenant.slug}: {e}")

        if has_vector:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            except Exception as e:
                logger.warning(f"Vector extension enabling note for {tenant.slug}: {e}")

        # Exclude master-only tables from tenant databases if not master
        tables_to_create = [
            t for name, t in Base.metadata.tables.items()
            if is_master_db or name not in ("tenants", "user_tenant_mappings", "global_reports")
        ]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables_to_create))

        # Stamp alembic version
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL, 
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                );
            """))
            await conn.execute(text("DELETE FROM alembic_version;"))
            await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('c7b8e1a2f3d4');"))
        except Exception as e:
            logger.warning(f"Alembic stamp note for {tenant.slug}: {e}")

    # 3. Seed operational data
    async with tenant_sessionmaker() as tenant_db:
        tenant_db.info["tenant_slug"] = tenant.slug

        # Seed Dictionary
        from app.db.seed_dictionary import seed_default_dictionary
        try:
            await seed_default_dictionary(tenant_db)
        except Exception as e:
            logger.warning(f"Dictionary seeding note for {tenant.slug}: {e}")

        # Seed Identity & Settings
        from app.api.routes.identitas import DEFAULT_IDENTITAS
        try:
            for key, val in DEFAULT_IDENTITAS.items():
                res = await tenant_db.execute(select(SystemSetting).where(SystemSetting.key == key))
                if not res.scalar_one_or_none():
                    actual_val = val
                    if key == "identitas_nama_instansi":
                        actual_val = tenant.name
                    elif key == "identitas_wilayah_kerja":
                        actual_val = f"Wilayah Kerja {tenant.name}"
                    tenant_db.add(SystemSetting(key=key, value=actual_val))
            await tenant_db.commit()
        except Exception as e:
            await tenant_db.rollback()
            logger.warning(f"Default settings seeding note for {tenant.slug}: {e}")

        # Seed Classifications
        from app.db.seed_classifications import sync_classifications_from_center
        try:
            await sync_classifications_from_center(tenant_db)
        except Exception as e:
            logger.warning(f"Classifications sync note for {tenant.slug}: {e}")

        # Seed Default Regional Locations if empty
        from app.models.settings_models import Location
        try:
            loc_res = await tenant_db.execute(select(Location))
            if not loc_res.scalars().first():
                default_locations = []
                if tenant.slug == "natuna":
                    default_locations = [
                        Location(name="Kantor SAR Natuna", type="Kantor SAR", lat=3.9431, lng=108.3888, address="Jl. Bandara Ranai, Natuna", unsur="Rescuer KPP Natuna (15 personil), ABK KN SASIKIRANA (12 personil)", alut="KN SASIKIRANA 245, RIB 01 Natuna, D-Max Rescue Carrier"),
                        Location(name="Pos SAR Anambas", type="Pos SAR", lat=3.2167, lng=106.2333, address="Tarempa, Kepulauan Anambas", unsur="Rescuer Pos SAR Anambas (6 personil)", alut="RIB 02 Anambas, Rubber Boat"),
                        Location(name="Unit Siaga SAR Serasan", type="Unit Siaga", lat=2.5000, lng=109.0167, address="Serasan, Natuna", unsur="Rescuer Unit Siaga Serasan (5 personil)", alut="Rubber Boat, Rescue Carrier"),
                        Location(name="Unit Siaga SAR Subi", type="Unit Siaga", lat=3.0500, lng=108.8500, address="Pulau Subi, Natuna", unsur="Unit Siaga Subi (4 personil)", alut="Rubber Boat")
                    ]
                elif tenant.slug == "jakarta":
                    default_locations = [
                        Location(name="Kantor SAR Jakarta", type="Kantor SAR", lat=-6.1264, lng=106.6534, address="Jl. Marsekal Suryadarma No.1, Tangerang", unsur="Tim Rescue Kansar Jakarta (25 personil)", alut="KN SAR Wisnu, Rescue Boat, Hovercraft")
                    ]
                elif tenant.slug == "surabaya":
                    default_locations = [
                        Location(name="Kantor SAR Surabaya", type="Kantor SAR", lat=-7.3756, lng=112.7753, address="Jl. Raya Juanda No.16, Sidoarjo", unsur="Tim Rescue Kansar Surabaya (25 personil)", alut="KN SAR 225, RIB 01 Surabaya, D-Max Rescue")
                    ]
                elif tenant.slug == "pusat":
                    default_locations = [
                        Location(name="Kantor Pusat BASARNAS", type="Kantor Pusat", lat=-6.1558, lng=106.8402, address="Jl. Angkasa Blok B.15 Kav. 2-3, Kemayoran, Jakarta Pusat", unsur="Command Center Siaga 24 Jam (30 personil)", alut="Helikopter Dauphin AS365N3+, Rescue Truck")
                    ]
                if default_locations:
                    tenant_db.add_all(default_locations)
                    await tenant_db.commit()
                    logger.info(f"Seeded {len(default_locations)} default locations for tenant '{tenant.slug}'")
        except Exception as e:
            await tenant_db.rollback()
            logger.warning(f"Location seeding note for {tenant.slug}: {e}")

        # Seed / Ensure Administrator Accounts in Tenant DB
        admin_emails = []
        if tenant.admin_email:
            admin_emails.append(tenant.admin_email.lower().strip())
        
        # Extra aliases for known tenants
        if tenant.slug == "natuna":
            for alias in ("sar.natuna@basarnas.go.id", "admin.natuna@basarnas.go.id", "natuna"):
                if alias not in admin_emails:
                    admin_emails.append(alias)

        for email_item in admin_emails:
            try:
                res_u = await tenant_db.execute(select(User).where(User.email == email_item))
                existing_user = res_u.scalar_one_or_none()
                if not existing_user:
                    hashed_pwd = get_password_hash(admin_password)
                    new_u = User(
                        name=tenant.admin_name or f"Admin SAR {tenant.name}",
                        email=email_item,
                        phone=tenant.admin_phone or "08123456789",
                        role="Admin",
                        hashed_password=hashed_pwd,
                        is_active=True,
                        is_verified=True
                    )
                    tenant_db.add(new_u)
                    await tenant_db.commit()
                    logger.info(f"Created admin user '{email_item}' in tenant '{tenant.slug}' DB.")
            except Exception as e:
                await tenant_db.rollback()
                logger.warning(f"Admin user creation note for '{email_item}' in {tenant.slug}: {e}")

    # 4. Ensure UserTenantMapping in Master DB
    async def register_mapping(session):
        for email_item in admin_emails:
            map_res = await session.execute(
                select(UserTenantMapping).where(UserTenantMapping.email == email_item)
            )
            if not map_res.scalar_one_or_none():
                session.add(UserTenantMapping(email=email_item, tenant_slug=tenant.slug))
                await session.commit()
                logger.info(f"Registered UserTenantMapping for '{email_item}' -> '{tenant.slug}'.")

    if db_master:
        await register_mapping(db_master)
    else:
        async with MasterSessionLocal() as session:
            await register_mapping(session)

    logger.info(f"Tenant '{tenant.slug}' provisioned successfully.")
    return True
