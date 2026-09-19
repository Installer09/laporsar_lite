import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

# Ensure backend root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import MASTER_DATABASE_URL, get_tenant_sessionmaker
from app.models.master_models import Tenant, GlobalReport
from app.models.report import Report

async def cleanup():
    print("--- Starting Cleanup of Orphaned Global Reports ---")
    
    # 1. Connect to Master DB
    master_engine = create_async_engine(MASTER_DATABASE_URL, echo=False)
    MasterSession = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=master_engine, class_=AsyncSession)
    
    try:
        async with MasterSession() as master_db:
            # Get all active tenants
            result = await master_db.execute(select(Tenant).where(Tenant.is_active == True))
            tenants = result.scalars().all()
            
            # Map tenant slug to active local report IDs
            tenant_local_ids = {}
            
            for tenant in tenants:
                print(f"Checking tenant: {tenant.name} (slug: {tenant.slug})")
                try:
                    tenant_session_maker = get_tenant_sessionmaker(tenant.db_url)
                    async with tenant_session_maker() as tenant_db:
                        # Get all report IDs from this tenant
                        r_result = await tenant_db.execute(select(Report.id))
                        local_ids = set(r_result.scalars().all())
                        tenant_local_ids[tenant.slug] = local_ids
                        print(f"  Found {len(local_ids)} reports locally in tenant {tenant.slug}.")
                except Exception as e:
                    print(f"  Error reading local reports for tenant {tenant.slug}: {e}")
            
            # Get all global reports
            g_result = await master_db.execute(select(GlobalReport))
            global_reports = g_result.scalars().all()
            
            orphaned_reports = []
            for g_rep in global_reports:
                slug = g_rep.tenant_slug
                local_id = g_rep.local_report_id
                
                # If tenant slug is not in our checked tenants, or if the local_id is not in the tenant's local IDs
                if slug in tenant_local_ids:
                    if local_id not in tenant_local_ids[slug]:
                        orphaned_reports.append(g_rep)
                else:
                    # Tenant is inactive or not found, but it has a global report
                    orphaned_reports.append(g_rep)
            
            if orphaned_reports:
                print(f"\nFound {len(orphaned_reports)} orphaned global report(s) to clean up:")
                for r in orphaned_reports:
                    print(f"  - [{r.tenant_slug}] Report ID: {r.local_report_id}, No Laporan: {r.no_laporan}, Pelapor: {r.pelapor_nama}")
                    await master_db.delete(r)
                
                await master_db.commit()
                print("Orphaned global reports successfully deleted from Master DB.")
            else:
                print("\nNo orphaned global reports found.")
                
    except Exception as e:
        print(f"An error occurred during cleanup: {e}")
    finally:
        await master_engine.dispose()

if __name__ == "__main__":
    asyncio.run(cleanup())
