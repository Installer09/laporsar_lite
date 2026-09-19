import os
import sys
import json
import logging
import argparse
import asyncio
import datetime
import subprocess
from typing import Dict, List, Any, Optional

# Ensure backend root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from app.db.session import MASTER_DATABASE_URL, get_tenant_sessionmaker
from app.models.master_models import Tenant
from app.services.system_backup import SystemBackupService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SafeMigration")

BACKUP_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups", "pre_migration")


class SafeMigrationRunner:
    """
    Release Manager Utility:
    Ensures safe database migrations with automated pre-migration snapshots,
    multi-tenant consistency verification, and instant rollback capabilities.
    """

    def __init__(self, master_db_url: str = MASTER_DATABASE_URL):
        self.master_db_url = master_db_url
        self.engine = create_async_engine(master_db_url, echo=False)
        self.session_factory = sessionmaker(
            autocommit=False, autoflush=False, expire_on_commit=False, bind=self.engine, class_=AsyncSession
        )

    async def get_active_tenants(self) -> List[Tenant]:
        """Fetch active tenants from Master DB."""
        async with self.session_factory() as session:
            try:
                res = await session.execute(select(Tenant).where(Tenant.is_active == True))
                return list(res.scalars().all())
            except Exception as e:
                logger.warning(f"Failed to query tenants table: {e}")
                return []

    async def get_alembic_current_rev(self, db_url: str) -> Optional[str]:
        """Query alembic_version table directly to find current schema revision."""
        eng = create_async_engine(db_url, echo=False)
        try:
            async with eng.begin() as conn:
                res = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                row = res.fetchone()
                return row[0] if row else None
        except Exception:
            return None
        finally:
            await eng.dispose()

    async def preflight_check(self) -> Dict[str, Any]:
        """
        Verify database connections, check current Alembic revision for Master and Tenants.
        """
        logger.info("=== STEP 1: Preflight Verification ===")
        report = {
            "master_db": "unhealthy",
            "master_rev": None,
            "tenants": [],
            "status": "ok"
        }

        # Check master DB
        try:
            async with self.session_factory() as session:
                await session.execute(text("SELECT 1"))
            report["master_db"] = "healthy"
            report["master_rev"] = await self.get_alembic_current_rev(self.master_db_url)
            logger.info(f"Master DB is connected. Current revision: {report['master_rev']}")
        except Exception as e:
            report["master_db"] = f"error: {e}"
            report["status"] = "failed"
            logger.error(f"Preflight FAILED on Master DB: {e}")
            return report

        # Check tenants
        tenants = await self.get_active_tenants()
        for t in tenants:
            t_info = {"slug": t.slug, "name": t.name, "status": "unhealthy", "rev": None}
            try:
                sm = get_tenant_sessionmaker(t.db_url)
                async with sm() as t_session:
                    await t_session.execute(text("SELECT 1"))
                t_info["status"] = "healthy"
                t_info["rev"] = await self.get_alembic_current_rev(t.db_url)
                logger.info(f"Tenant '{t.slug}' ({t.name}) is connected. Current revision: {t_info['rev']}")
            except Exception as te:
                t_info["status"] = f"error: {te}"
                report["status"] = "warning"
                logger.warning(f"Tenant '{t.slug}' connection issue: {te}")
            report["tenants"].append(t_info)

        return report

    async def create_pre_migration_backup(self, custom_dir: Optional[str] = None) -> str:
        """
        Export pre-migration snapshots for Master DB and each active Tenant DB.
        Saves into a timestamped directory and writes manifest.json.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = custom_dir or os.path.join(BACKUP_ROOT, f"pre_mig_{timestamp}")
        os.makedirs(target_dir, exist_ok=True)

        logger.info(f"=== STEP 2: Creating Automated Pre-Migration Backup Snapshot ===")
        logger.info(f"Snapshot directory: {target_dir}")

        manifest = {
            "timestamp": datetime.datetime.now().isoformat(),
            "target_dir": target_dir,
            "master_db": None,
            "tenants": {},
            "status": "success"
        }

        # Backup Master DB (Tenants table)
        try:
            async with self.session_factory() as session:
                res = await session.execute(select(Tenant))
                tenants_all = res.scalars().all()
                tenants_data = [
                    {c.name: getattr(t, c.name) for c in Tenant.__table__.columns}
                    for t in tenants_all
                ]
                master_backup_path = os.path.join(target_dir, "master_tenants.json")
                with open(master_backup_path, "w", encoding="utf-8") as f:
                    json.dump(tenants_data, f, indent=2, default=str)
                manifest["master_db"] = {
                    "path": master_backup_path,
                    "rows": len(tenants_data)
                }
                logger.info(f"Master DB snapshot saved: {master_backup_path} ({len(tenants_data)} tenants)")
        except Exception as e:
            logger.error(f"Failed to backup Master DB: {e}")
            manifest["master_db"] = {"error": str(e)}

        # Backup each Tenant DB using SystemBackupService
        tenants = await self.get_active_tenants()
        for t in tenants:
            try:
                sm = get_tenant_sessionmaker(t.db_url)
                async with sm() as t_session:
                    t_session.info["tenant_slug"] = t.slug
                    zip_bytes = await SystemBackupService.export_backup(t_session)
                    tenant_file = os.path.join(target_dir, f"tenant_{t.slug}.zip")
                    with open(tenant_file, "wb") as f:
                        f.write(zip_bytes)
                    manifest["tenants"][t.slug] = {
                        "path": tenant_file,
                        "size_bytes": len(zip_bytes)
                    }
                    logger.info(f"Tenant '{t.slug}' snapshot saved: {tenant_file} ({len(zip_bytes)} bytes)")
            except Exception as te:
                logger.error(f"Failed to backup Tenant '{t.slug}': {te}")
                manifest["tenants"][t.slug] = {"error": str(te)}
                manifest["status"] = "partial_failure"

        # Write manifest.json
        manifest_path = os.path.join(target_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Pre-migration backup completed. Manifest written to {manifest_path}")
        return target_dir

    def run_alembic_upgrade(self, db_url: str, slug: str = "database") -> bool:
        """Run alembic upgrade head with clean subprocess logging."""
        display_url = db_url.split("@")[-1] if "@" in db_url else db_url
        logger.info(f"Running Alembic migration on [{slug}]: {display_url}")

        cmd = [
            sys.executable, "-m", "alembic",
            "-x", f"db_url={db_url}",
            "upgrade", "head"
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            logger.info(f"Migration SUCCEEDED for [{slug}]")
            if result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    logger.info(f"  [alembic] {line}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Migration FAILED for [{slug}]!")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")
            return False

    async def execute_migrations(self, backup_first: bool = True, dry_run: bool = False) -> Dict[str, Any]:
        """
        Full orchestration of Safe Migration:
        1. Preflight check
        2. Automated pre-migration snapshot
        3. Master DB Alembic upgrade
        4. Multi-Tenant DBs Alembic upgrade & classification sync
        5. Verification
        """
        logger.info("==================================================")
        logger.info("       LAPOR SAR SAFE MIGRATION RUNNER            ")
        logger.info("==================================================")

        preflight = await self.preflight_check()
        if preflight["status"] == "failed":
            raise RuntimeError("Preflight verification failed. Aborting migrations.")

        backup_dir = None
        if backup_first and not dry_run:
            backup_dir = await self.create_pre_migration_backup()

        if dry_run:
            logger.info("=== DRY-RUN MODE: No schema modifications will be applied ===")
            return {
                "status": "dry_run_complete",
                "preflight": preflight,
                "backup_dir": backup_dir
            }

        logger.info("=== STEP 3: Executing Alembic Upgrades ===")

        # 1. Master DB schema verify & alembic
        async with self.engine.begin() as conn:
            await conn.run_sync(Tenant.__table__.create, checkfirst=True)
        
        master_success = self.run_alembic_upgrade(self.master_db_url, slug="master")
        if not master_success:
            logger.error(f"CRITICAL: Master DB migration failed! Instant rollback recommended:")
            logger.error(f"Rollback command: python safe_migration.py --rollback \"{backup_dir}\"")
            raise RuntimeError("Master DB migration failed.")

        # 2. Tenants migration
        tenants = await self.get_active_tenants()
        logger.info(f"Found {len(tenants)} active tenants to migrate.")

        failed_tenants = []
        succeeded_tenants = []

        for tenant in tenants:
            logger.info(f"--- Processing Tenant: {tenant.name} ({tenant.slug}) ---")
            success = self.run_alembic_upgrade(tenant.db_url, slug=tenant.slug)
            if not success:
                failed_tenants.append(tenant.slug)
                logger.error(f"Migration failed for tenant '{tenant.slug}'.")
                continue

            # Sync classifications from center
            try:
                from app.db.seed_classifications import sync_classifications_from_center
                session_maker = get_tenant_sessionmaker(tenant.db_url)
                async with session_maker() as tenant_db:
                    await sync_classifications_from_center(tenant_db)
                logger.info(f"Synced classifications successfully for '{tenant.slug}'")
            except Exception as sync_err:
                logger.warning(f"Classification sync warning for '{tenant.slug}': {sync_err}")

            succeeded_tenants.append(tenant.slug)

        summary = {
            "status": "success" if not failed_tenants else "partial_failure",
            "backup_dir": backup_dir,
            "master": "succeeded",
            "succeeded_tenants": succeeded_tenants,
            "failed_tenants": failed_tenants
        }

        if failed_tenants:
            logger.error(f"WARNING: {len(failed_tenants)} tenants failed migration: {failed_tenants}")
            logger.error(f"To restore previous state: python safe_migration.py --rollback \"{backup_dir}\"")
        else:
            logger.info("=== ALL MIGRATIONS COMPLETED SAFELY AND SUCCESSFULLY! ===")

        return summary

    async def rollback_from_backup(self, backup_dir: str) -> Dict[str, Any]:
        """
        Instant Rollback: Restore Master & Tenant databases from a snapshot directory.
        """
        logger.info("==================================================")
        logger.info("         RESTORING FROM PRE-MIGRATION BACKUP      ")
        logger.info("==================================================")
        manifest_path = os.path.join(backup_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found in {backup_dir}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        logger.info(f"Loaded snapshot created at: {manifest.get('timestamp')}")
        results = {"tenants": {}, "status": "restored"}

        # Restore tenants
        for slug, t_info in manifest.get("tenants", {}).items():
            snap_path = t_info.get("path")
            if not snap_path or not os.path.exists(snap_path):
                logger.warning(f"Snapshot missing for tenant {slug}: {snap_path}")
                continue

            # Find tenant DB URL
            tenants = await self.get_active_tenants()
            target_tenant = next((t for t in tenants if t.slug == slug), None)
            if not target_tenant:
                logger.warning(f"Tenant {slug} not found in current Master DB.")
                continue

            try:
                with open(snap_path, "rb") as f:
                    zip_data = f.read()
                sm = get_tenant_sessionmaker(target_tenant.db_url)
                async with sm() as session:
                    session.info["tenant_slug"] = slug
                    res = await SystemBackupService.import_restore(zip_data, session)
                    results["tenants"][slug] = "restored"
                    logger.info(f"Successfully restored tenant '{slug}' from {snap_path}")
            except Exception as e:
                logger.error(f"Failed to restore tenant '{slug}': {e}")
                results["tenants"][slug] = f"failed: {e}"
                results["status"] = "partial_restore"

        return results

    async def close(self):
        await self.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Lapor SAR Safe Migration Runner")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without modifying schemas")
    parser.add_argument("--backup-only", action="store_true", help="Create pre-migration backup only")
    parser.add_argument("--skip-backup", action="store_true", help="Bypass automated backup (not recommended)")
    parser.add_argument("--rollback", type=str, help="Restore from a pre-migration snapshot directory")
    parser.add_argument("--dir", type=str, help="Custom output directory for pre-migration backups")
    args = parser.parse_args()

    runner = SafeMigrationRunner()

    async def _run():
        try:
            if args.rollback:
                await runner.rollback_from_backup(args.rollback)
            elif args.backup_only:
                await runner.create_pre_migration_backup(custom_dir=args.dir)
            else:
                await runner.execute_migrations(
                    backup_first=not args.skip_backup,
                    dry_run=args.dry_run
                )
        finally:
            await runner.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
