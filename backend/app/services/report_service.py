from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.exc import StaleDataError

from datetime import datetime
import json
import logging
import enum
from fastapi import HTTPException, status
from app.models.report import Report, ReportSequence, ReportStatus
from app.models.audit_log import AuditLog
from app.schemas.report import ReportCreate, ReportUpdate
from app.services.geo_service import parse_coordinates, find_nearest_location
from app.models.settings_models import Location
from app.core.websocket import manager

logger = logging.getLogger(__name__)

class ReportService:
    @staticmethod
    async def _generate_no_laporan(db: AsyncSession) -> str:
        current_date = datetime.now()
        year_month = current_date.strftime("%Y%m")
        
        # Get or create sequence for this month
        result = await db.execute(
            select(ReportSequence).where(ReportSequence.year_month == year_month).with_for_update()
        )
        seq = result.scalar_one_or_none()
        
        if not seq:
            seq = ReportSequence(year_month=year_month, last_seq=0)
            db.add(seq)
        
        seq.last_seq += 1
        return f"SAR-{year_month}-{seq.last_seq:03d}"

    @staticmethod
    async def enrich_report_geo(report: Report, db: AsyncSession):
        # Determine dynamic search radius
        if report.radius_pencarian is None:
            report.radius_pencarian = 2.0

        # Try to extract radius from chronology (e.g. "radius 3 km", "sekitar 2 kilometer", "3 mil")
        import re
        radius_extracted = None
        if report.kronologi:
            kronologi_lower = report.kronologi.lower()
            # Match "radius \d+ km" or "sekitar \d+ km" or "\d+ kilometer"
            match_km = re.search(r'(?:radius|sekitar|jarak)?\s*(\d+(?:[.,]\d+)?)\s*(?:km|kilometer)', kronologi_lower)
            if match_km:
                radius_extracted = float(match_km.group(1).replace(",", "."))
            else:
                # Match "\d+ mil" or "\d+ nautical miles" or "\d+ nm"
                match_mil = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:mil|nm|nautical\s+mile)', kronologi_lower)
                if match_mil:
                    # Convert Nautical Miles to Kilometers (1 NM = 1.852 km)
                    radius_extracted = float(match_mil.group(1).replace(",", ".")) * 1.852
        
        if radius_extracted is not None:
            report.radius_pencarian = radius_extracted
        else:
            # Automatic radius depending on terrain type (jenis_kejadian / lokasi_teks)
            jenis_lower = (report.jenis_kejadian or "").lower()
            lokasi_lower = (report.lokasi_teks or "").lower()
            
            # Check for perairan/laut/kapal (Sea terrain)
            if any(k in jenis_lower or k in lokasi_lower for k in ["kapal", "laut", "perairan", "selat", "tenggelam"]):
                report.radius_pencarian = 3.704  # 2 Nautical Miles (2 * 1.852 km)
            # Check for gunung/hutan/kmm (Land terrain)
            elif any(k in jenis_lower or k in lokasi_lower for k in ["gunung", "hutan", "bukit", "kmm", "hilang"]):
                report.radius_pencarian = 2.0
            # Check for beach/village
            else:
                report.radius_pencarian = 1.0

        lat, lon = report.koordinat_lat, report.koordinat_lng
        
        if not lat or not lon:
            coords = parse_coordinates(report.lokasi_teks or "")
            if coords:
                lat, lon = coords
                report.koordinat_lat = lat
                report.koordinat_lng = lon
                
        if lat and lon:
            try:
                loc_result = await db.execute(select(Location))
                locations = loc_result.scalars().all()
                nearest = find_nearest_location(lat, lon, locations)
                if nearest:
                    report.pos_sar_terdekat = nearest['name']
                    report.jarak_ke_lokasi = f"{nearest['distance_nm']} Nm"
                    report.heading_ke_lokasi = nearest['heading']
                    
                    if not report.unsur_alut:
                        import json
                        unsur_list = []
                        if nearest.get("unsur"):
                            unsur_list = [{"nama": u.strip()} for u in nearest["unsur"].split(",") if u.strip()]
                        alut_list = []
                        if nearest.get("alut"):
                            alut_list = [{"nama": a.strip()} for a in nearest["alut"].split(",") if a.strip()]
                        report.unsur_alut = json.dumps({
                            "unsur": unsur_list,
                            "alut": alut_list
                        })
                    
                    if not report.gmaps_link:
                        report.gmaps_link = f"https://www.google.com/maps?q={lat},{lon}"
            except Exception as e:
                logger.warning(f"Enrichment failed for report {report.no_laporan or 'new'}: {e}")

    @classmethod
    async def create_report(cls, report_in: ReportCreate, db: AsyncSession, commit: bool = True) -> Report:
        try:
            no_laporan = await cls._generate_no_laporan(db)
            
            new_report = Report(
                **report_in.model_dump(),
                no_laporan=no_laporan,
                status=ReportStatus.PENDING
            )
            
            await cls.enrich_report_geo(new_report, db)
            
            # ── Auto-Sync Contacts Database ──
            try:
                from app.models.contact import Contact
                from app.models.chat_session import ChatSession
                
                # Look for existing contact by phone number
                contact_res = await db.execute(
                    select(Contact).where(Contact.phone_number == report_in.pelapor_nomor)
                )
                existing_contact = contact_res.scalar_one_or_none()
                
                # Check for active chat session to determine channel source
                session_res = await db.execute(
                    select(ChatSession).where(
                        (ChatSession.contact_phone == report_in.pelapor_nomor) |
                        (ChatSession.user_id == f"wa_{report_in.pelapor_nomor}") |
                        (ChatSession.user_id == f"tg_{report_in.pelapor_nomor}")
                    )
                )
                chat_session = session_res.scalars().first()
                source = chat_session.channel if chat_session else "manual"
                
                if existing_contact:
                    # Update contact name if generic, last location, and notes
                    if report_in.pelapor_nama and (not existing_contact.name or existing_contact.name.startswith("WA User") or existing_contact.name.startswith("Telegram User") or existing_contact.name.startswith("User ")):
                        existing_contact.name = report_in.pelapor_nama
                    existing_contact.last_location = report_in.lokasi_teks
                    existing_contact.notes = f"Pelapor untuk laporan {no_laporan} ({report_in.jenis_kejadian})"
                    if chat_session:
                        existing_contact.source = chat_session.channel
                    logger.info(f"Contact {report_in.pelapor_nomor} updated automatically from report {no_laporan}")
                    
                    # Broadcast WS update
                    await manager.broadcast({
                        "type": "new_contact", # Trigger invalidation in frontend
                        "payload": {"id": existing_contact.id, "phone_number": existing_contact.phone_number}
                    }, db=db)
                else:
                    # Create new contact
                    new_contact = Contact(
                        phone_number=report_in.pelapor_nomor,
                        name=report_in.pelapor_nama,
                        source=source,
                        last_location=report_in.lokasi_teks,
                        notes=f"Pelapor untuk laporan {no_laporan} ({report_in.jenis_kejadian})"
                    )
                    db.add(new_contact)
                    logger.info(f"Contact {report_in.pelapor_nomor} created automatically from report {no_laporan}")
                    
                    # Broadcast WS update
                    await manager.broadcast({
                        "type": "new_contact", # Trigger invalidation in frontend
                        "payload": {"phone_number": report_in.pelapor_nomor}
                    }, db=db)
            except Exception as contact_err:
                logger.warning(f"Failed to auto-sync contact for report {no_laporan}: {contact_err}")
            
            db.add(new_report)
            if commit:
                await db.commit()
                await db.refresh(new_report)
            else:
                await db.flush()
                await db.refresh(new_report)
            
            # Centralized Report Mirroring (Sync to Master DB)
            try:
                from app.services.report_sync import sync_report_to_master
                info = getattr(db, "info", None)
                tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"
                await sync_report_to_master(db, new_report, tenant_slug)
            except Exception as sync_err:
                logger.warning(f"Failed to sync created report {no_laporan} to master DB: {sync_err}")
                
            await manager.broadcast({"event": "new_report", "report_id": new_report.id}, db=db)
            
            # Trigger continuous learning vectorization in background if committing immediately
            if commit:
                try:
                    from app.services.llm_rag import LLMRagService
                    import asyncio
                    llm_rag = LLMRagService()
                    
                    nama_kapal = None
                    if new_report.metadata_kejadian:
                        try:
                            if isinstance(new_report.metadata_kejadian, str):
                                meta_dict = json.loads(new_report.metadata_kejadian)
                            else:
                                meta_dict = new_report.metadata_kejadian
                            nama_kapal = (
                                meta_dict.get("nama_kapal")
                                or (meta_dict.get("data_kapal", {}).get("nama_kapal") if isinstance(meta_dict.get("data_kapal"), dict) else None)
                                or meta_dict.get("data_kapal")
                            )
                        except Exception:
                            pass
                    metadata = {
                        "jenis_kejadian": new_report.jenis_kejadian,
                        "nama_kapal": nama_kapal,
                        "lokasi_teks": new_report.lokasi_teks,
                        "waktu": new_report.waktu,
                        "korban_detail": new_report.korban or str(new_report.korban_total or "")
                    }
                    content_text = f"Laporan {new_report.no_laporan}: {new_report.kronologi or ''}"
                    
                    db_url = db.bind.url.render_as_string(hide_password=False)
                    
                    async def run_vectorize(target_db_url: str):
                        from app.db.session import get_tenant_sessionmaker
                        session_maker = get_tenant_sessionmaker(target_db_url)
                        async with session_maker() as bg_db:
                            await llm_rag.vectorize_report(new_report.id, content_text, metadata, bg_db)
                    
                    asyncio.create_task(run_vectorize(db_url))
                except Exception as e:
                    logger.warning(f"Failed to queue background vectorize: {e}")

            return new_report
        except Exception as e:
            await db.rollback()
            logger.error(f"Transaction failed for report creation: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create report due to internal transaction error."
            )

    @classmethod
    async def update_report(
        cls, 
        report_id: int, 
        report_in: ReportUpdate, 
        db: AsyncSession,
        user_id: int = None,
        ip_address: str = None
    ) -> Report:
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        
        update_data = report_in.model_dump(exclude_unset=True)
        
        status_changed = False
        old_status = report.status
        new_status = None
        if 'status' in update_data:
            try:
                new_status = ReportStatus(update_data['status'].upper())
                if new_status != old_status:
                    status_changed = True
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value")

        # Capture state before modifications for audit trail
        before_state = {}
        after_state = {}
        for field in update_data.keys():
            val = getattr(report, field, None)
            before_state[field] = val

        for field, value in update_data.items():
            setattr(report, field, value)
            after_state[field] = value
            
        if 'koordinat_lat' in update_data or 'koordinat_lng' in update_data or 'lokasi_teks' in update_data:
            await cls.enrich_report_geo(report, db)
            
        # Helper to serialize values to JSON-friendly format
        def serialize_state(state):
            serializable = {}
            for k, v in state.items():
                if hasattr(v, "value"): # Enum
                    serializable[k] = v.value
                elif isinstance(v, datetime):
                    serializable[k] = v.isoformat()
                else:
                    serializable[k] = v
            return serializable

        # Create audit log record
        audit = AuditLog(
            user_id=user_id,
            action="UPDATE_REPORT",
            target_id=str(report.id),
            before_state=serialize_state(before_state),
            after_state=serialize_state(after_state),
            ip_address=ip_address
        )
        db.add(audit)

        try:
            await db.commit()
            await db.refresh(report)
            
            # Centralized Report Mirroring (Sync to Master DB)
            try:
                from app.services.report_sync import sync_report_to_master
                info = getattr(db, "info", None)
                tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"
                await sync_report_to_master(db, report, tenant_slug)
            except Exception as sync_err:
                logger.warning(f"Failed to sync updated report {report.no_laporan} to master DB: {sync_err}")
                
            await manager.broadcast({"event": "report_updated", "report_id": report.id}, db=db)
            
            # Trigger continuous learning vectorization in background
            try:
                from app.services.llm_rag import LLMRagService
                import asyncio
                llm_rag = LLMRagService()
                
                nama_kapal = None
                if report.metadata_kejadian:
                    try:
                        if isinstance(report.metadata_kejadian, str):
                            meta_dict = json.loads(report.metadata_kejadian)
                        else:
                            meta_dict = report.metadata_kejadian
                        nama_kapal = (
                            meta_dict.get("nama_kapal")
                            or (meta_dict.get("data_kapal", {}).get("nama_kapal") if isinstance(meta_dict.get("data_kapal"), dict) else None)
                            or meta_dict.get("data_kapal")
                        )
                    except Exception:
                        pass
                metadata = {
                    "jenis_kejadian": report.jenis_kejadian,
                    "nama_kapal": nama_kapal,
                    "lokasi_teks": report.lokasi_teks,
                    "waktu": report.waktu,
                    "korban_detail": report.korban or str(report.korban_total or "")
                }
                content_text = f"Laporan {report.no_laporan}: {report.kronologi or ''}"
                
                db_url = db.bind.url.render_as_string(hide_password=False)
                
                async def run_vectorize(target_db_url: str):
                    from app.db.session import get_tenant_sessionmaker
                    session_maker = get_tenant_sessionmaker(target_db_url)
                    async with session_maker() as bg_db:
                        await llm_rag.vectorize_report(report.id, content_text, metadata, bg_db)
                
                asyncio.create_task(run_vectorize(db_url))
            except Exception as e:
                logger.warning(f"Failed to queue background vectorize: {e}")
            
            # Send proactive notification if status changed
            if status_changed:
                try:
                    from app.models.chat_session import ChatSession
                    from app.services.reply_dispatcher import reply_dispatcher
                    from app.core.tenant_config import get_tenant_settings
                    
                    tenant_settings = await get_tenant_settings(db)
                    
                    # Find chat sessions for this reporter
                    session_res = await db.execute(
                        select(ChatSession).where(
                            (ChatSession.contact_phone == report.pelapor_nomor) |
                            (ChatSession.user_id == f"wa_{report.pelapor_nomor}") |
                            (ChatSession.user_id == f"tg_{report.pelapor_nomor}")
                        )
                    )
                    chat_sessions = session_res.scalars().all()
                    
                    if chat_sessions:
                        # Construct proactive notification message
                        status_friendly = {
                            ReportStatus.PENDING: "🕒 *PENDING* (Sedang Diverifikasi oleh Petugas Piket)",
                            ReportStatus.AKTIF: "🔴 *AKTIF* (Operasi SAR Sedang Berlangsung)",
                            ReportStatus.TIDAK_AKTIF: "🟢 *TIDAK AKTIF / SELESAI* (Operasi SAR Telah Ditutup)",
                            ReportStatus.SALAH_LAPORAN: "⚠️ *BATAL / DUPLIKAT* (Laporan Selesai/Dibatalkan)"
                        }
                        
                        status_text = status_friendly.get(new_status, f"❓ *{new_status.value}*")
                        pos_sar = report.pos_sar_terdekat or "Kantor Pencarian dan Pertolongan Natuna"
                        
                        notification_msg = (
                            "🔔 *PEMBARUAN STATUS OPERASI SAR* 🔔\n\n"
                            "Yth. Bapak/Ibu pelapor, status laporan musibah Anda telah diperbarui oleh operator Command Center BASARNAS.\n\n"
                            f"• *No Laporan:* `{report.no_laporan}`\n"
                            f"• *Jenis Musibah:* {report.jenis_kejadian or 'Darurat Umum'}\n"
                            f"• *Unit Penanganan:* {pos_sar}\n"
                            f"• *Status Terbaru:* {status_text}\n\n"
                            "━━━━━━━━━━━━━━━━━━━━━\n"
                            "Petugas kami akan terus melakukan penanganan terbaik. Terima kasih atas kerja sama Anda."
                        )
                        
                        buttons = ["Buat Laporan Baru", "Cek Status Laporan"]
                        
                        # Dispatch based on channel
                        for chat_session in chat_sessions:
                            if chat_session.channel == "whatsapp":
                                await reply_dispatcher.send_whatsapp_reply(
                                    recipient_phone=report.pelapor_nomor,
                                    text=notification_msg,
                                    buttons=buttons,
                                    wa_token=tenant_settings.WHATSAPP_API_TOKEN,
                                    phone_id=tenant_settings.WHATSAPP_PHONE_NUMBER_ID
                                )
                                logger.info(f"Proactive WhatsApp status update sent to {report.pelapor_nomor} for report {report.no_laporan}")
                            elif chat_session.channel == "telegram":
                                telegram_chat_id = chat_session.user_id
                                if telegram_chat_id.startswith("tg_"):
                                    telegram_chat_id = telegram_chat_id[3:]
                                await reply_dispatcher.send_telegram_reply(
                                    chat_id=telegram_chat_id,
                                    text=notification_msg,
                                    buttons=buttons,
                                    bot_token=tenant_settings.TELEGRAM_BOT_TOKEN
                                )
                                logger.info(f"Proactive Telegram status update sent to chat_id {telegram_chat_id} for report {report.no_laporan}")
                except Exception as notify_err:
                    logger.error(f"Failed to send proactive notification for report {report.no_laporan}: {str(notify_err)}")
            
            return report
        except StaleDataError as stale_err:
            await db.rollback()
            logger.warning(f"Optimistic lock conflict detected on report {report_id} by user {user_id}: {stale_err}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Laporan telah diperbarui oleh operator lain. Silakan muat ulang halaman."
            )
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update report {report_id}: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update report")
