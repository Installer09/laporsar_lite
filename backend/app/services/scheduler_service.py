import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.future import select
from sqlalchemy import func
from datetime import datetime, timedelta
from app.db.session import MasterSessionLocal, get_tenant_sessionmaker
from app.models.master_models import Tenant
from app.models.report import Report

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def generate_regional_recap():
    """
    Background job that aggregates incident stats for all active tenants.
    Runs hourly/daily to generate regional recaps.
    Uses composite indexes for efficient date/range aggregates.
    """
    logger.info("Starting background regional recap generation...")
    async with MasterSessionLocal() as master_db:
        # Get all active tenants
        result = await master_db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()
        
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        
        for tenant in tenants:
            try:
                # Resolve tenant session
                session_maker = get_tenant_sessionmaker(tenant.db_url)
                async with session_maker() as db:
                    # Query reports created in the last 24 hours using composite indexes
                    report_stmt = select(
                        func.count(Report.id).label("total"),
                        func.sum(func.coalesce(Report.korban_total, 0)).label("total_korban"),
                        func.sum(func.coalesce(Report.korban_selamat, 0)).label("selamat"),
                        func.sum(func.coalesce(Report.korban_meninggal, 0)).label("meninggal"),
                        func.sum(func.coalesce(Report.korban_hilang, 0)).label("hilang")
                    ).where(Report.created_at >= one_day_ago)
                    
                    res = await db.execute(report_stmt)
                    stats = res.fetchone()
                    
                    total = stats.total or 0
                    total_korban = int(stats.total_korban or 0)
                    selamat = int(stats.selamat or 0)
                    meninggal = int(stats.meninggal or 0)
                    hilang = int(stats.hilang or 0)
                    
                    logger.info(
                        f"Regional Recap for tenant '{tenant.slug}' (Last 24h):\n"
                        f"  - Total Reports: {total}\n"
                        f"  - Total Victims: {total_korban} (Selamat: {selamat}, Meninggal: {meninggal}, Hilang: {hilang})"
                    )
            except Exception as e:
                logger.error(f"Failed to generate recap for tenant '{tenant.slug}': {e}")

def start_scheduler():
    if not scheduler.running:
        # Run immediately on start, and then every hour
        scheduler.add_job(generate_regional_recap, 'interval', hours=1, id='regional_recap_job')
        scheduler.start()
        logger.info("Background job scheduler started successfully.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background job scheduler shut down.")
