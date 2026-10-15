"""
Group Listener Service
======================
Monitors and processes operational updates posted by SAR personnel/operators
in Telegram and WhatsApp coordination groups.

Key Capabilities:
1. Target Report Resolution:
   - Matches replies to previous Info Awal messages (via message_id or regex).
   - Matches report numbers mentioned explicitly in chat.
   - Contextually matches active SAR incidents based on keywords/locations.
2. Incremental Delta Update:
   - Uses LLM to extract only changed fields (victim statuses, new teams/alut, coordinates).
   - Appends timestamped development timeline entries to kronologi.
   - Updates the database without recreating or re-generating the report from scratch.
3. Continuous Learning Ingestion:
   - Ingests new local toponyms/locations into DictionaryWord (ner_type="LOCATION", APPROVED).
   - Ingests operational terms/abbreviations into DictionaryWord.
   - Re-vectorizes the updated incident report into VectorMemory (pgvector 1024-dim).
   - Broadcasts real-time WebSocket events to the frontend dashboard.
4. Feedback Dispatch:
   - Sends a concise confirmation directly into the group discussion thread.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.report import Report, ReportStatus
from app.models.knowledge_models import DictionaryWord, DictionaryStatus
from app.services.ai_providers import ai_provider_manager
from app.services.reply_dispatcher import reply_dispatcher
from app.services.llm_rag import LLMRagService
from app.core.tenant_config import get_tenant_settings
from app.core.websocket import manager

logger = logging.getLogger(__name__)

# Keywords indicating an operational SAR update rather than casual banter
SAR_UPDATE_KEYWORDS = {
    "update", "laporan", "korban", "selamat", "md", "hilang", "dp",
    "pencarian", "ditemukan", "ops", "sar", "alut", "rib", "kri",
    "kn", "perkembangan", "posisi", "koordinat", "evakuasi", "jenazah",
    "jasad", "selesai", "tenggelam", "hanyut", "karang", "pantai",
    "muara", "tanjung", "pulau", "medis", "rsud", "puskesmas"
}

def has_sar_update_intent(text: str) -> bool:
    """Check if message contains SAR update intent, filtering out casual greetings like 'selamat pagi'."""
    cleaned = text.lower()
    for greeting in (
        "selamat pagi", "selamat siang", "selamat sore", 
        "selamat malam", "selamat bertugas", "selamat bekerja", 
        "selamat beristirahat"
    ):
        cleaned = cleaned.replace(greeting, " ")
    return any(kw in cleaned for kw in SAR_UPDATE_KEYWORDS)


# Regex to capture report numbers like KMM-202605-001 or LAP-202605-012
REPORT_NO_REGEX = re.compile(r'\b([A-Z]{2,5}-\d{6}-\d{3})\b', re.IGNORECASE)


class GroupListenerService:
    """Service to process incoming group messages and perform continuous learning."""

    def __init__(self):
        self.llm_rag = LLMRagService()

    @staticmethod
    def is_group_chat(message_dict: dict) -> bool:
        """Determines if the incoming Telegram message originated from a group."""
        chat = message_dict.get("chat", {})
        chat_type = chat.get("type", "private")
        if chat_type in ("group", "supergroup"):
            return True
        chat_id_str = str(chat.get("id", ""))
        return chat_id_str.startswith("-")

    async def resolve_target_report(
        self,
        message: dict,
        text: str,
        db: AsyncSession
    ) -> Optional[Report]:
        """
        Identify which SAR Report this group message refers to.
        Strategy 1: Direct Reply to previous bot Info Awal message.
        Strategy 2: Explicit Report Number in text or replied message.
        Strategy 3: Active Incident Matching (single active or keyword matched).
        """
        reply_to = message.get("reply_to_message")
        
        # ── 1. Check Reply-To Message ────────────────────────────────
        if reply_to:
            replied_msg_id = reply_to.get("message_id")
            if replied_msg_id:
                # Check Report by stored telegram_group_msg_id in metadata_kejadian
                res = await db.execute(
                    select(Report).where(
                        Report.metadata_kejadian["telegram_group_msg_id"].astext == str(replied_msg_id)
                    )
                )
                rep = res.scalar_one_or_none()
                if rep:
                    logger.info(f"[GroupListener] Matched report {rep.no_laporan} via replied_msg_id {replied_msg_id}")
                    return rep

            # Check text of replied message for report number
            replied_text = reply_to.get("text", "")
            matched_no = REPORT_NO_REGEX.search(replied_text)
            if matched_no:
                no_lap = matched_no.group(1).upper()
                res = await db.execute(
                    select(Report).where(func.upper(Report.no_laporan) == no_lap)
                )
                rep = res.scalar_one_or_none()
                if rep:
                    logger.info(f"[GroupListener] Matched report {rep.no_laporan} via replied text regex")
                    return rep

        # ── 2. Check Report Number in incoming text ───────────────────
        direct_match = REPORT_NO_REGEX.search(text)
        if direct_match:
            no_lap = direct_match.group(1).upper()
            res = await db.execute(
                select(Report).where(func.upper(Report.no_laporan) == no_lap)
            )
            rep = res.scalar_one_or_none()
            if rep:
                logger.info(f"[GroupListener] Matched report {rep.no_laporan} via direct text regex")
                return rep

        # ── 3. Check Active Reports ──────────────────────────────────
        # Fetch active or recently created reports (last 72 hours)
        res = await db.execute(
            select(Report)
            .where(Report.status == ReportStatus.AKTIF)
            .order_by(Report.updated_at.desc().nullslast(), Report.created_at.desc())
            .limit(10)
        )
        active_reports = res.scalars().all()
        if not active_reports:
            # Fallback: check pending reports if none are active
            res_pending = await db.execute(
                select(Report)
                .where(Report.status == ReportStatus.PENDING)
                .order_by(Report.created_at.desc())
                .limit(5)
            )
            active_reports = res_pending.scalars().all()

        if not active_reports:
            return None

        # Check if text contains any SAR update intent (ignoring morning/evening greetings)
        if not has_sar_update_intent(text):
            # Probably normal group conversation or greeting
            return None

        # If exactly 1 active report exists and text has SAR keywords, associate with it
        if len(active_reports) == 1:
            logger.info(f"[GroupListener] Matched sole active report {active_reports[0].no_laporan}")
            return active_reports[0]

        # If multiple active reports, match based on specific location or vessel name
        best_rep = None
        highest_score = 0
        for rep in active_reports:
            score = 0
            if rep.lokasi_teks and len(rep.lokasi_teks) > 3:
                # Split location words (ignoring very short words)
                loc_words = [w for w in re.split(r'[\s,]+', rep.lokasi_teks.lower()) if len(w) > 3]
                for lw in loc_words:
                    if lw in text_lower:
                        score += 3
            if rep.jenis_kejadian and rep.jenis_kejadian.lower() in text_lower:
                score += 2
            if rep.pelapor_nama and rep.pelapor_nama.lower() in text_lower:
                score += 2
            
            # Check vessel name in metadata
            if rep.metadata_kejadian and isinstance(rep.metadata_kejadian, dict):
                v_name = rep.metadata_kejadian.get("nama_kapal")
                if v_name and len(v_name) > 3 and v_name.lower() in text_lower:
                    score += 4

            if score > highest_score:
                highest_score = score
                best_rep = rep

        if best_rep and highest_score >= 3:
            logger.info(f"[GroupListener] Matched active report {best_rep.no_laporan} with score {highest_score}")
            return best_rep

        return None

    async def extract_delta_update(
        self,
        report: Report,
        update_text: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Uses LLM to perform Delta Extraction between current report and incoming operator chat.
        Returns fields to update, timeline entry, and newly discovered toponyms/terms.
        """
        tenant_settings = None
        if db:
            try:
                tenant_settings = await get_tenant_settings(db)
            except Exception as ts_err:
                logger.debug(f"[GroupListener] Safe tenant_settings fallback: {ts_err}")

        current_summary = {
            "no_laporan": report.no_laporan,
            "jenis_kejadian": report.jenis_kejadian,
            "lokasi": report.lokasi_teks,
            "koordinat": f"{report.koordinat_lat}, {report.koordinat_lng}" if report.koordinat_lat else "Belum ada",
            "korban_total": report.korban_total,
            "korban_selamat": report.korban_selamat,
            "korban_meninggal": report.korban_meninggal,
            "korban_hilang": report.korban_hilang,
            "unsur_alut": report.unsur_alut,
            "kronologi": (report.kronologi or "")[-500:] # Last 500 chars of chronology
        }

        system_prompt = (
            "Anda adalah asisten AI Puskodal Badan Nasional Pencarian dan Pertolongan (BASARNAS).\n"
            "Tugas Anda: mengekstrak informasi perubahan (DELTA UPDATE) dari pesan update operator di grup SAR.\n"
            "Keluarkan output HANYA dalam format valid JSON tanpa teks pembuka atau markdown formatting di luar JSON."
        )

        user_prompt = f"""
DATA LAPORAN SAR SAAT INI:
{json.dumps(current_summary, indent=2, ensure_ascii=False)}

PESAN UPDATE DARI OPERATOR DI GRUP:
"{update_text}"

INSTRUKSI ANALISIS:
1. 'is_relevant_sar_update': true jika pesan ini memuat informasi/perkembangan operasi SAR, false jika hanya obrolan umum.
2. 'summary_text': 1-2 kalimat ringkasan bahasa Indonesia yang jelas tentang apa yang berubah/ditemukan.
3. 'fields_to_update': Dictionary berisi kolom yang berubah (isi null jika tidak ada perubahan):
   - 'korban_selamat': integer angka baru (jika ada korban ditemukan selamat, perbarui total selamat)
   - 'korban_meninggal': integer angka baru (jika ada korban ditemukan tewas/MD)
   - 'korban_hilang': integer angka baru (jumlah yang masih dicari)
   - 'unsur_alut': string penambahan tim atau armada alut yang merapat/dikerahkan
   - 'lokasi_teks': string jika ada penegasan lokasi penemuan atau pergeseran titik
   - 'koordinat_lat': float latitude baru jika disebutkan
   - 'koordinat_lng': float longitude baru jika disebutkan
   - 'status': "TIDAK_AKTIF" jika operasi resmi ditutup/dihentikan/selesai, selain itu null.
4. 'timeline_entry': 1 kalimat padat perkembangan terbaru untuk dicatat ke riwayat kronologi operasi.
5. 'new_locations': Array objek toponimi/nama tempat/patokan lokal spesifik yang disebut (contoh: pantai, karang, muara, tanjung, teluk):
   [ {{"word": "Nama Lokasi", "description": "Deskripsi atau patokan"}} ]
6. 'new_terms': Array singkatan atau istilah SAR operasional baru jika ada.

FORMAT JSON OUTPUT HARUS TEPAT SEPERTI INI:
{{
  "is_relevant_sar_update": true,
  "summary_text": "...",
  "fields_to_update": {{
    "korban_selamat": null,
    "korban_meninggal": null,
    "korban_hilang": null,
    "unsur_alut": null,
    "lokasi_teks": null,
    "koordinat_lat": null,
    "koordinat_lng": null,
    "status": null
  }},
  "timeline_entry": "...",
  "new_locations": [],
  "new_terms": []
}}
"""
        try:
            raw_response = await ai_provider_manager.llm_generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                json_mode=True,
                tenant_settings=tenant_settings,
                timeout=30.0
            )

            # Clean JSON wrapping if present
            cleaned_json = raw_response.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json[7:]
            if cleaned_json.startswith("```"):
                cleaned_json = cleaned_json[3:]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json[:-3]
            cleaned_json = cleaned_json.strip()

            parsed = json.loads(cleaned_json)
            return parsed
        except Exception as e:
            logger.warning(f"[GroupListener] LLM delta extraction failed: {e}. Falling back to rule-based parser.")
            return self._fallback_delta_extractor(report, update_text)

    def _fallback_delta_extractor(self, report: Report, text: str) -> Dict[str, Any]:
        """Simple rule-based fallback when LLM is unavailable."""
        text_lower = text.lower()
        fields: Dict[str, Any] = {}
        summary_parts = []
        new_locs = []

        # Check for victim updates
        selamat_match = re.search(r'(\d+)\s*(?:orang\s*)?selamat', text_lower)
        if selamat_match:
            val = int(selamat_match.group(1))
            fields["korban_selamat"] = (report.korban_selamat or 0) + val
            summary_parts.append(f"{val} korban selamat")

        md_match = re.search(r'(\d+)\s*(?:orang\s*)?(?:meninggal|md|tewas|jenazah)', text_lower)
        if md_match:
            val = int(md_match.group(1))
            fields["korban_meninggal"] = (report.korban_meninggal or 0) + val
            summary_parts.append(f"{val} korban meninggal dunia")

        # Check for status closed
        if any(w in text_lower for w in ("operasi ditutup", "ops sar ditutup", "selesai ops", "operasi sar selesai")):
            fields["status"] = "TIDAK_AKTIF"
            summary_parts.append("Operasi SAR resmi ditutup")

        # Check for coordinates
        coord_match = re.search(r'(-?\d{1,2}\.\d+)[,\s]+(\d{2,3}\.\d+)', text)
        if coord_match:
            fields["koordinat_lat"] = float(coord_match.group(1))
            fields["koordinat_lng"] = float(coord_match.group(2))
            summary_parts.append("Koordinat lokasi diperbarui")

        # Check for location keywords like "di karang ...", "di pantai ..."
        loc_match = re.search(r'\b(?:di|sekitar|perairan|pantai|karang|muara|tanjung)\s+([A-Za-z\s]{3,25})\b', text, re.IGNORECASE)
        if loc_match:
            cand = loc_match.group(0).strip()
            new_locs.append({"word": cand.title(), "description": f"Lokasi disebut dalam update laporan {report.no_laporan}"})

        summary = ", ".join(summary_parts) if summary_parts else "Pembaruan informasi operasional SAR"

        return {
            "is_relevant_sar_update": True,
            "summary_text": summary,
            "fields_to_update": fields,
            "timeline_entry": text.strip(),
            "new_locations": new_locs,
            "new_terms": []
        }

    async def apply_delta_update(
        self,
        report: Report,
        delta: Dict[str, Any],
        db: AsyncSession
    ) -> Tuple[Report, str]:
        """
        Applies extracted delta updates to Report record, stores new vocabulary to DictionaryWord,
        re-vectorizes report memory, and broadcasts WebSocket update.
        """
        fields = delta.get("fields_to_update") or {}
        summary_text = delta.get("summary_text", "Update berhasil diproses")

        # ── 1. Apply Report Field Updates ────────────────────────────
        if fields.get("korban_selamat") is not None:
            report.korban_selamat = int(fields["korban_selamat"])
        if fields.get("korban_meninggal") is not None:
            report.korban_meninggal = int(fields["korban_meninggal"])
        if fields.get("korban_hilang") is not None:
            report.korban_hilang = int(fields["korban_hilang"])

        # Auto-recalculate korban_total if breakdown was updated
        if any(k in fields for k in ("korban_selamat", "korban_meninggal", "korban_hilang")):
            tot = (report.korban_selamat or 0) + (report.korban_meninggal or 0) + (report.korban_hilang or 0)
            if tot > 0:
                report.korban_total = tot

        if fields.get("unsur_alut"):
            current_alut = report.unsur_alut or ""
            new_alut = str(fields["unsur_alut"]).strip()
            if new_alut not in current_alut:
                report.unsur_alut = f"{current_alut}\n* {new_alut}".strip() if current_alut else new_alut

        if fields.get("lokasi_teks"):
            report.lokasi_teks = str(fields["lokasi_teks"]).strip()

        if fields.get("koordinat_lat") is not None and fields.get("koordinat_lng") is not None:
            try:
                report.koordinat_lat = float(fields["koordinat_lat"])
                report.koordinat_lng = float(fields["koordinat_lng"])
                from geoalchemy2.elements import WKTElement
                report.location_geom = WKTElement(f"POINT({report.koordinat_lng} {report.koordinat_lat})", srid=4326)
            except Exception as geom_err:
                logger.warning(f"[GroupListener] Failed to set location_geom: {geom_err}")

        if fields.get("status") == "TIDAK_AKTIF":
            report.status = ReportStatus.TIDAK_AKTIF

        # ── 2. Append Timeline Entry to Kronologi ────────────────────
        timeline_entry = delta.get("timeline_entry") or summary_text
        now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        update_log_line = f"[{now_str}] Perkembangan Grup: {timeline_entry}"
        if report.kronologi:
            report.kronologi = f"{report.kronologi}\n{update_log_line}"
        else:
            report.kronologi = update_log_line

        report.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(report)

        # ── 3. Continuous Learning: Ingest New Locations ─────────────
        new_locs = delta.get("new_locations", [])
        if isinstance(new_locs, list):
            for loc_item in new_locs:
                if not isinstance(loc_item, dict):
                    continue
                word = loc_item.get("word", "").strip()
                if not word or len(word) < 3:
                    continue

                try:
                    # Check if word already exists in DictionaryWord
                    res_word = await db.execute(
                        select(DictionaryWord).where(func.lower(DictionaryWord.word) == word.lower())
                    )
                    existing_word = res_word.scalar_one_or_none()
                    if not existing_word:
                        new_dw = DictionaryWord(
                            word=word,
                            definition=loc_item.get("description") or f"Lokasi/toponimi lokal dari update {report.no_laporan}",
                            ner_type="LOCATION",
                            word_type="GENERAL",
                            status=DictionaryStatus.APPROVED,
                            is_auto_detected=True,
                            frequency=1
                        )
                        db.add(new_dw)
                        await db.commit()
                        logger.info(f"[Continuous Learning] Learned new location toponimi: '{word}'")
                    else:
                        existing_word.frequency = (existing_word.frequency or 1) + 1
                        if not existing_word.ner_type:
                            existing_word.ner_type = "LOCATION"
                        await db.commit()
                except Exception as dw_err:
                    await db.rollback()
                    logger.warning(f"[GroupListener] Could not save location '{word}' to dictionary: {dw_err}")

        # ── 4. Continuous Learning: Vector Memory Update ─────────────
        try:
            embed_content = (
                f"Laporan {report.no_laporan} - {report.jenis_kejadian} di {report.lokasi_teks}.\n"
                f"Kronologi: {report.kronologi}\n"
                f"Alut/Unsur: {report.unsur_alut}\n"
                f"Korban: Total {report.korban_total}, Selamat {report.korban_selamat}, MD {report.korban_meninggal}, DP {report.korban_hilang}"
            )
            metadata = {
                "no_laporan": report.no_laporan,
                "jenis_kejadian": report.jenis_kejadian,
                "lokasi_teks": report.lokasi_teks,
                "pos_sar": report.pos_sar_terdekat,
                "status": report.status.value if hasattr(report.status, "value") else str(report.status)
            }
            await self.llm_rag.vectorize_report(report.id, embed_content, metadata, db)
            logger.info(f"[Continuous Learning] Re-vectorized report {report.id} to VectorMemory")
        except Exception as vec_err:
            logger.warning(f"[GroupListener] Vectorization failed: {vec_err}")

        # ── 5. Real-Time Broadcast to Web Frontend ───────────────────
        try:
            await manager.broadcast({
                "type": "REPORT_UPDATED",
                "report_id": report.id,
                "no_laporan": report.no_laporan,
                "status": report.status.value if hasattr(report.status, "value") else str(report.status),
                "summary": summary_text,
                "updated_at": report.updated_at.isoformat() if report.updated_at else None
            }, db=db)
        except Exception as ws_err:
            logger.warning(f"[GroupListener] WebSocket broadcast failed: {ws_err}")

        return report, summary_text

    async def process_telegram_group_message(
        self,
        message: dict,
        token: str,
        db: AsyncSession
    ) -> bool:
        """
        Orchestrates processing of a message received from a Telegram group.
        Supports text messages and voice note transcriptions.
        """
        chat_id = str(message.get("chat", {}).get("id"))
        msg_id = message.get("message_id")
        text = message.get("text", "")

        # ── Handle Voice Notes in Group ──────────────────────────────
        if "voice" in message or "audio" in message:
            try:
                from app.services.transcription import transcription_service
                audio_obj = message.get("voice") or message.get("audio")
                file_id = audio_obj.get("file_id")
                if file_id:
                    local_path = await transcription_service.download_telegram_voice(file_id, bot_token=token)
                    if local_path and local_path != "size_limit_exceeded":
                        transcribed = await transcription_service.transcribe_audio(local_path)
                        if transcribed and transcribed.strip():
                            text = transcribed.strip()
                            logger.info(f"[GroupListener] Transcribed group voice note: '{text}'")
            except Exception as voice_err:
                logger.warning(f"[GroupListener] Voice transcription failed: {voice_err}")

        if not text or len(text.strip()) < 3:
            return False

        # ── 1. Resolve Target Report ─────────────────────────────────
        target_report = await self.resolve_target_report(message, text, db)
        if not target_report:
            # Message is regular group chat or unrelated to any SAR incident
            logger.debug(f"[GroupListener] Message in group {chat_id} did not match any active report. Ignored.")
            return False

        logger.info(f"[GroupListener] Processing SAR update for {target_report.no_laporan}: '{text}'")

        # ── 2. Delta Extraction via LLM ──────────────────────────────
        delta = await self.extract_delta_update(target_report, text, db)
        if not delta.get("is_relevant_sar_update"):
            logger.info(f"[GroupListener] Message classified as not relevant SAR update for {target_report.no_laporan}")
            return False

        # ── 3. Apply Delta & Continuous Learning ──────────────────────
        updated_report, summary_text = await self.apply_delta_update(target_report, delta, db)

        # ── 4. Send Confirmation into Telegram Group ─────────────────
        reply_message = (
            f"*Pembaruan Data Operasi SAR Tercatat*\n\n"
            f"*No Laporan:* `{updated_report.no_laporan}`\n"
            f"*Lokasi:* {updated_report.lokasi_teks or '-'}\n"
            f"*Status Korban:* Selamat: {updated_report.korban_selamat or 0} | MD: {updated_report.korban_meninggal or 0} | Hilang: {updated_report.korban_hilang or 0}\n\n"
            f"*Ringkasan:* {summary_text}\n"
            f"_{now_utc()}_"
        )

        try:
            await reply_dispatcher.send_telegram_reply(
                chat_id=chat_id,
                text=reply_message,
                reply_to_message_id=msg_id,
                bot_token=token
            )
            logger.info(f"[GroupListener] Sent confirmation reply to group {chat_id} for {updated_report.no_laporan}")
            return True
        except Exception as reply_err:
            logger.error(f"[GroupListener] Failed to send reply to group: {reply_err}")
            return False


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


# Singleton
group_listener_service = GroupListenerService()
