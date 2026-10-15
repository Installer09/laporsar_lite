import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat_session import ChatSession
from app.engine.state_handlers.base import BaseStateHandler

if TYPE_CHECKING:
    from app.engine.chatbot_engine import ChatbotEngine

logger = logging.getLogger(__name__)

class ConfirmingStateHandler(BaseStateHandler):
    """Handles user replies when in the draft confirmation state (CONFIRMING state)."""

    async def handle(
        self, engine: "ChatbotEngine", session: ChatSession, message: str, extracted_data: dict, db: AsyncSession, autopilot: bool
    ) -> dict:
        answer = message.strip().lower()
        affirm = ("ya", "y", "benar", "betul", "ok", "oke", "yep", "yes", "setuju", "kirim", "lanjut")
        deny = ("tidak", "no", "n", "batal", "salah", "ulangi", "ulang", "reset", "batalkan")
        lengkapi = ("lengkapi", "tambah", "edit")

        if answer in affirm:
            # Complete report -> trigger action_handler (does not commit)
            info_awal, saved_report = await engine.action_handler.complete_report(
                {"user_id": session.user_id, "extracted_data": extracted_data}, db
            )
            session.state = "COMPLETED"
            
            # Save completed timestamp to session for rate limit tracking
            completed_reports = extracted_data.get("_completed_reports", [])
            completed_reports.append(datetime.now(timezone.utc).isoformat())
            extracted_data["_completed_reports"] = completed_reports
            if saved_report and getattr(saved_report, "no_laporan", None):
                extracted_data["_last_report_no"] = saved_report.no_laporan
            
            # Ensure contact_phone is synced with pelapor_hp if not set
            if not session.contact_phone and extracted_data.get("pelapor_hp"):
                session.contact_phone = extracted_data.get("pelapor_hp")
                
            session.extracted_data = json.dumps(extracted_data)
            
            # Check if location is outside working area of Natuna SAR (Natuna/Anambas)
            is_outside = await engine._is_outside_working_area(extracted_data, db)
            
            no_lap = saved_report.no_laporan if (saved_report and getattr(saved_report, "no_laporan", None)) else "-"
            pos_sar = getattr(saved_report, "pos_sar_terdekat", None) or "Command Center Kantor SAR"

            if is_outside:
                reply = (
                    "*Laporan Anda Telah Diterima secara Resmi*\n\n"
                    f"*Nomor Laporan:* `{no_lap}`\n"
                    "*Catatan Wilayah:* Lokasi kejadian berada di luar wilayah kerja operasional unit lokal ini. "
                    "Laporan darurat Anda telah dikoordinasikan langsung ke Kantor SAR terdekat yang berwenang.\n\n"
                    "*PANDUAN KESELAMATAN SEMENTARA:*\n"
                    "1. Tetap tenang dan usahakan berada di titik aman/terapung.\n"
                    "2. Gunakan pelampung (*life jacket*) atau benda terapung darurat.\n"
                    "3. Hemat daya baterai ponsel Anda untuk komunikasi darurat.\n\n"
                    "*PENTING:* Pastikan nomor telepon/WhatsApp Anda selalu aktif. Petugas rescue/SAR akan segera menghubungi Anda untuk memandu tindakan penyelamatan.\n\n"
                    "*Call Center BASARNAS:* 115 (Bebas Pulsa 24 Jam)\n"
                    "*Website Resmi:* https://basarnas.go.id\n\n"
                    "Untuk membuat laporan baru atau mengecek status, silakan ketik */start* atau pilih tombol di bawah."
                )
            else:
                reply = (
                    "*Laporan Anda Telah Diterima secara Resmi*\n\n"
                    f"*Nomor Laporan:* `{no_lap}`\n"
                    f"Laporan darurat ini telah diteruskan langsung ke *{pos_sar}* dan tim siaga rescue.\n\n"
                    "*PANDUAN KESELAMATAN SEMENTARA:*\n"
                    "1. Tetap tenang dan usahakan bertahan di tempat aman/titik terapung.\n"
                    "2. Gunakan pelampung (*life jacket*) atau alat apung darurat.\n"
                    "3. Hemat daya baterai ponsel Anda untuk komunikasi darurat.\n\n"
                    "*PENTING:* Pastikan nomor telepon/WhatsApp Anda selalu aktif. Petugas rescue/SAR akan segera menghubungi Anda untuk memandu tindakan penyelamatan.\n\n"
                    "*Call Center BASARNAS:* 115 (Bebas Pulsa 24 Jam)\n"
                    "*Website Resmi:* https://basarnas.go.id\n\n"
                    "Untuk membuat laporan baru atau mengecek status, silakan ketik */start* atau pilih tombol di bawah."
                )
                
            buttons = ["Buat Laporan Baru", "Cek Status Laporan"]
            engine._update_history(session, "assistant", reply, buttons=buttons)
            
            # Consolidate all database operations (report, attachments, session, state) into exactly one commit
            try:
                await db.commit()
            except Exception as commit_err:
                await db.rollback()
                logger.error(f"Transaction failed for final report confirmation: {commit_err}")
                raise HTTPException(
                    status_code=500,
                    detail="Gagal memproses konfirmasi laporan karena kendala database."
                )
                
            # Trigger background tasks (vectorize, slang learning) ONLY after successful transaction commit
            try:
                db_url = db.bind.url.render_as_string(hide_password=False)
                cron_text = f"Laporan {saved_report.no_laporan}: {saved_report.kronologi or ''}"
                
                # Safe vessel name extraction from metadata
                nama_kapal = None
                if saved_report.metadata_kejadian:
                    try:
                        if isinstance(saved_report.metadata_kejadian, str):
                            meta_dict = json.loads(saved_report.metadata_kejadian)
                        else:
                            meta_dict = saved_report.metadata_kejadian
                        nama_kapal = (
                            meta_dict.get("nama_kapal")
                            or (meta_dict.get("data_kapal", {}).get("nama_kapal") if isinstance(meta_dict.get("data_kapal"), dict) else None)
                            or meta_dict.get("data_kapal")
                        )
                    except Exception:
                        pass
                
                metadata = {
                    "jenis_kejadian": saved_report.jenis_kejadian,
                    "nama_kapal": nama_kapal,
                    "lokasi_teks": saved_report.lokasi_teks,
                    "waktu": saved_report.waktu,
                    "korban_detail": saved_report.korban or str(saved_report.korban_total or "")
                }
                
                from app.engine.action_handler import ActionHandler
                await ActionHandler.trigger_post_commit_tasks(
                    user_id=session.user_id,
                    report_id=saved_report.id,
                    db_url=db_url,
                    cron_text=cron_text,
                    metadata=metadata
                )
            except Exception as bg_err:
                logger.error(f"Failed to queue post-commit background tasks: {bg_err}")

            await engine._broadcast_session(session, autopilot, extracted_data)
            return {"text": reply, "buttons": buttons}
            
        elif answer in lengkapi:
            # Force missing fields to ask again
            for field in ["jenis_kejadian", "waktu", "lokasi_teks", "korban"]:
                if engine._is_field_missing(extracted_data.get(field, "")):
                    extracted_data[field] = ""
                    # Clear explicit skip/Belum Tahu flag to force asking
                    if f"_explicit_{field}" in extracted_data:
                        extracted_data[f"_explicit_{field}"] = False
            session.extracted_data = json.dumps(extracted_data)
            await db.commit()
            return await engine._validate_and_route(session, extracted_data, db, autopilot)
            
        elif answer in deny:
            await engine._reset_session(session, db, autopilot)
            reply = "*Laporan Batal.*\n\nSilakan kirimkan laporan baru jika Anda mengalami atau melihat keadaan darurat."
            return {"text": reply}
            
        else:
            reply = "Mohon jawab *Ya* untuk mengirim laporan, *Lengkapi* untuk merevisi data, atau *Batalkan* untuk menghapus draf."
            return {"text": reply, "buttons": ["Ya", "Lengkapi", "Batalkan"]}
