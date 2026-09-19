from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json
import logging
from typing import List, Dict, Any
import redis.asyncio as redis_client

from app.db.session import get_master_db, get_tenant_sessionmaker, get_redis
from app.models.master_models import Tenant
from app.models.report import Report
from app.models.settings_models import SystemSetting, Location

logger = logging.getLogger(__name__)
router = APIRouter(redirect_slashes=False)

CACHE_KEY = "public_map_data"
CACHE_TTL = 300  # 5 minutes

@router.get("/reports/map", response_model=List[Dict[str, Any]])
async def get_public_map_reports(
    db_master: AsyncSession = Depends(get_master_db),
    redis: redis_client.Redis = Depends(get_redis)
):
    """
    Fetch aggregated active incident reports from all tenants for the public map.
    Uses Redis cache to prevent database connection bottlenecks.
    """
    # 1. Try reading from cache
    try:
        cached_data = await redis.get(CACHE_KEY)
        if cached_data:
            logger.info("Serving aggregated public map reports from Redis cache")
            return json.loads(cached_data)
    except Exception as cache_err:
        logger.warning(f"Failed to read from Redis cache: {cache_err}")

    # 2. Cache miss -> aggregate from all active tenants
    logger.info("Cache miss: aggregating public map reports from all tenants")
    
    # Query active tenants
    try:
        result = await db_master.execute(
            select(Tenant).where(Tenant.is_active == True)
        )
        tenants = result.scalars().all()
    except Exception as e:
        logger.error(f"Failed to query tenants from master DB: {e}")
        raise HTTPException(status_code=500, detail="Gagal mengambil data instansi master.")

    async def fetch_tenant_reports(tenant) -> list:
        reports = []
        try:
            session_maker = get_tenant_sessionmaker(tenant.db_url)
            async with session_maker() as tenant_db:
                stmt = select(
                    Report.id,
                    Report.no_laporan,
                    Report.jenis_kejadian,
                    Report.koordinat_lat,
                    Report.koordinat_lng,
                    Report.status,
                    Report.pos_sar_terdekat,
                    Report.created_at,
                    Report.lokasi_teks,
                    Report.waktu,
                    Report.korban,
                    Report.korban_total
                ).where(
                    Report.status.in_(["AKTIF", "PENDING"]),
                    Report.koordinat_lat != None,
                    Report.koordinat_lng != None
                )
                
                rep_result = await tenant_db.execute(stmt)
                rows = rep_result.all()
                
                for row in rows:
                    reports.append({
                        "id": row.id,
                        "no_laporan": row.no_laporan,
                        "jenis_kejadian": row.jenis_kejadian,
                        "koordinat_lat": row.koordinat_lat,
                        "koordinat_lng": row.koordinat_lng,
                        "status": row.status,
                        "pos_sar_terdekat": row.pos_sar_terdekat,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "lokasi_teks": row.lokasi_teks,
                        "waktu": row.waktu,
                        "korban": row.korban,
                        "korban_total": row.korban_total,
                        "tenant_name": tenant.name,
                        "tenant_slug": tenant.slug
                    })
        except Exception as tenant_err:
            logger.error(f"Failed to fetch reports from tenant {tenant.slug}: {tenant_err}")
        return reports

    import asyncio
    results = await asyncio.gather(*[fetch_tenant_reports(tenant) for tenant in tenants])
    
    aggregated_reports = []
    for r in results:
        aggregated_reports.extend(r)

    # 3. Write to cache
    try:
        await redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(aggregated_reports))
        logger.info("Successfully wrote aggregated reports to Redis cache")
    except Exception as cache_write_err:
        logger.warning(f"Failed to write to Redis cache: {cache_write_err}")

    return aggregated_reports


TENANTS_CACHE_KEY = "cache:public_tenants"
TENANTS_CACHE_TTL = 300  # 5 minutes

@router.get("/tenants", response_model=List[Dict[str, Any]])
async def get_active_tenants(
    db_master: AsyncSession = Depends(get_master_db),
    redis: redis_client.Redis = Depends(get_redis)
):
    """
    Fetch list of all active tenants (workspaces) with details for card UI and dropdown.
    Cached in Redis to eliminate per-tenant database connection storms.
    """
    try:
        if redis and hasattr(redis, "get"):
            cached_data = await redis.get(TENANTS_CACHE_KEY)
            if cached_data:
                logger.info("Serving active tenants from Redis cache")
                return json.loads(cached_data)
    except Exception as cache_err:
        logger.warning(f"Failed to read tenants from Redis: {cache_err}")

    try:
        result = await db_master.execute(
            select(Tenant).where(Tenant.is_active == True).order_by(Tenant.name)
        )
        tenants = result.scalars().all()
        
        async def fetch_tenant_details(tenant) -> dict:
            logo_path = ""
            address = "Wilayah Operasional"
            wa_phone = ""
            fallback_phone = ""
            lat = None
            lng = None
            
            try:
                session_maker = get_tenant_sessionmaker(tenant.db_url)
                async with session_maker() as tenant_db:
                    res = await tenant_db.execute(
                        select(SystemSetting).where(
                            SystemSetting.key.in_([
                                "identitas_logo_path", 
                                "identitas_wilayah_kerja", 
                                "wa_phone_number",
                                "fallback_phone"
                            ])
                        )
                    )
                    settings = res.scalars().all()
                    for setting in settings:
                        if setting.key == "identitas_logo_path" and setting.value:
                            logo_path = setting.value
                        elif setting.key == "identitas_wilayah_kerja" and setting.value:
                            address = setting.value
                        elif setting.key == "wa_phone_number" and setting.value:
                            wa_phone = setting.value
                        elif setting.key == "fallback_phone" and setting.value:
                            fallback_phone = setting.value
                            
                    # Query UPT location coordinates
                    loc_res = await tenant_db.execute(
                        select(Location).where(Location.type.ilike("%Kantor%")).limit(1)
                    )
                    kantor_loc = loc_res.scalar_one_or_none()
                    if kantor_loc:
                        lat = kantor_loc.lat
                        lng = kantor_loc.lng
            except Exception as err:
                logger.error(f"Failed to fetch details for tenant {tenant.slug}: {err}")
            
            # Fallback hierarchy for telephone
            if not fallback_phone:
                fallback_phone = tenant.admin_phone or wa_phone or "115"
            
            # Build WhatsApp link
            wa_link = ""
            if wa_phone:
                import re
                import urllib.parse
                clean_phone = re.sub(r"\D", "", wa_phone)
                if clean_phone.startswith("0"):
                    clean_phone = "62" + clean_phone[1:]
                
                greeting_text = "Halo SARBot, saya ingin melaporkan kejadian darurat."
                encoded_text = urllib.parse.quote(greeting_text)
                wa_link = f"https://wa.me/{clean_phone}?text={encoded_text}"
                
            return {
                "name": tenant.name,
                "slug": tenant.slug,
                "logo_path": logo_path,
                "address": address,
                "wa_phone": wa_phone,
                "wa_link": wa_link,
                "fallback_phone": fallback_phone,
                "lat": lat,
                "lng": lng
            }

        import asyncio
        results = await asyncio.gather(*[fetch_tenant_details(t) for t in tenants])
        
        try:
            if redis and hasattr(redis, "setex"):
                await redis.setex(TENANTS_CACHE_KEY, TENANTS_CACHE_TTL, json.dumps(results))
        except Exception as cache_write_err:
            logger.warning(f"Failed to write tenants to Redis: {cache_write_err}")

        return results
    except Exception as e:
        logger.error(f"Failed to fetch active tenants: {e}")
        raise HTTPException(status_code=500, detail="Gagal mengambil data instansi.")
