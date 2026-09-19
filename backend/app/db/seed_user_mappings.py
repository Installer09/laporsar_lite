import asyncio
import logging
import sys
import os
from sqlalchemy.future import select

# Add parent directory to path to allow running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.session import MasterSessionLocal, get_tenant_sessionmaker
from app.models.master_models import Tenant, UserTenantMapping
from app.models.settings_models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_user_mappings():
    logger.info("Starting user-to-tenant mapping seeding...")
    added_count = 0
    skipped_count = 0

    async with MasterSessionLocal() as master_db:
        # 1. Fetch all active tenants
        result = await master_db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        if not tenants:
            logger.info("No active tenants found. Seeding finished.")
            return

        for tenant in tenants:
            logger.info(f"Processing tenant '{tenant.slug}' (DB: {tenant.db_url.split('@')[-1]})...")
            
            # 2. Connect to tenant DB
            tenant_sessionmaker = get_tenant_sessionmaker(tenant.db_url)
            try:
                async with tenant_sessionmaker() as tenant_db:
                    # 3. Query all users in tenant DB
                    user_result = await tenant_db.execute(select(User))
                    users = user_result.scalars().all()

                    for user in users:
                        if not user.email:
                            continue
                        
                        email_clean = user.email.lower().strip()

                        # 4. Check if mapping already exists in master DB
                        map_result = await master_db.execute(
                            select(UserTenantMapping).where(UserTenantMapping.email == email_clean)
                        )
                        existing_map = map_result.scalar_one_or_none()

                        if not existing_map:
                            new_map = UserTenantMapping(
                                email=email_clean,
                                tenant_slug=tenant.slug
                            )
                            master_db.add(new_map)
                            added_count += 1
                        else:
                            skipped_count += 1
            except Exception as e:
                logger.error(f"Failed to fetch users from tenant '{tenant.slug}' database: {e}")

        # 5. Commit changes to master DB
        if added_count > 0:
            try:
                await master_db.commit()
                logger.info(f"Successfully seeded {added_count} user mappings. Skipped {skipped_count} existing mappings.")
            except Exception as e:
                await master_db.rollback()
                logger.error(f"Failed to commit mappings to Master DB: {e}")
        else:
            logger.info(f"No new user mappings found. Skipped {skipped_count} existing mappings.")

if __name__ == "__main__":
    asyncio.run(seed_user_mappings())
