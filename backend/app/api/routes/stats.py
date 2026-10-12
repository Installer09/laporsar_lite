"""
Dashboard Stats Endpoint
========================
Aggregates real-time metrics from multiple tables to power the
Dashboard Overview cards. Single round-trip for the frontend.
"""

import json
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

from app.db.session import get_db, get_redis
from app.core.security import verify_jwt
from app.models.report import Report, ReportStatus
from app.models.settings_models import Location
from app.models.knowledge_models import SOPDocument, SOPDocStatus, DictionaryWord
from app.models.contact import Contact

router = APIRouter(redirect_slashes=False)

def format_trend(current: int, previous: int) -> str:
    if previous == 0:
        if current == 0:
            return "0% minggu ini"
        return f"+{current * 100}% minggu ini"
    
    change = current - previous
    percent = (change / previous) * 100
    sign = "+" if change > 0 else ""
    return f"{sign}{percent:.0f}% minggu ini"

@router.get("", dependencies=[Depends(verify_jwt)])
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """
    Return aggregated dashboard metrics in a single query.
    Cached in Redis for 30s.
    """
    tenant_slug = db.info.get("tenant_slug", "default") if hasattr(db, "info") and isinstance(db.info, dict) else "default"
    cache_key = f"cache:stats:{tenant_slug}"

    try:
        if redis and hasattr(redis, "get"):
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
    except Exception as e:
        logger.warning(f"Failed to read stats from Redis cache: {e}")

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)
    
    # Today's start in UTC
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    from sqlalchemy import case

    # 1. Consolidated Report Queries
    report_stmt = select(
        func.count(Report.id).label("total_laporan"),
        func.count(case((Report.status == ReportStatus.AKTIF, 1))).label("laporan_aktif"),
        func.count(case(((Report.status == ReportStatus.AKTIF) & (Report.created_at >= seven_days_ago), 1))).label("aktif_this_week"),
        func.count(case(((Report.status == ReportStatus.AKTIF) & (Report.created_at >= fourteen_days_ago) & (Report.created_at < seven_days_ago), 1))).label("aktif_last_week"),
        func.count(case((Report.created_at >= seven_days_ago, 1))).label("total_this_week"),
        func.count(case(((Report.created_at >= fourteen_days_ago) & (Report.created_at < seven_days_ago), 1))).label("total_last_week"),
        func.count(case((Report.created_at >= today_start, 1))).label("total_today"),
        func.count(case((Report.status == ReportStatus.PENDING, 1))).label("pending_validation"),
        func.count(case((Report.status.in_([ReportStatus.TIDAK_AKTIF, ReportStatus.SALAH_LAPORAN]), 1))).label("inactive_or_false_reports")
    )

    # 2. Consolidated SOP Doc Queries
    doc_stmt = select(
        func.count(SOPDocument.id).label("total_docs"),
        func.count(case((SOPDocument.status == SOPDocStatus.INDEXED, 1))).label("indexed_docs")
    )

    # Execute all queries sequentially on the AsyncSession connection
    res_reports = await db.execute(report_stmt)
    res_pos = await db.execute(select(func.count(Location.id)).where(Location.type.ilike("%Pos%")))
    res_docs = await db.execute(doc_stmt)
    res_contacts = await db.execute(select(func.count(Contact.id)))
    res_dict = await db.execute(select(func.count(DictionaryWord.id)))

    # Parse results
    rep_row = res_reports.fetchone()
    total_laporan = rep_row.total_laporan or 0
    laporan_aktif = rep_row.laporan_aktif or 0
    aktif_this_week = rep_row.aktif_this_week or 0
    aktif_last_week = rep_row.aktif_last_week or 0
    total_this_week = rep_row.total_this_week or 0
    total_last_week = rep_row.total_last_week or 0
    total_today = rep_row.total_today or 0
    pending_validation = rep_row.pending_validation or 0
    inactive_or_false_reports = rep_row.inactive_or_false_reports or 0

    pos_sar_siaga = res_pos.scalar_one() or 0

    doc_row = res_docs.fetchone()
    total_docs = doc_row.total_docs or 0
    indexed_docs = doc_row.indexed_docs or 0

    total_contacts = res_contacts.scalar_one() or 0
    total_knowledge = res_dict.scalar_one() or 0

    # Calculate trends
    trend_laporan_aktif = format_trend(aktif_this_week, aktif_last_week)
    trend_total_laporan = format_trend(total_this_week, total_last_week)

    # RAG Accuracy
    if total_docs > 0:
        akurasi_rag = round((indexed_docs / total_docs) * 100)
    else:
        akurasi_rag = None

    result_data = {
        "laporan_aktif": laporan_aktif,
        "trend_laporan_aktif": trend_laporan_aktif,
        "total_laporan": total_laporan,
        "trend_total_laporan": trend_total_laporan,
        "pos_sar_siaga": pos_sar_siaga,
        "akurasi_rag": akurasi_rag,
        
        # UI Mapped Fields
        "total_today": total_today,
        "pending_validation": pending_validation,
        "total_contacts": total_contacts,
        "total_knowledge": total_knowledge,
        "inactive_or_false_reports": inactive_or_false_reports,
        
        "model_version": "Model v2.5",
        "meta": {
            "total_docs": total_docs,
            "indexed_docs": indexed_docs,
        }
    }

    try:
        if redis and hasattr(redis, "setex"):
            await redis.setex(cache_key, 30, json.dumps(result_data))
    except Exception as e:
        logger.warning(f"Failed to write stats to Redis cache: {e}")

    return result_data
