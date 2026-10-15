import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.reply_dispatcher import reply_dispatcher
from app.services.report_service import ReportService
from app.services.message_formatter import message_formatter

logger = logging.getLogger(__name__)

class ActionHandler:
    """Handles terminal actions like saving reports and sending broadcasts."""
    
    def __init__(self):
        self.report_service = ReportService()

    def _parse_metadata_string(self, text: str, mode: str) -> dict:
        """Parses a multi-line string with Key: Value format into a standard dictionary."""
        if not text:
            return text
        if not isinstance(text, str):
            return text
        
        parsed_dict = {}
        for line in text.split("\n"):
            if ":" in line:
                k, v = [part.strip() for part in line.split(":", 1)]
                k_lower = k.lower()
                if mode == "kapal":
                    if "nama" in k_lower:
                        parsed_dict["nama_kapal"] = v
                    elif "jenis" in k_lower or "kapal" in k_lower:
                        parsed_dict["jenis_kapal"] = v
                    elif "warna" in k_lower:
                        parsed_dict["warna_kapal"] = v
                    elif "imo" in k_lower:
                        parsed_dict["imo"] = v
                    elif "call" in k_lower:
                        parsed_dict["call_sign"] = v
                    elif "satelit" in k_lower or "telp" in k_lower or "telepon" in k_lower:
                        parsed_dict["telepon_satelit"] = v
                elif mode == "pesawat":
                    if "nama" in k_lower:
                        parsed_dict["nama_pesawat"] = v
                    elif "jenis" in k_lower or "pesawat" in k_lower:
                        parsed_dict["jenis_pesawat"] = v
                    elif "warna" in k_lower:
                        parsed_dict["warna_pesawat"] = v
                    elif "register" in k_lower or "call" in k_lower:
                        parsed_dict["register"] = v
                    elif "rute" in k_lower:
                        parsed_dict["rute"] = v
                    elif "operator" in k_lower:
                        parsed_dict["operator"] = v
                elif mode == "alat":
                    if "jenis" in k_lower or "kendaraan" in k_lower or "alat" in k_lower:
                        parsed_dict["jenis_kendaraan"] = v
                    elif "warna" in k_lower:
                        parsed_dict["warna_kendaraan"] = v
                    elif "nopol" in k_lower or "polisi" in k_lower:
                        parsed_dict["nopol"] = v
                    elif "pemilik" in k_lower:
                        parsed_dict["pemilik"] = v
        
        # Fallback if no keys were successfully parsed
        if not parsed_dict:
            if mode == "kapal":
                parsed_dict = {"nama_kapal": "-", "jenis_kapal": text.strip(), "warna_kapal": "-", "imo": "-", "call_sign": "-", "telepon_satelit": "-"}
            elif mode == "pesawat":
                parsed_dict = {"nama_pesawat": "-", "jenis_pesawat": text.strip(), "warna_pesawat": "-", "register": "-", "rute": "-", "operator": "-"}
            elif mode == "alat":
                parsed_dict = {"jenis_kendaraan": text.strip(), "warna_kendaraan": "-", "nopol": "-", "pemilik": "-"}
                
        return parsed_dict

    async def complete_report(self, session_data: dict, db: AsyncSession):
        """Builds final info awal, saves to SQLite DB via ReportService, and forwards to SAR groups."""
        logger.info(f"Report completed for {session_data.get('user_id')}")
        
        from app.core.tenant_config import get_tenant_settings
        tenant_settings = await get_tenant_settings(db)
        
        extracted = session_data.get("extracted_data") or {}
        
        # 1. Clean/prepare fields for Pydantic ReportCreate validation
        pelapor_nama = extracted.get("pelapor_nama") or extracted.get("contact_name") or "Pelapor SARBot"
        if len(pelapor_nama) < 2:
            pelapor_nama = pelapor_nama + " "
        pelapor_nama = pelapor_nama[:100]
        
        pelapor_nomor = extracted.get("pelapor_hp") or extracted.get("contact_phone") or "08123456789"
        
        # Zero-Trust phone formatting cleanup
        import re
        pelapor_nomor = re.sub(r'[^\d\+\-\s]', '', pelapor_nomor)
        if not re.match(r'^[\+\d\-\s]{8,20}$', pelapor_nomor):
            pelapor_nomor = "08123456789"
            
        # Resolve classification based on ship/vehicle usage and match with DB
        pakai_kapal = extracted.get("pakai_kapal")
        prev_jenis = extracted.get("jenis_kejadian") or "KMM"
        
        # If the user answered "Apakah menggunakan kapal"
        if pakai_kapal == "Ya":
            # If it's a ship/vessel context, it is a ship accident (Kecelakaan Kapal)
            if prev_jenis in ("KMM", "Kondisi Membahayakan Manusia", "Kecelakaan Kapal", "Laka Kapal"):
                jenis_kejadian_resolved = "Kecelakaan Kapal"
            else:
                jenis_kejadian_resolved = prev_jenis
        elif pakai_kapal == "Tidak":
            # If they did not use a vessel, it is a KMM (Kondisi Membahayakan Manusia)
            if prev_jenis in ("KMM", "Kondisi Membahayakan Manusia", "Kecelakaan Kapal", "Laka Kapal"):
                jenis_kejadian_resolved = "Kondisi Membahayakan Manusia"
            else:
                jenis_kejadian_resolved = prev_jenis
        else:
            jenis_kejadian_resolved = prev_jenis
            
        # Match with DB classifications table to ensure perfect name match
        from app.services.classification_service import match_classification
        from app.models.settings_models import Classification
        from sqlalchemy.future import select
        from sqlalchemy import func
        
        jenis_kejadian = "Kondisi Membahayakan Manusia"
        try:
            matched = await match_classification(jenis_kejadian_resolved, db)
            if matched:
                # Query the exact title case category name from DB
                res_cls = await db.execute(select(Classification).where(func.upper(Classification.category) == matched.upper()))
                cls_obj = res_cls.scalar_one_or_none()
                if hasattr(cls_obj, "category") and isinstance(cls_obj.category, str):
                    jenis_kejadian = cls_obj.category
                else:
                    jenis_kejadian = matched.title()
            elif jenis_kejadian_resolved:
                jenis_kejadian = jenis_kejadian_resolved
        except Exception as e:
            logger.warning(f"Failed to match database classification for {jenis_kejadian_resolved}: {e}")
            if jenis_kejadian_resolved in ("KMM", "Kondisi Membahayakan Manusia"):
                jenis_kejadian = "Kondisi Membahayakan Manusia"
            elif jenis_kejadian_resolved in ("Kecelakaan Kapal", "Laka Kapal"):
                jenis_kejadian = "Kecelakaan Kapal"
            else:
                jenis_kejadian = jenis_kejadian_resolved or "Kondisi Membahayakan Manusia"
            
        jenis_kejadian = jenis_kejadian[:50]
        waktu = (extracted.get("waktu") or "Tidak diketahui")[:50]
        lokasi_teks = (extracted.get("lokasi_teks") or "Tidak diketahui")[:255]
        korban = (extracted.get("korban") or "Tidak diketahui")[:255]
        kronologi = extracted.get("kronologi") or "Tidak diketahui"
        
        # Coordinates parsing
        lat = None
        lng = None
        try:
            lat_val = extracted.get("koordinat_lat")
            lng_val = extracted.get("koordinat_lng")
            if lat_val is not None:
                lat = float(lat_val)
            if lng_val is not None:
                lng = float(lng_val)
        except (ValueError, TypeError):
            pass
            
        # Reporter coordinates parsing
        pelapor_lat = None
        pelapor_lng = None
        try:
            p_lat = extracted.get("pelapor_lat")
            p_lng = extracted.get("pelapor_lng")
            if p_lat is not None:
                pelapor_lat = float(p_lat)
            if p_lng is not None:
                pelapor_lng = float(p_lng)
        except (ValueError, TypeError):
            pass
            
        # Victims count
        korban_total = None
        korban_selamat = None
        korban_meninggal = None
        korban_hilang = None
        try:
            korban_s = int(extracted.get("korban_s", 0))
            korban_md = int(extracted.get("korban_md", 0))
            korban_dp = int(extracted.get("korban_dp", 0))
            
            # Extract total from korban string if not calculated
            k_tot = None
            if extracted.get("korban"):
                k_val = str(extracted.get("korban")).lower()
                for k_word, k_num in [("satu", 1), ("dua", 2), ("tiga", 3), ("empat", 4), ("lima", 5), ("enam", 6), ("tujuh", 7), ("delapan", 8), ("sembilan", 9), ("sepuluh", 10), ("berdua", 2), ("bertiga", 3), ("berempat", 4), ("berlima", 5), ("berenam", 6), ("bertujuh", 7), ("berdelapan", 8), ("bersembilan", 9), ("bersepuluh", 10)]:
                    if k_word in k_val:
                        k_tot = k_num
                        break
                if not k_tot:
                    digits = re.findall(r'\d+', k_val)
                    if digits:
                        k_tot = int(digits[0])
            if not k_tot and extracted.get("korban_total"):
                try:
                    k_tot = int(extracted.get("korban_total"))
                except:
                    pass
                
            total_calc = (korban_s or 0) + (korban_md or 0) + (korban_dp or 0)
            
            if total_calc == 0 and k_tot and k_tot > 0:
                # If no breakdown is provided, automatically assign all as DP (Dalam Pencarian)
                korban_dp = k_tot
                total_calc = k_tot
                
            korban_selamat = korban_s if korban_s > 0 else None
            korban_meninggal = korban_md if korban_md > 0 else None
            korban_hilang = korban_dp if korban_dp > 0 else None
            
            if total_calc > 0:
                korban_total = total_calc
        except (ValueError, TypeError):
            pass

        # Prepare victim detail dict
        raw_data_korban = extracted.get("data_korban", [])
        data_korban_payload = None
        if isinstance(raw_data_korban, list) and raw_data_korban:
            data_korban_payload = {"daftar_korban": raw_data_korban}
        elif isinstance(raw_data_korban, dict):
            data_korban_payload = raw_data_korban
        elif isinstance(raw_data_korban, str) and raw_data_korban.strip():
            try:
                from app.services.llm_rag import LLMRagService
                llm_rag = LLMRagService()
                parsed_list = await llm_rag.parse_data_korban(raw_data_korban)
                if parsed_list:
                    data_korban_payload = {"daftar_korban": parsed_list}
                else:
                    data_korban_payload = {"daftar_korban": [{"nama": raw_data_korban.strip(), "jenis_kelamin": "-", "umur": "-", "alamat": "-", "no_hp": "-", "ciri_ciri": "-"}]}
            except Exception as e:
                logger.error(f"Failed to parse raw_data_korban in ActionHandler: {e}")
                data_korban_payload = {"daftar_korban": [{"nama": raw_data_korban.strip(), "jenis_kelamin": "-", "umur": "-", "alamat": "-", "no_hp": "-", "ciri_ciri": "-"}]}


        # Parse vessel / vehicle metadata payload
        raw_kapal = extracted.get("data_kapal")
        raw_pesawat = extracted.get("data_pesawat")
        raw_alat = extracted.get("data_alat")
        
        data_kapal_payload = self._parse_metadata_string(raw_kapal, "kapal")
        data_pesawat_payload = self._parse_metadata_string(raw_pesawat, "pesawat")
        data_alat_payload = self._parse_metadata_string(raw_alat, "alat")

        # Build ReportCreate
        from app.schemas.report import ReportCreate
        report_in = ReportCreate(
            pelapor_nama=pelapor_nama,
            pelapor_nomor=pelapor_nomor,
            pelapor_lat=pelapor_lat,
            pelapor_lng=pelapor_lng,
            jenis_kejadian=jenis_kejadian,
            waktu=waktu,
            lokasi_teks=lokasi_teks,
            koordinat_lat=lat,
            koordinat_lng=lng,
            korban=korban,
            korban_total=korban_total,
            korban_selamat=korban_selamat,
            korban_meninggal=korban_meninggal,
            korban_hilang=korban_hilang,
            data_korban=data_korban_payload,
            kronologi=kronologi,
            metadata_kejadian={
                "data_kapal": data_kapal_payload,
                "data_pesawat": data_pesawat_payload,
                "data_alat": data_alat_payload,
                "koordinat_teks": extracted.get("koordinat"),
                "reporter_user_id": session_data.get("user_id")
            }
        )
        
        # 2. Save report to DB using the ReportService (do not commit yet)
        saved_report = await self.report_service.create_report(report_in, db, commit=False)
        
        # ── Attachment Linking & Forwarding ──
        user_id = session_data.get("user_id")
        if user_id:
            try:
                from sqlalchemy.future import select
                from app.models.attachment_model import Attachment
                from app.services.storage_service import storage_service
                
                result = await db.execute(
                    select(Attachment).where(
                        Attachment.user_id == user_id,
                        Attachment.report_id == None
                    )
                )
                unlinked_attachments = result.scalars().all()
                if isinstance(unlinked_attachments, list) and unlinked_attachments:
                    for att in unlinked_attachments:
                        att.report_id = saved_report.id
                        db.add(att)
                    await db.flush()
                    logger.info(f"Linked {len(unlinked_attachments)} attachments to report {saved_report.no_laporan}")
                    
                    for att in unlinked_attachments:
                        try:
                            file_bytes = await storage_service.download_file_bytes(att.file_key, bucket_name=att.bucket)
                            if file_bytes:
                                caption = f"*Lampiran Bukti Kejadian ({att.original_filename or 'Dokumen'})*\nLaporan No: {saved_report.no_laporan}"
                                
                                # Forward to Telegram SAR Group
                                await reply_dispatcher.forward_file_to_telegram_sar_group(
                                    file_bytes=file_bytes,
                                    filename=att.original_filename or "attachment",
                                    caption=caption,
                                    bot_token=tenant_settings.TELEGRAM_BOT_TOKEN,
                                    group_id=tenant_settings.TELEGRAM_SAR_GROUP_ID
                                )
                                
                                # Forward to WhatsApp SAR Group
                                await reply_dispatcher.forward_file_to_whatsapp_sar_group(
                                    file_bytes=file_bytes,
                                    filename=att.original_filename or "attachment",
                                    mime_type=att.mime_type or "application/octet-stream",
                                    caption=caption,
                                    wa_token=tenant_settings.WHATSAPP_API_TOKEN,
                                    phone_id=tenant_settings.WHATSAPP_PHONE_NUMBER_ID,
                                    group_id=tenant_settings.WHATSAPP_SAR_GROUP_ID
                                )
                                logger.info(f"Forwarded attachment {att.file_key} to SAR Groups.")
                            else:
                                logger.warning(f"Downloaded empty bytes for attachment key: {att.file_key}")
                        except Exception as forward_err:
                            logger.error(f"Failed to forward attachment {att.file_key}: {forward_err}")
            except Exception as att_err:
                logger.error(f"Failed to link or forward attachments: {att_err}")
        
        # ── KML & Attachment Dispatcher (Phase 2 integration) ──
        if saved_report.koordinat_lat and saved_report.koordinat_lng:
            try:
                import os
                from app.services.kml_generator import generate_incident_kml
                from app.models.settings_models import Location
                from sqlalchemy.future import select
                
                nearest_post_name = saved_report.pos_sar_terdekat
                nearest_post_lat = None
                nearest_post_lng = None
                
                if nearest_post_name:
                    loc_result = await db.execute(
                        select(Location).where(Location.name == nearest_post_name)
                    )
                    nearest_post = loc_result.scalars().first()
                    if nearest_post:
                        nearest_post_lat = nearest_post.lat
                        nearest_post_lng = nearest_post.lng
                
                # output directory under project root/uploads
                output_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "uploads"
                )
                
                kml_path = generate_incident_kml(
                    report_id=saved_report.no_laporan,
                    incident_name=saved_report.jenis_kejadian,
                    incident_lat=saved_report.koordinat_lat,
                    incident_lng=saved_report.koordinat_lng,
                    nearest_post_name=nearest_post_name,
                    nearest_post_lat=nearest_post_lat,
                    nearest_post_lng=nearest_post_lng,
                    radius_km=saved_report.radius_pencarian,
                    output_dir=output_dir
                )
                
                if os.path.exists(kml_path):
                    with open(kml_path, "rb") as f:
                        kml_bytes = f.read()
                    
                    kml_filename = os.path.basename(kml_path)
                    caption = f"Peta KML Terintegrasi untuk Laporan {saved_report.no_laporan}"
                    
                    # Forward document to Telegram & WhatsApp
                    await reply_dispatcher.forward_file_to_telegram_sar_group(
                        file_bytes=kml_bytes,
                        filename=kml_filename,
                        caption=caption,
                        bot_token=tenant_settings.TELEGRAM_BOT_TOKEN,
                        group_id=tenant_settings.TELEGRAM_SAR_GROUP_ID
                    )
                    
                    await reply_dispatcher.forward_file_to_whatsapp_sar_group(
                        file_bytes=kml_bytes,
                        filename=kml_filename,
                        mime_type="application/vnd.google-earth.kml+xml",
                        caption=caption,
                        wa_token=tenant_settings.WHATSAPP_API_TOKEN,
                        phone_id=tenant_settings.WHATSAPP_PHONE_NUMBER_ID,
                        group_id=tenant_settings.WHATSAPP_SAR_GROUP_ID
                    )
                    logger.info(f"KML map dispatched successfully for {saved_report.no_laporan}")
            except Exception as e:
                logger.error(f"Failed to generate or forward KML map: {e}")

        # Fetch weather automatically if coordinates are present
        cuaca_val = extracted.get("cuaca")
        if not cuaca_val and lat and lng:
            try:
                from app.services import weather_service
                cuaca_val = await weather_service.fetch_weather(lat, lng)
            except Exception as e:
                logger.warning(f"Failed to fetch weather in action_handler: {e}")
        if not cuaca_val:
            cuaca_val = "Berawan (Otomatis)"

        # Extract unsur and alut from nearest Pos SAR in DB if not explicitly provided
        unsur_val = extracted.get("unsur")
        alut_val = extracted.get("alut")
        
        if not unsur_val or not alut_val:
            unsur_alut_str = saved_report.unsur_alut
            if unsur_alut_str:
                try:
                    import json
                    if isinstance(unsur_alut_str, str):
                        data_ua = json.loads(unsur_alut_str)
                    else:
                        data_ua = unsur_alut_str
                        
                    if isinstance(data_ua, dict):
                        if not unsur_val and "unsur" in data_ua:
                            u_list = data_ua["unsur"]
                            if isinstance(u_list, list):
                                items = []
                                for item in u_list:
                                    if isinstance(item, dict):
                                        items.append(item.get("nama") or item.get("name"))
                                    elif isinstance(item, str):
                                        items.append(item)
                                if items:
                                    unsur_val = "\n".join(f"* {i}" for i in items if i)
                                    
                        if not alut_val and "alut" in data_ua:
                            a_list = data_ua["alut"]
                            if isinstance(a_list, list):
                                items = []
                                for item in a_list:
                                    if isinstance(item, dict):
                                        items.append(item.get("nama") or item.get("name"))
                                    elif isinstance(item, str):
                                        items.append(item)
                                if items:
                                    alut_val = "\n".join(f"* {i}" for i in items if i)
                except Exception as e:
                    logger.warning(f"Failed to parse unsur_alut from report: {e}")

        # Convert created_at to local timezone dynamically based on bujur coordinate
        local_created_at = saved_report.created_at
        tz_char = "G" # Default WIB
        offset_hours = 7.0
        
        # 1. Determine local timezone offset based on bujur coordinate (longitude)
        if saved_report.koordinat_lng is not None:
            try:
                lng_val = float(saved_report.koordinat_lng)
                if lng_val >= 135.0:
                    offset_hours = 9.0
                    tz_char = "J" # WIT
                elif lng_val >= 115.0:
                    offset_hours = 8.0
                    tz_char = "H" # WITA
                else:
                    offset_hours = 7.0
                    tz_char = "G" # WIB
            except Exception:
                pass
                
        # 2. Convert UTC to local target timezone
        if local_created_at:
            from datetime import timezone, timedelta
            if local_created_at.tzinfo is not None:
                local_created_at = local_created_at.astimezone(timezone(timedelta(hours=offset_hours)))
            else:
                local_created_at = local_created_at.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=offset_hours)))

        # 3. Format final BASARNAS template
        template_data = {
            "KLASIFIKASI": saved_report.jenis_kejadian,
            "JUDUL_KEJADIAN": f"{saved_report.jenis_kejadian} di {saved_report.lokasi_teks}",
            "WAKTU_INFO_DITERIMA": local_created_at.strftime(f"%m%d %H%M {tz_char}") if local_created_at else "",
            "created_at": local_created_at,
            "PELAPOR": f"{saved_report.pelapor_nama} ({saved_report.pelapor_nomor})",
            "WAKTU_KEJADIAN": saved_report.waktu,
            "LOKASI_KEJADIAN": saved_report.lokasi_teks,
            "KOORDINAT": extracted.get("koordinat") or (f"{saved_report.koordinat_lat}, {saved_report.koordinat_lng}" if saved_report.koordinat_lat else "Tidak diketahui"),
            "heading_ke_lokasi": saved_report.heading_ke_lokasi,
            "jarak_ke_lokasi": saved_report.jarak_ke_lokasi,
            "pos_sar_terdekat": saved_report.pos_sar_terdekat,
            "HEADING_JARAK": f"{saved_report.heading_ke_lokasi or '-'} / {saved_report.jarak_ke_lokasi or '-'}" if saved_report.heading_ke_lokasi else "Tidak terdeteksi",
            "JUMLAH_KORBAN_TOTAL": str(saved_report.korban_total or "0"),
            "korban_selamat": str(saved_report.korban_selamat or "-"),
            "korban_meninggal": str(saved_report.korban_meninggal or "-"),
            "korban_hilang": str(saved_report.korban_hilang or "-"),
            "data_korban": data_korban_payload.get("daftar_korban") if data_korban_payload and isinstance(data_korban_payload, dict) else raw_data_korban,
            "data_kapal": extracted.get("data_kapal"),
            "data_pesawat": extracted.get("data_pesawat"),
            "data_alat": extracted.get("data_alat"),
            "KRONOLOGI": saved_report.kronologi,
            "CUACA": cuaca_val,
            "unsur_alut": saved_report.unsur_alut,
            "UNSUR_SAR": unsur_val,
            "ALUT_PALSAR": alut_val,
            "AKSI": extracted.get("aksi"),
            "HASIL": extracted.get("hasil")
        }
        
        info_awal_text = message_formatter.render(None, template_data)
        
        # 4. Dispatch to WhatsApp & Telegram SAR command groups
        dispatch_res = await reply_dispatcher.forward_report_to_all_groups(
            info_awal_text,
            bot_token=tenant_settings.TELEGRAM_BOT_TOKEN,
            tg_group_id=tenant_settings.TELEGRAM_SAR_GROUP_ID,
            wa_token=tenant_settings.WHATSAPP_API_TOKEN,
            wa_phone_id=tenant_settings.WHATSAPP_PHONE_NUMBER_ID,
            wa_group_id=tenant_settings.WHATSAPP_SAR_GROUP_ID,
            lat=saved_report.koordinat_lat,
            lng=saved_report.koordinat_lng
        )
        if isinstance(dispatch_res, dict) and dispatch_res.get("tg_message_id") and saved_report:
            try:
                meta = saved_report.metadata_kejadian if isinstance(saved_report.metadata_kejadian, dict) else {}
                meta["telegram_group_msg_id"] = dispatch_res["tg_message_id"]
                saved_report.metadata_kejadian = meta
                await db.commit()
            except Exception as meta_err:
                logger.warning(f"Could not update telegram_group_msg_id on saved_report: {meta_err}")
        
        return info_awal_text, saved_report

    @staticmethod
    async def trigger_post_commit_tasks(user_id: str, report_id: int, db_url: str, cron_text: str, metadata: dict):
        """Triggers asynchronous LLM vectorization and vocabulary learning after transaction commits successfully."""
        # Trigger LLM Vectorization
        try:
            from app.services.llm_rag import LLMRagService
            import asyncio
            llm_rag = LLMRagService()
            
            async def run_vectorize():
                from app.db.session import get_tenant_sessionmaker
                session_maker = get_tenant_sessionmaker(db_url)
                async with session_maker() as bg_db:
                    await llm_rag.vectorize_report(report_id, cron_text, metadata, bg_db)
            
            asyncio.create_task(run_vectorize())
        except Exception as e:
            logger.warning(f"Failed to trigger post-commit vectorize: {e}")

        # Trigger Vocabulary Learning
        if user_id:
            try:
                import asyncio
                async def learn_vocabulary_task():
                    try:
                        from app.db.session import get_tenant_sessionmaker
                        from app.models.chat_session import ChatSession
                        session_maker = get_tenant_sessionmaker(db_url)
                        async with session_maker() as db_session:
                            from sqlalchemy.future import select
                            res = await db_session.execute(
                                select(ChatSession).where(ChatSession.user_id == user_id)
                            )
                            sess = res.scalar_one_or_none()
                            if sess and sess.conversation_history:
                                import json
                                history = json.loads(sess.conversation_history)
                                user_msgs = []
                                for h in history:
                                    if h.get("role") == "user":
                                        content = h.get("content", "").strip()
                                        if len(content) > 2:
                                            user_msgs.append(content)
                                if user_msgs:
                                    combined_text = "\n".join(user_msgs)
                                    from app.services.llm_rag import LLMRagService
                                    llm_rag = LLMRagService()
                                    unrecognized = await llm_rag.detect_unknown_words(combined_text)
                                    if unrecognized:
                                        await llm_rag.save_unknown_words(
                                            unrecognized, combined_text, user_id, db_session, word_type="JARGON"
                                        )
                    except Exception as task_err:
                        logger.error(f"Failed post-commit vocabulary learning task: {task_err}")
                        
                asyncio.create_task(learn_vocabulary_task())
            except Exception as e:
                logger.warning(f"Failed to trigger post-commit vocabulary learning: {e}")
