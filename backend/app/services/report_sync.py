import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import MasterSessionLocal
from app.models.master_models import GlobalReport
from app.models.report import Report

logger = logging.getLogger(__name__)

async def sync_report_to_master(db: AsyncSession, report: Report, tenant_slug: str) -> None:
    """
    Synchronizes (upserts) a tenant report into the master database 'global_reports' table.
    Wrapped in try/except so that sync failures do not crash the local tenant transaction.
    """
    if not tenant_slug or tenant_slug == "global":
        return
        
    try:
        async with MasterSessionLocal() as master_db:
            # Check if global report entry already exists for this tenant & local report ID
            result = await master_db.execute(
                select(GlobalReport).where(
                    GlobalReport.tenant_slug == tenant_slug,
                    GlobalReport.local_report_id == report.id
                )
            )
            global_report = result.scalar_one_or_none()
            
            # Ensure status string conversion
            status_str = report.status.value if hasattr(report.status, 'value') else str(report.status)
            
            if not global_report:
                global_report = GlobalReport(
                    tenant_slug=tenant_slug,
                    local_report_id=report.id,
                    no_laporan=report.no_laporan,
                    pelapor_nama=report.pelapor_nama,
                    pelapor_nomor=report.pelapor_nomor,
                    jenis_kejadian=report.jenis_kejadian,
                    waktu=report.waktu,
                    lokasi_teks=report.lokasi_teks,
                    koordinat_lat=report.koordinat_lat,
                    koordinat_lng=report.koordinat_lng,
                    korban_total=report.korban_total,
                    korban_selamat=report.korban_selamat,
                    korban_meninggal=report.korban_meninggal,
                    korban_hilang=report.korban_hilang,
                    status=status_str,
                    created_at=report.created_at,
                    updated_at=report.updated_at
                )
                master_db.add(global_report)
                logger.info(f"[ReportSync] Created global report entry for {tenant_slug}/{report.no_laporan}")
            else:
                global_report.no_laporan = report.no_laporan
                global_report.pelapor_nama = report.pelapor_nama
                global_report.pelapor_nomor = report.pelapor_nomor
                global_report.jenis_kejadian = report.jenis_kejadian
                global_report.waktu = report.waktu
                global_report.lokasi_teks = report.lokasi_teks
                global_report.koordinat_lat = report.koordinat_lat
                global_report.koordinat_lng = report.koordinat_lng
                global_report.korban_total = report.korban_total
                global_report.korban_selamat = report.korban_selamat
                global_report.korban_meninggal = report.korban_meninggal
                global_report.korban_hilang = report.korban_hilang
                global_report.status = status_str
                global_report.updated_at = report.updated_at
                logger.info(f"[ReportSync] Updated global report entry for {tenant_slug}/{report.no_laporan}")
                
            await master_db.commit()
    except Exception as e:
        logger.error(f"[ReportSync] Failed to sync report {tenant_slug}/{report.no_laporan} to master DB: {e}")

async def delete_report_from_master(local_report_id: int, tenant_slug: str) -> None:
    """
    Deletes a mirrored tenant report from the master database 'global_reports' table.
    Wrapped in try/except so that sync failures do not crash the local tenant transaction.
    """
    if not tenant_slug or tenant_slug == "global":
        return
        
    try:
        async with MasterSessionLocal() as master_db:
            result = await master_db.execute(
                select(GlobalReport).where(
                    GlobalReport.tenant_slug == tenant_slug,
                    GlobalReport.local_report_id == local_report_id
                )
            )
            global_report = result.scalar_one_or_none()
            if global_report:
                await master_db.delete(global_report)
                await master_db.commit()
                logger.info(f"[ReportSync] Deleted global report entry for {tenant_slug}/local_id_{local_report_id}")
            else:
                logger.warning(f"[ReportSync] Global report entry not found for deletion: {tenant_slug}/local_id_{local_report_id}")
    except Exception as e:
        logger.error(f"[ReportSync] Failed to delete report {tenant_slug}/local_id_{local_report_id} from master DB: {e}")

