import asyncio
import os
import sys

# Ensure backend root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_migration import SafeMigrationRunner

async def migrate_all():
    """
    Standard entrypoint for tenant migrations.
    Now backed by SafeMigrationRunner to ensure automated pre-migration backups,
    atomic verification, and failure safety.
    """
    runner = SafeMigrationRunner()
    try:
        summary = await runner.execute_migrations(backup_first=True, dry_run=False)
        return summary
    finally:
        await runner.close()

if __name__ == "__main__":
    asyncio.run(migrate_all())
