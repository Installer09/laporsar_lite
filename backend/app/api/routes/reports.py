from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import uuid

from app.db.session import get_db
from app.models.report import Report, ReportStatus
from app.schemas.report import ReportCreate, ReportResponse, ReportUpdate, BroadcastPayload
from app.core.security import verify_jwt, verify_admin, verify_operator_or_admin
import logging
from typing import Dict, List, Optional
from app.services.geo_service import parse_coordinates, find_nearest_location
from app.services import weather_service
from app.services.classification_service import match_classification
from app.services.message_formatter import message_formatter
from app.models.settings_models import Location, AlutPalsarTemplate
from app.models.attachment_model import Attachment
from app.services.storage_service import storage_service
from app.core.websocket import manager
import simplekml

logger = logging.getLogger(__name__)


router = APIRouter(redirect_slashes=False)

@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_operator_or_admin)])
async def create_report(
    report_in: ReportCreate, 
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new emergency report.
    Demonstrates Data Integrity using SQLAlchemy transactions.
    """
    from app.services.report_service import ReportService
    return await ReportService.create_report(report_in, db)

@router.get("", response_model=List[ReportResponse], dependencies=[Depends(verify_operator_or_admin)])
async def get_all_reports(
    cursor: Optional[int] = Query(None, description="Cursor for pagination (last seen report id)"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin-only endpoint to get all reports. Protected by Zero-Trust JWT.
    Query Optimization: Cursor-based pagination.
    """
    query = select(Report).order_by(Report.id.desc()).limit(limit)
    if cursor:
        query = query.where(Report.id < cursor)
        
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{report_id}", response_model=ReportResponse, dependencies=[Depends(verify_operator_or_admin)])
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report

@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: int, 
    report_in: ReportUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_operator_or_admin),
    request: Request = None
):
    from app.services.report_service import ReportService
    user_id_val = None
    if current_user:
        try:
            user_id_val = int(current_user.get("user_id"))
        except (ValueError, TypeError):
            user_id_val = None
    ip_address = request.client.host if request and request.client else None
    return await ReportService.update_report(
        report_id=report_id, 
        report_in=report_in, 
        db=db, 
        user_id=user_id_val, 
        ip_address=ip_address
    )

@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_admin)])
async def delete_report(report_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        
    try:
        # Delete linked attachments from storage and database first to satisfy foreign key constraints.
        attachment_result = await db.execute(select(Attachment).where(Attachment.report_id == report_id))
        attachments = attachment_result.scalars().all()
        for att in attachments:
            try:
                await storage_service.delete_file(att.file_key)
            except Exception as se:
                logger.error(f"Failed to delete file from storage for attachment {att.id}: {str(se)}")
            await db.delete(att)
            
        await db.delete(report)
        await db.commit()

        # Centralized Report Mirroring (Delete from Master DB)
        try:
            from app.services.report_sync import delete_report_from_master
            info = getattr(db, "info", None)
            tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"
            await delete_report_from_master(local_report_id=report_id, tenant_slug=tenant_slug)
        except Exception as sync_err:
            logger.warning(f"Failed to sync deleted report {report_id} to master DB: {sync_err}")

        await manager.broadcast({"event": "report_deleted", "report_id": report_id}, db=db)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete report {report_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete report")

@router.post("/{report_id}/generate-info-awal", dependencies=[Depends(verify_operator_or_admin)])
async def generate_info_awal(
    report_id: int, 
    manual_data: Dict[str, str], 
    db: AsyncSession = Depends(get_db)
):
    """
    Generate the formal Info Awal format by merging report data with manual inputs.
    Auto-enriches: HEADING, JARAK, CUACA, KLASIFIKASI, KOORDINAT.
    """
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        
    # Build data dictionary from manual operator input first
    merged_data = manual_data.copy()
    
    # Set the auto fields from the report
    merged_data["JUDUL_KEJADIAN"] = report.jenis_kejadian.upper() if report.jenis_kejadian else "DARURAT UMUM"
    merged_data["PELAPOR"] = f"{report.pelapor_nama} ({report.pelapor_nomor})"
    merged_data["WAKTU_KEJADIAN"] = report.waktu
    merged_data["LOKASI_KEJADIAN"] = report.lokasi_teks
    merged_data["KRONOLOGI"] = report.kronologi
    
    # ── Map Unsur and Alut JSON ───────────────────────────────────
    if report.unsur_alut and report.unsur_alut.startswith("{"):
        try:
            import json
            ua_data = json.loads(report.unsur_alut)
            if "unsur" in ua_data and ua_data["unsur"]:
                unsur_text = "\n".join([f"* {u.get('nama')}" for u in ua_data["unsur"] if u.get("nama")])
                if not merged_data.get("UNSUR_SAR") and unsur_text:
                    merged_data["UNSUR_SAR"] = unsur_text
            if "alut" in ua_data and ua_data["alut"]:
                alut_text = "\n".join([f"* {a.get('nama')}" for a in ua_data["alut"] if a.get("nama")])
                if not merged_data.get("ALUT_PALSAR") and alut_text:
                    merged_data["ALUT_PALSAR"] = alut_text
        except Exception as e:
            logger.warning(f"Failed to parse unsur_alut JSON: {e}")
            
    # ── Auto-enrichment pipeline ──────────────────────────────────
    
    # 1. Resolve coordinates
    lat, lon = report.koordinat_lat, report.koordinat_lng
    if not lat or not lon:
        # Try parsing from lokasi_teks
        coords = parse_coordinates(report.lokasi_teks or "")
        if coords:
            lat, lon = coords
    
    if lat and lon:
        # Set KOORDINAT field
        if not merged_data.get("KOORDINAT"):
            merged_data["KOORDINAT"] = f"{lat}°N - {lon}°E"
        
        # 2. Calculate HEADING & JARAK from nearest SAR location
        if not merged_data.get("HEADING") or not merged_data.get("JARAK"):
            try:
                loc_result = await db.execute(select(Location))
                locations = loc_result.scalars().all()
                nearest = find_nearest_location(lat, lon, locations)
                if nearest:
                    if not merged_data.get("HEADING"):
                        merged_data["HEADING"] = f"{int(nearest['heading'])}° dari {nearest['name']}"
                    if not merged_data.get("JARAK"):
                        merged_data["JARAK"] = f"{nearest['distance_nm']} Nm dari {nearest['name']}"
                    
                    # Auto-fill Unsur and Alut from the nearest location
                    if not merged_data.get("UNSUR_SAR") and nearest.get("unsur"):
                        # Convert comma separated to bullet list
                        unsur_list = [u.strip() for u in nearest["unsur"].split(",") if u.strip()]
                        merged_data["UNSUR_SAR"] = "\n".join([f"* {u}" for u in unsur_list]) if unsur_list else nearest["unsur"]
                        
                    if not merged_data.get("ALUT_PALSAR") and nearest.get("alut"):
                        alut_list = [a.strip() for a in nearest["alut"].split(",") if a.strip()]
                        merged_data["ALUT_PALSAR"] = "\n".join([f"* {a}" for a in alut_list]) if alut_list else nearest["alut"]
            except Exception as e:
                logger.warning(f"Auto heading/jarak failed: {e}")
        
        # 3. Fetch CUACA from weather API
        if not merged_data.get("CUACA"):
            try:
                weather_text = await weather_service.fetch_weather(lat, lon)
                if weather_text:
                    merged_data["CUACA"] = weather_text
            except Exception as e:
                logger.warning(f"Auto weather fetch failed: {e}")
    
    # 4. Auto-classify from database
    if not merged_data.get("KLASIFIKASI"):
        try:
            classification = await match_classification(report.jenis_kejadian or "", db)
            if classification:
                merged_data["KLASIFIKASI"] = classification
        except Exception as e:
            logger.warning(f"Auto classification failed: {e}")
    
    # ── Fetch Identity Settings from DB dynamically ──────────────────
    from app.models.settings_models import SystemSetting
    from app.api.routes.identitas import DEFAULT_IDENTITAS
    
    try:
        result_identity = await db.execute(
            select(SystemSetting).where(SystemSetting.key.in_(DEFAULT_IDENTITAS.keys()))
        )
        settings_rows = result_identity.scalars().all()
        identity_data = DEFAULT_IDENTITAS.copy()
        for setting in settings_rows:
            if setting.value is not None:
                identity_data[setting.key] = setting.value
                
        instansi = identity_data["identitas_nama_instansi"]
        motto = identity_data["identitas_motto"]
        last_word = instansi.strip().split()[-1].upper() if instansi else "NATUNA"
        ttd_kepala = f"{last_word} 01"
        
        merged_data["NAMA_INSTANSI"] = instansi
        merged_data["MOTTO_INSTANSI"] = motto
        merged_data["TTD_KEPALA"] = ttd_kepala
    except Exception as identity_err:
        logger.warning(f"Failed to fetch dynamic identity settings: {identity_err}")
    
    # ── Render the template ───────────────────────────────────────
    try:
        rendered_text = message_formatter.render(None, merged_data)
        
        # Return rendered text + auto-enriched fields for UI pre-fill
        auto_fields = {}
        for key in ["HEADING", "JARAK", "CUACA", "KLASIFIKASI", "KOORDINAT", "UNSUR_SAR", "ALUT_PALSAR"]:
            if key in merged_data and merged_data[key]:
                auto_fields[key] = merged_data[key]
        
        return {
            "status": "success", 
            "text": rendered_text,
            "auto_fields": auto_fields,
        }
    except Exception as e:
        logger.error(f"Failed to generate info awal for report {report_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate template")

async def background_kml_and_evidence(report_id: int, db_url: str):
    from app.db.session import get_tenant_sessionmaker
    from app.services.reply_dispatcher import reply_dispatcher
    from app.core.tenant_config import get_tenant_settings
    
    session_maker = get_tenant_sessionmaker(db_url)
    async with session_maker() as db:
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            return

        tenant_settings = await get_tenant_settings(db)

        # 2. Generate and Send KML
        try:
            if report.koordinat_lat is not None and report.koordinat_lng is not None:
                lat, lng = float(report.koordinat_lat), float(report.koordinat_lng)
                
                kml = simplekml.Kml()
                kml.document.name = f"Info Awal - {report.no_laporan}"
                
                # Incident point
                inc_pnt = kml.newpoint(name="Lokasi Kejadian", coords=[(lng, lat)])
                inc_pnt.description = f"Kejadian: {report.jenis_kejadian}\nKronologi: {report.kronologi}\nLokasi: {report.lokasi_teks}"
                
                # Find nearest location
                loc_result = await db.execute(select(Location))
                locations = loc_result.scalars().all()
                nearest = find_nearest_location(lat, lng, locations)
                
                if nearest and nearest.get('lat') and nearest.get('lng'):
                    n_lat, n_lng = float(nearest['lat']), float(nearest['lng'])
                    pos_pnt = kml.newpoint(name=f"Posko: {nearest['name']}", coords=[(n_lng, n_lat)])
                    
                    # LineString for distance
                    linestring = kml.newlinestring(name=f"Jarak: {nearest['distance_nm']} Nm", coords=[(n_lng, n_lat), (lng, lat)])
                    linestring.style.linestyle.color = simplekml.Color.red
                    linestring.style.linestyle.width = 3
                
                kml_str = kml.kml()
                kml_bytes = kml_str.encode('utf-8')
                kml_filename = f"Peta_Kejadian_{report.no_laporan.replace('/', '_')}.kml"
                kml_caption = f"📍 Peta Lokasi Kejadian & Garis Lurus Jarak\nBuka di aplikasi pemetaan (Google Earth/Maps) untuk melihat detail titik.\nNo: {report.no_laporan}"
                
                await reply_dispatcher.forward_file_to_telegram_sar_group(
                    kml_bytes, kml_filename, kml_caption,
                    bot_token=tenant_settings.TELEGRAM_BOT_TOKEN,
                    group_id=tenant_settings.TELEGRAM_SAR_GROUP_ID
                )
                await reply_dispatcher.forward_file_to_whatsapp_sar_group(
                    kml_bytes, kml_filename, "application/vnd.google-earth.kml+xml", kml_caption,
                    wa_token=tenant_settings.WHATSAPP_API_TOKEN,
                    phone_id=tenant_settings.WHATSAPP_PHONE_NUMBER_ID,
                    group_id=tenant_settings.WHATSAPP_SAR_GROUP_ID
                )
        except Exception as e:
            logger.error(f"Failed to generate/send KML: {e}")
            
        # 3. Send Evidence Attachments
        try:
            att_result = await db.execute(select(Attachment).where(Attachment.report_id == report_id))
            attachments = att_result.scalars().all()
            for i, att in enumerate(attachments, 1):
                file_bytes = await storage_service.download_file_bytes(att.file_key, bucket_name=att.bucket)
                if file_bytes:
                    caption = f"Eviden {i}: {att.original_filename or 'Lampiran'}\nLaporan: {report.no_laporan}"
                    await reply_dispatcher.forward_file_to_telegram_sar_group(
                        file_bytes, att.original_filename or f"Eviden_{i}", caption,
                        bot_token=tenant_settings.TELEGRAM_BOT_TOKEN,
                        group_id=tenant_settings.TELEGRAM_SAR_GROUP_ID
                    )
                    
                    mime_type = att.mime_type or "application/octet-stream"
                    await reply_dispatcher.forward_file_to_whatsapp_sar_group(
                        file_bytes, att.original_filename or f"Eviden_{i}", mime_type, caption,
                        wa_token=tenant_settings.WHATSAPP_API_TOKEN,
                        phone_id=tenant_settings.WHATSAPP_PHONE_NUMBER_ID,
                        group_id=tenant_settings.WHATSAPP_SAR_GROUP_ID
                    )
        except Exception as e:
            logger.error(f"Failed to send evidence attachments: {e}")

@router.post("/{report_id}/send-broadcast", dependencies=[Depends(verify_operator_or_admin)])
async def send_broadcast(report_id: int, payload: BroadcastPayload, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Directly broadcast a generated Info Awal text to SAR command groups (Telegram/WhatsApp).
    KML generation and evidence fetching are sent to background tasks to prevent timeouts.
    """
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        
    from app.services.reply_dispatcher import reply_dispatcher
    from app.core.tenant_config import get_tenant_settings
    
    tenant_settings = await get_tenant_settings(db)
    
    # 1. Send the Text first
    dispatch_result = await reply_dispatcher.forward_report_to_all_groups(
        payload.text,
        bot_token=tenant_settings.TELEGRAM_BOT_TOKEN,
        tg_group_id=tenant_settings.TELEGRAM_SAR_GROUP_ID,
        wa_token=tenant_settings.WHATSAPP_API_TOKEN,
        wa_phone_id=tenant_settings.WHATSAPP_PHONE_NUMBER_ID,
        wa_group_id=tenant_settings.WHATSAPP_SAR_GROUP_ID
    )
    
    # 2. Add KML and Evidence dispatch to background task
    db_url = db.bind.url.render_as_string(hide_password=False)
    background_tasks.add_task(background_kml_and_evidence, report_id, db_url)
    
    return {
        "status": "success",
        "message": "Text Broadcast sent, KML & Evidence processing in background",
        "result": dispatch_result
    }

@router.get("/tools/auto-suggestions", dependencies=[Depends(verify_operator_or_admin)])
async def get_auto_suggestions(
    lat: float,
    lng: float,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get auto-suggestions for Unsur, Alut, and Cuaca based on location and category.
    """
    suggestions = {
        "unsur": [],
        "alut": [],
        "cuaca": None
    }
    
    # 1. Get Nearest Unsur
    try:
        loc_result = await db.execute(select(Location))
        locations = loc_result.scalars().all()
        nearest = find_nearest_location(lat, lng, locations)
        if nearest:
            suggestions["unsur"].append({
                "nama": nearest["name"],
                "jarak": f"{nearest['distance_nm']} Nm",
                "is_nearest": True
            })
    except Exception as e:
        logger.warning(f"Failed to find nearest location: {e}")

    # 2. Get Alut Recommendations
    if category:
        try:
            alut_result = await db.execute(
                select(AlutPalsarTemplate).where(AlutPalsarTemplate.category.ilike(f"%{category}%"))
            )
            template = alut_result.scalar_one_or_none()
            if template and template.recommended_alut:
                aluts = [a.strip() for a in template.recommended_alut.split(",")]
                suggestions["alut"] = [{"nama": a} for a in aluts]
        except Exception as e:
            logger.warning(f"Failed to fetch alut templates: {e}")
            
    # 3. Get Weather
    try:
        weather_text = await weather_service.fetch_weather(lat, lng)
        if weather_text:
            suggestions["cuaca"] = weather_text
    except Exception as e:
        logger.warning(f"Failed to fetch weather: {e}")

    return suggestions
