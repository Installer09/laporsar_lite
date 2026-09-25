from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

from app.db.session import get_db, MasterSessionLocal
from app.models.master_models import GlobalReport, Tenant
from app.core.security import verify_jwt

router = APIRouter()

def verify_national_admin(payload: dict = Depends(verify_jwt)):
    """Dependency that ensures only Super Admin or Pusat admin/operator can access national data."""
    role = payload.get("role")
    tenant_slug = payload.get("tenant_slug")
    sub = payload.get("sub")
    
    from app.core.config import settings
    superadmin_user = getattr(settings, "DEV_SUPERADMIN_USERNAME", "superadmin")
    
    # 1. Global Super Admin
    if role == "Super Admin" or sub == superadmin_user:
        return payload
        
    # 2. Basarnas Pusat Command Center admin or operator
    if tenant_slug in (None, "pusat") and role in ("Admin", "admin", "Operator", "Super Admin"):
        return payload
    if sub == settings.DEV_ADMIN_USERNAME:
        return payload
        
    raise HTTPException(
        status_code=403,
        detail="Akses ditolak: Hanya diperbolehkan untuk Basarnas Pusat atau Super Admin."
    )

@router.get("/national/reports", dependencies=[Depends(verify_national_admin)])
async def get_national_reports(
    status: Optional[str] = Query(None, description="Filter status reports"),
    search: Optional[str] = Query(None, description="Search by No Laporan or Pelapor Name"),
    jenis_kejadian: Optional[str] = Query(None, description="Filter by incident type"),
    tenant_slug: Optional[str] = Query(None, description="Filter by specific regional office (tenant slug)"),
    skip: int = Query(0, description="Offset for pagination"),
    limit: int = Query(50, description="Limit for pagination")
):
    """Retrieve mirrored reports from all regions (Master DB)."""
    async with MasterSessionLocal() as master_db:
        query = select(GlobalReport)
        
        # Apply filters
        if status:
            query = query.where(GlobalReport.status == status.upper())
        if jenis_kejadian:
            query = query.where(GlobalReport.jenis_kejadian == jenis_kejadian)
        if tenant_slug:
            query = query.where(GlobalReport.tenant_slug == tenant_slug.lower())
        if search:
            search_pattern = f"%{search.strip().lower()}%"
            query = query.where(
                (func.lower(GlobalReport.no_laporan).like(search_pattern)) |
                (func.lower(GlobalReport.pelapor_nama).like(search_pattern))
            )
            
        # Order by created_at desc
        query = query.order_by(GlobalReport.created_at.desc())
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        result = await master_db.execute(query)
        reports = result.scalars().all()
        return reports

@router.get("/national/stats", dependencies=[Depends(verify_national_admin)])
async def get_national_stats():
    """Get aggregated statistics across all tenants from the master database."""
    async with MasterSessionLocal() as master_db:
        # 1. Total reports count
        total_count = await master_db.scalar(select(func.count(GlobalReport.id)))
        
        # 2. Count by status
        status_counts = {}
        status_res = await master_db.execute(
            select(GlobalReport.status, func.count(GlobalReport.id)).group_by(GlobalReport.status)
        )
        for row in status_res.all():
            status_counts[row[0]] = row[1]
            
        # 3. Sum of victims
        victim_res = await master_db.execute(
            select(
                func.sum(GlobalReport.korban_total).label("total"),
                func.sum(GlobalReport.korban_selamat).label("selamat"),
                func.sum(GlobalReport.korban_meninggal).label("meninggal"),
                func.sum(GlobalReport.korban_hilang).label("hilang")
            )
        )
        victim_row = victim_res.one()
        victim_stats = {
            "total": victim_row.total or 0,
            "selamat": victim_row.selamat or 0,
            "meninggal": victim_row.meninggal or 0,
            "hilang": victim_row.hilang or 0
        }
        
        # 4. Count by incident type (jenis_kejadian)
        incident_counts = {}
        inc_res = await master_db.execute(
            select(GlobalReport.jenis_kejadian, func.count(GlobalReport.id))
            .where(GlobalReport.jenis_kejadian.isnot(None))
            .group_by(GlobalReport.jenis_kejadian)
        )
        for row in inc_res.all():
            incident_counts[row[0]] = row[1]
            
        # 5. Count by tenant (UPT)
        tenant_counts = {}
        tenant_res = await master_db.execute(
            select(GlobalReport.tenant_slug, func.count(GlobalReport.id)).group_by(GlobalReport.tenant_slug)
        )
        for row in tenant_res.all():
            tenant_counts[row[0]] = row[1]
            
        # 6. Fetch active tenant names for mapping slugs to UPT names
        tenant_names = {}
        tenants_res = await master_db.execute(select(Tenant.slug, Tenant.name))
        for row in tenants_res.all():
            tenant_names[row.slug] = row.name
            
        return {
            "total_reports": total_count or 0,
            "status_breakdown": status_counts,
            "victim_stats": victim_stats,
            "incident_breakdown": incident_counts,
            "tenant_breakdown": tenant_counts,
            "tenant_names": tenant_names
        }
