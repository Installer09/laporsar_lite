import logging
import json
import re
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.chat_session import ChatSession
from app.engine.action_handler import ActionHandler
from app.engine.validator_router import ValidatorRouter
from app.engine.state_manager import StateManager
from app.services.incident_data_service import extract_incident_data
from app.services.message_formatter import message_formatter
from app.services.reply_dispatcher import reply_dispatcher
from app.core.websocket import manager

logger = logging.getLogger(__name__)

# =====================================================================
# Constants
# =====================================================================

REQUIRED_FIELDS = ["waktu", "lokasi_teks", "korban"]

# Core question sequence
CORE_QUESTION_ORDER = ["waktu", "lokasi_teks", "korban"]

# Human-friendly questions in Indonesian (BASARNAS format)
FIELD_QUESTIONS = {
    "waktu": {
        "text": (
            "*Kapan kejadiannya?*\n"
            "Sebutkan jamnya atau kapan musibah itu terjadi.\n"
            "Contoh: _Baru saja_, _10 menit yang lalu_, _jam 10 pagi_."
        ),
        "buttons": ["Baru Saja", "1 Jam yang Lalu", "Hari Ini", "Kemarin", "Belum Tahu"]
    },
    "lokasi_teks": {
        "text": (
            "*Di mana lokasi kejadiannya?*\n"
            "Sebutkan nama pantai, laut, desa, atau patokan terdekat yang Anda ketahui."
        ),
        "buttons": ["Belum Tahu"]
    },
    "koordinat": {
        "text": (
            "*Apakah Anda memiliki titik koordinat GPS kejadian?*\n\n"
            "Anda dapat memberikan titik lokasi kejadian dengan cara:\n"
            "1. Ketuk tombol *Bagikan Lokasi Kejadian* di bawah (jika Anda berada di lokasi kejadian).\n"
            "2. Atau kirim via menu Telegram: ikon lampiran / klip kertas -> *Lokasi* (bisa geser pin ke posisi musibah).\n"
            "3. Atau ketik angka koordinat / tautan Google Maps (contoh: _-3.391282, 106.241521_).\n"
            "4. Jika tidak tahu titik koordinatnya, pilih tombol *Belum Tahu* (cukup nama lokasi yang sudah Anda sebutkan)."
        ),
        "buttons": [{"text": "Bagikan Lokasi Kejadian", "request_location": True}, "Belum Tahu"]
    },
    "korban": {
        "text": (
            "*Berapa perkiraan jumlah total korban?*\n"
        ),
        "buttons": ["Belum Tahu"]
    },
    "korban_kondisi": {
        "text": (
            "*Bagaimana rincian kondisi korban saat ini?*\n"
            "Berapa korban yang selamat, meninggal, atau masih dalam pencarian (hilang)?\n\n"
            "Contoh: _2 selamat, 1 hilang_ atau _selamat semua_"
        ),
        "buttons": ["Belum Tahu"]
    },
    "data_korban": {
        "text": (
            "*Siapa saja nama atau identitas korban?*\n"
            "Sebutkan nama, jenis kelamin, umur, atau ciri-cirinya seadanya jika Anda tahu.\n"
            "Contoh: _Budi (Laki-laki, 40 thn)_"
        ),
        "buttons": ["Tidak Tahu"]
    },
    "data_kapal": {
        "text": (
            "*Apa nama dan jenis kapal yang digunakan?*\n"
            "Sebutkan nama kapal, jenis (misal: pompong/speedboat/kapal nelayan), dan rutenya jika diketahui."
        ),
        "buttons": ["Tidak Tahu"]
    },
    "pakai_kapal": {
        "text": (
            "*Apakah korban menggunakan kapal atau perahu?*\n"
            "Pilih Ya jika melibatkan sarana perahu (seperti pompong, sampan, ketinting, speedboat, kelong, atau kapal nelayan) atau Tidak."
        ),
        "buttons": ["Ya", "Tidak", "Belum Tahu"]
    },
    "data_pesawat": {
        "text": (
            "*Apa nama maskapai dan rute pesawat tersebut?*\n"
            "Sebutkan nama pesawat/maskapai dan rute penerbangan jika diketahui."
        ),
        "buttons": ["Tidak Tahu"]
    },
    "data_alat": {
        "text": (
            "*Apa jenis kendaraan atau alat yang terlibat?*\n"
            "Sebutkan jenis kendaraan, warna, atau nomor polisi jika diketahui."
        ),
        "buttons": ["Tidak Tahu"]
    },
    "eviden": {
        "text": (
            "*Lampiran Dokumentasi Kejadian*\n"
            "Kirimkan foto atau video kondisi lokasi atau korban jika tersedia untuk membantu tim SAR menganalisis medan operasi."
        ),
        "buttons": ["Tidak Ada"]
    },
    "pelapor_nama": {
        "text": (
            "*Nama Lengkap Pelapor*\n"
            "Sebutkan nama lengkap Anda sebagai pelapor resmi."
        ),
        "buttons": []
    },
    "pelapor_hp": {
        "text": (
            "*Nomor Kontak Pelapor*\n"
            "Sebutkan nomor telepon atau WhatsApp aktif yang dapat segera dihubungi oleh tim SAR."
        ),
        "buttons": []
    },
    "pelapor_hubungan": {
        "text": (
            "*Hubungan dengan Korban atau Musibah*\n"
            "Pilih opsi di bawah atau ketik hubungan Anda (contoh: Keluarga Korban, Rekan, Saksi Mata, atau Korban Langsung)."
        ),
        "buttons": ["Keluarga Korban", "Saksi Mata", "Korban"]
    },
    "reporter_location": {
        "text": (
            "*Verifikasi Lokasi Pelapor*\n"
            "Silakan bagikan titik lokasi GPS perangkat Anda saat ini."
        ),
        "buttons": [{"text": "Bagikan Lokasi", "request_location": True}]
    }
}

FIELD_STATE_MAP = {
    "waktu": "AWAITING_WAKTU",
    "lokasi_teks": "AWAITING_LOKASI",
    "korban": "AWAITING_KORBAN",
    "korban_kondisi": "AWAITING_KORBAN_KONDISI",
    "data_korban": "AWAITING_DATA_KORBAN",
    "data_kapal": "AWAITING_DATA_KAPAL",
    "pakai_kapal": "AWAITING_PAKAI_KAPAL",
    "data_pesawat": "AWAITING_DATA_PESAWAT",
    "data_alat": "AWAITING_DATA_ALAT",
    "koordinat": "AWAITING_KOORDINAT",
    "eviden": "AWAITING_EVIDEN",
    "pelapor_nama": "AWAITING_PELAPOR_NAMA",
    "pelapor_hp": "AWAITING_PELAPOR_HP",
    "pelapor_hubungan": "AWAITING_PELAPOR_HUBUNGAN",
    "reporter_location": "AWAITING_REPORTER_LOCATION",
}

# Inverse map
STATE_FIELD_MAP = {v: k for k, v in FIELD_STATE_MAP.items()}

SKIP_WORDS = {
    "lewat", "skip", "tidak", "tidak ada", "tidak tahu", "belum tahu",
    "ga ada", "gak ada", "tdk", "tdk ada", "-", "lanjut",
    "belum tau", "tidak tau", "ndak tahu", "ndak tau",
    "tidak tahu sama sekali", "belum tahu sama sekali",
    "tidak ada data", "belum ada data", "n/a", "unknown", "nihil"
}

MAIN_MENU_TEXT = (
    "*LAYANAN SIAGA PENCARIAN DAN PERTOLONGAN (SAR)*\n"
    "Badan Nasional Pencarian dan Pertolongan (BASARNAS)\n\n"
    "Silakan pilih layanan yang Anda butuhkan:"
)

MAIN_MENU_BUTTONS = ["Lapor SAR", "Info SAR"]

MAIN_MENU_INLINE_KEYBOARD = [
    [{"text": "1. Lapor SAR", "callback_data": "menu_lapor_sar"}],
    [{"text": "2. Info SAR", "callback_data": "menu_info_sar"}]
]

GREETING_MSG = MAIN_MENU_TEXT

SHORT_REPORT_WARNING = (
    "*Informasi Perlu Dilengkapi*\n\n"
    "Mohon berikan rincian tambahan: apa musibah yang dialami, perkiraan lokasi kejadian, dan berapa estimasi korban yang membutuhkan pertolongan."
)


class ChatbotEngine:
    """Thin orchestrator that delegates to specific state handlers."""
    
    def __init__(self):
        self.action_handler = ActionHandler()

    async def get_or_create_session(self, user_id: str, channel: str, db: AsyncSession) -> ChatSession:
        result = await db.execute(select(ChatSession).where(ChatSession.user_id == user_id))
        session = result.scalars().first()
        if not session:
            session = ChatSession(user_id=user_id, channel=channel, state="MAIN_MENU")
            
            # Auto-populate contact info from database if available (especially WhatsApp users)
            phone = None
            if channel == "whatsapp" and user_id.startswith("wa_"):
                phone = user_id[3:]
                session.contact_phone = phone
            
            if phone or session.contact_phone:
                lookup_phone = phone or session.contact_phone
                try:
                    from app.models.contact import Contact
                    contact_res = await db.execute(
                        select(Contact).where(Contact.phone_number == lookup_phone)
                    )
                    existing_contact = contact_res.scalar_one_or_none()
                    if existing_contact:
                        session.contact_name = existing_contact.name
                except Exception as e:
                    logger.warning(f"Failed to pre-populate contact info: {e}")
                    
            db.add(session)
            await db.commit()
            await db.refresh(session)
        return session

    def _update_history(self, session: ChatSession, role: str, content: str, buttons: list = None):
        try:
            history = json.loads(session.conversation_history)
        except Exception:
            history = []
            
        msg_obj = {
            "role": role, 
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        if buttons:
            msg_obj["buttons"] = buttons
            
        history.append(msg_obj)
        history = history[-20:]
        session.conversation_history = json.dumps(history)

    async def _broadcast_session(self, session: ChatSession, autopilot: bool, extracted_data: dict, db: AsyncSession = None):
        """Broadcast session updates over WebSocket to frontend clients."""
        try:
            try:
                history = json.loads(session.conversation_history)
            except Exception:
                history = []
                
            import asyncio
            asyncio.create_task(manager.broadcast({
                "type": "chat_message",
                "session_id": session.id,
                "user_id": session.user_id,
                "channel": session.channel,
                "state": session.state,
                "contact_name": session.contact_name,
                "contact_phone": session.contact_phone,
                "conversation_history": history,
                "extracted_data": extracted_data,
                "autopilot": autopilot,
                "updated_at": datetime.now().isoformat()
            }, db=db))
        except Exception as e:
            logger.error(f"Failed to broadcast WebSocket update: {e}")

    async def process_message(
        self, user_id: str, message_text: str, channel: str, db: AsyncSession, user_profile: dict = None
    ) -> dict:
        from app.services.rule_extractor import RuleExtractor
        # Load dictionary cache if not already loaded (lifespan pre-warmed it)
        if not RuleExtractor._cache_loaded:
            await RuleExtractor.load_cache(db)
        
        session = await self.get_or_create_session(user_id, channel, db)
        
        # 1. Update Profile info if available
        if user_profile:
            if user_profile.get("contact_name"):
                session.contact_name = user_profile.get("contact_name")[:100]
            if user_profile.get("contact_phone"):
                session.contact_phone = user_profile.get("contact_phone")[:50]
            if user_profile.get("platform_username") and not session.platform_username:
                session.platform_username = user_profile.get("platform_username")[:100]

        # ── Proactive Contact Sync from Chat ──
        if session.contact_phone:
            try:
                from app.models.contact import Contact
                contact_res = await db.execute(
                    select(Contact).where(Contact.phone_number == session.contact_phone)
                )
                existing_contact = contact_res.scalar_one_or_none()
                
                if existing_contact:
                    if session.contact_name and (not existing_contact.name or existing_contact.name.startswith("WA User") or existing_contact.name.startswith("Telegram User") or existing_contact.name.startswith("User ")):
                        existing_contact.name = session.contact_name
                    existing_contact.source = session.channel
                else:
                    new_contact = Contact(
                        phone_number=session.contact_phone,
                        name=session.contact_name or f"User {session.channel}",
                        source=session.channel,
                        notes=f"Kontak otomatis dari obrolan {session.channel}"
                    )
                    db.add(new_contact)
                    
                # Broadcast WS update
                await manager.broadcast({
                    "type": "new_contact", # Trigger invalidation in frontend
                    "payload": {"phone_number": session.contact_phone}
                }, db=db)
            except Exception as contact_err:
                logger.warning(f"Proactive contact sync failed for {session.contact_phone}: {contact_err}")

        # 2. Parse extracted_data and history
        try:
            extracted_data = json.loads(session.extracted_data)
        except Exception:
            extracted_data = {}

        # Auto-propagate contact details from session if not already in extracted_data
        has_updates = False
        if session.contact_phone and not extracted_data.get("pelapor_hp"):
            if session.contact_phone != "08123456789":
                extracted_data["pelapor_hp"] = session.contact_phone
                has_updates = True
            
        if session.contact_name and not extracted_data.get("pelapor_nama"):
            low_name = session.contact_name.lower()
            if not ("user" in low_name or "telegram" in low_name or "whatsapp" in low_name or len(session.contact_name) < 2):
                extracted_data["pelapor_nama"] = session.contact_name
                has_updates = True
                
        if has_updates:
            session.extracted_data = json.dumps(extracted_data)

        autopilot = extracted_data.get("_autopilot", True)

        # 3. Log user message in history
        self._update_history(session, "user", message_text)
        await db.commit()
        
        # Determine intent using AI classification (with exact match fast-paths)
        from app.services.llm_rag import llm_rag_service
        intent = await llm_rag_service.classify_user_intent(message_text, current_state=session.state, db=db)

        # Handle Reset / Mulai Baru
        if intent == "RESET":
            is_limited, limit_msg = await self._is_rate_limited(session, extracted_data, db)
            if is_limited:
                reply = f"*Batas Pengiriman Laporan Terlampaui*\n\n{limit_msg}"
                self._update_history(session, "assistant", reply)
                await db.commit()
                await self._broadcast_session(session, autopilot, extracted_data, db=db)
                return {"text": reply}
            return await self._reset_session(session, db, autopilot)

        # Handle Cek Status
        if intent == "CEK_STATUS" or session.state == "AWAITING_STATUS_QUERY":
            return await self._handle_status_check(session, db, autopilot, extracted_data, message_text=message_text)

        # Check if user explicitly clicked/typed a Lapor SAR menu command
        lapor_menu_triggers = {
            "lapor sar", "lapor", "1", "1.", "1. lapor sar", "1.lapor sar", "1 lapor sar", "menu_lapor_sar",
            "lapor sar cepat", "lapor cepat", "lapor sar kejadian", "lapor kejadian",
            "laporkan kejadian", "sos", "lapor cepat (sos)",
            "menu_lapor_cepat", "menu_lapor_kejadian", "/lapor"
        }
        msg_clean = message_text.strip().lower()
        is_lapor_menu_click = msg_clean in lapor_menu_triggers

        # Handle Lapor SAR Menu Selection (Only on explicit menu button clicks or commands)
        if is_lapor_menu_click:
            from app.core.config import settings
            base_url = settings.FRONTEND_URL.rstrip('/')
            is_public_url = base_url.startswith("https://") or (not any(h in base_url for h in [".lan", "localhost", "127.0.0.1"]))
            webview_url = f"{base_url}/location-picker?session_id={session.id}"
            
            # Telegram supports native location sharing button
            if session.channel == "telegram":
                buttons = [
                    {"text": "Bagikan Lokasi GPS Sekarang", "request_location": True},
                    "Info SAR"
                ]
            else:
                buttons = ["Lapor SAR", "Info SAR"]

            reply = (
                "*LAPOR SAR*\n"
                "Layanan Siaga Pelaporan Kedaruratan dan Musibah.\n\n"
                "Silakan jelaskan musibah yang dialami atau disaksikan:\n"
                "• Jenis kejadian (contoh: kapal mati mesin/tenggelam, orang hilang/hanyut, bencana)\n"
                "• Lokasi kejadian (nama perairan/pantai/desa, atau kirim titik GPS jika di lokasi)\n"
                "• Waktu kejadian\n"
                "• Estimasi jumlah korban yang membutuhkan pertolongan\n\n"
                f"Jika Anda berada langsung di lokasi kejadian, Anda juga dapat membuka [Peta Titik Darurat SAR]({webview_url}) untuk mengunci koordinat secara akurat.\n\n"
                "Ketik keterangan kejadian secara singkat atau kirimkan pesan suara/lokasi."
            )
            session.state = "AWAITING_REPORT"
            self._update_history(session, "assistant", reply, buttons=buttons)
            await db.commit()
            await self._broadcast_session(session, autopilot, extracted_data, db=db)
            return {"text": reply, "buttons": buttons}

        # Handle Info SAR
        if intent == "LAPOR_INFO":
            session.state = "MODE_BANTUAN"

            # Check if user asked a direct substantive question rather than just clicking the menu
            info_menu_keywords = {
                "info sar", "lapor sar info", "bantuan sar", "bantuan sar lainnya", 
                "info", "2", "2.", "/bantuan", "tanya sar", "bantuan", "menu info", "menu_info_sar"
            }
            if message_text.strip().lower() not in info_menu_keywords and len(message_text.strip().split()) >= 2:
                # Direct conversational answering without intermediate menu friction
                rag_answer = await llm_rag_service.answer_bantuan_sar(message_text, db)
                buttons = ["Lapor SAR", "Info SAR"]
                self._update_history(session, "assistant", rag_answer, buttons=buttons)
                await db.commit()
                await self._broadcast_session(session, autopilot, extracted_data, db=db)
                return {"text": rag_answer, "buttons": buttons}

            reply = (
                "*INFO SAR*\n"
                "Layanan Informasi Resmi, Regulasi, dan Standar Operasional Prosedur BASARNAS.\n\n"
                "Ajukan pertanyaan Anda mengenai regulasi SAR, prosedur penyelamatan, istilah kedaruratan, atau kontak unit operasional BASARNAS.\n\n"
                "Seluruh jawaban disusun secara faktual berdasarkan dokumen resmi sistem dan sumber internet terverifikasi.\n\n"
                "Contoh pertanyaan:\n"
                "• Bagaimana prosedur pelaporan orang hilang di laut?\n"
                "• Apa kriteria musibah yang termasuk Kondisi Membahayakan Manusia?\n"
                "• Berapa nomor kontak resmi siaga darurat BASARNAS?"
            )
            buttons = ["Lapor SAR", "Info SAR"]
            self._update_history(session, "assistant", reply, buttons=buttons)
            await db.commit()
            await self._broadcast_session(session, autopilot, extracted_data, db=db)
            return {"text": reply, "buttons": buttons}

        # If already in MODE_BANTUAN:
        if session.state == "MODE_BANTUAN":
            # Emergency Context Hijack: If user reports an incident while in info mode, immediately switch to report triage!
            if intent in ("DATA_PELAPORAN", "LAPOR_SAR", "LAPOR_CEPAT", "LAPOR_KEJADIAN"):
                session.state = "AWAITING_REPORT"
                # Fall through to the reporting state handler below
            else:
                rag_answer = await llm_rag_service.answer_bantuan_sar(message_text, db)
                buttons = ["Lapor SAR", "Info SAR"]
                self._update_history(session, "assistant", rag_answer, buttons=buttons)
                await db.commit()
                await self._broadcast_session(session, autopilot, extracted_data, db=db)
                return {"text": rag_answer, "buttons": buttons}

        # If in MAIN_MENU state:
        if session.state == "MAIN_MENU":
            if intent in ("DATA_PELAPORAN", "LAPOR_SAR", "LAPOR_CEPAT", "LAPOR_KEJADIAN"):
                session.state = "AWAITING_REPORT"
                # Fall through to the reporting state handler below
            elif intent in ("LAPOR_INFO", "BANTUAN_SAR"):
                session.state = "MODE_BANTUAN"
                rag_answer = await llm_rag_service.answer_bantuan_sar(message_text, db)
                buttons = ["Lapor SAR", "Info SAR"]
                self._update_history(session, "assistant", rag_answer, buttons=buttons)
                await db.commit()
                await self._broadcast_session(session, autopilot, extracted_data, db=db)
                return {"text": rag_answer, "buttons": buttons}
            else:
                reply = MAIN_MENU_TEXT
                self._update_history(session, "assistant", reply, buttons=MAIN_MENU_BUTTONS)
                await db.commit()
                await self._broadcast_session(session, autopilot, extracted_data, db=db)
                return {
                    "text": reply,
                    "buttons": MAIN_MENU_BUTTONS,
                    "inline_keyboard": MAIN_MENU_INLINE_KEYBOARD
                }

        # Check rate limit before entering report state machine for new chronology
        if session.state == "AWAITING_REPORT":
            is_limited, limit_msg = await self._is_rate_limited(session, extracted_data, db)
            if is_limited:
                reply = f"*Batas Pengiriman Laporan Terlampaui*\n\n{limit_msg}"
                self._update_history(session, "assistant", reply)
                await db.commit()
                await self._broadcast_session(session, autopilot, extracted_data, db=db)
                return {"text": reply}

        # Check autopilot
        if not autopilot:
            session.updated_at = datetime.now()
            await db.commit()
            await self._broadcast_session(session, False, extracted_data, db=db)
            return {"status": "bot_paused"}

        # 4. State Handlers Delegation
        from app.engine.state_handlers import get_state_handler
        handler = get_state_handler(session.state)
        res = await handler.handle(self, session, message_text, extracted_data, db, autopilot)

        await db.commit()
        return res

    # =====================================================================
    # API Compatibility Wrappers & Helpers
    # =====================================================================

    async def _validate_and_route(
        self, session: ChatSession, extracted_data: dict, db: AsyncSession, autopilot: bool
    ) -> dict:
        sequence = await self._get_full_question_sequence(session, extracted_data, db)
        
        next_field = None
        for field in sequence:
            val = extracted_data.get(field)
            
            # Special check for korban
            if field == "korban":
                if extracted_data.get("_explicit_korban"):
                    continue
                    
                has_number = False
                if val:
                    val_str = str(val).lower()
                    if re.search(r'\d+', val_str):
                        has_number = True
                    else:
                        from app.services.rule_extractor import RuleExtractor
                        num_words = ["satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "seorang", "seorang diri", "abk", "nelayan", "penumpang", "kru", "awak", "korban"]
                        if RuleExtractor._dictionary_cache:
                            db_num_words = []
                            for cat in ["QUANTIFIER", "VICTIM_ROLE"]:
                                for item in RuleExtractor._dictionary_cache.get(cat, []):
                                    db_num_words.append(item["word"].lower())
                            if db_num_words:
                                num_words = list(set(num_words + db_num_words))
                        if any(nw in val_str for nw in num_words):
                            has_number = True
                            
                is_missing = not val or str(val).strip() in ("", "-", "0", "NIHIL") or not has_number
                has_valid_list = False
                dk = extracted_data.get("data_korban")
                if isinstance(dk, list) and len(dk) > 0:
                    has_valid_list = True
                elif isinstance(dk, str) and dk.strip() not in ("", "-", "NIHIL", "Belum ada data korban."):
                    has_valid_list = True
                    
                if is_missing and not has_valid_list:
                    next_field = field
                    break
                continue
                
            # Special check for reporter_location
            if field == "reporter_location":
                if not extracted_data.get("is_current_location_shared") and not extracted_data.get("reporter_location"):
                    next_field = field
                    break
                continue

            # Check other missing fields
            is_vehicle_field = field in ["data_kapal", "data_pesawat", "data_alat"]
            if is_vehicle_field:
                if not val and not extracted_data.get(f"_explicit_{field}"):
                    next_field = field
                    break
            else:
                if not val and not extracted_data.get(f"_explicit_{field}"):
                    next_field = field
                    break

        if next_field:
            next_state = FIELD_STATE_MAP.get(next_field)
            if not next_state:
                return await self._enter_confirming(session, extracted_data, db, autopilot)
                
            session.state = next_state
            
            # Resolve question & buttons dynamically from FieldProcessor
            from app.engine.field_processors import get_field_processor
            processor = get_field_processor(next_field)
            q_text, q_buttons = processor.get_question(session, extracted_data)
            
            self._update_history(session, "assistant", q_text, buttons=q_buttons)
            await self._broadcast_session(session, autopilot, extracted_data, db=db)
            
            if q_buttons:
                return {"text": q_text, "buttons": list(q_buttons)}
            return {"text": q_text}
            
        # If all fields in sequence are filled
        return await self._enter_confirming(session, extracted_data, db, autopilot)

    async def _get_full_question_sequence(self, session: ChatSession, extracted_data: dict, db: AsyncSession) -> list:
        sequence = list(CORE_QUESTION_ORDER) # ["waktu", "lokasi_teks", "korban"]

        # Insert koordinat & GPS question after lokasi_teks if not explicitly provided by user
        if not extracted_data.get("_explicit_koordinat"):
            lok_idx = sequence.index("lokasi_teks")
            sequence.insert(lok_idx + 1, "koordinat")

        # Victim condition breakdown - skip if count is unknown/Belum Diketahui
        korban_val = str(extracted_data.get("korban") or "").lower()
        is_korban_unknown = not korban_val or "belum tahu" in korban_val or "belum diketahui" in korban_val or "nihil" in korban_val
        
        if not is_korban_unknown:
            sequence.append("korban_kondisi")
            
        sequence.append("data_korban")

        # Dynamic vehicle fields depending on classification and water context
        jenis = str(extracted_data.get("jenis_kejadian", "")).lower()

        # Check if this is a water/sea incident for KMM
        is_kmm = "kmm" in jenis or (not jenis and not extracted_data.get("jenis_kejadian"))
        is_water = False
        text_to_check = (
            str(extracted_data.get("lokasi_teks") or "") + " " +
            str(extracted_data.get("kronologi") or "") + " " +
            str(extracted_data.get("jenis_kejadian") or "")
        ).lower()
        water_keywords = [
            "laut", "pantai", "perairan", "mancing", "tenggelam", "hanyut", "sungai", 
            "danau", "selat", "dermaga", "pompong", "perahu", "kapal", "senoa", "piwang"
        ]
        if any(kw in text_to_check for kw in water_keywords):
            is_water = True

        lat = extracted_data.get("koordinat_lat")
        lng = extracted_data.get("koordinat_lng")
        if lat is not None and lng is not None:
            try:
                from app.services.geocoding_service import geocoding_service
                if geocoding_service.is_coordinate_in_water(float(lat), float(lng)):
                    is_water = True
            except Exception as e:
                logger.warning(f"Failed to check water coordinates: {e}")

        # Auto-detect pakai_kapal if ship data was already extracted
        if extracted_data.get("data_kapal") and not extracted_data.get("pakai_kapal"):
            extracted_data["pakai_kapal"] = "Ya"
            extracted_data["_explicit_pakai_kapal"] = True

        if is_kmm and is_water:
            sequence.append("pakai_kapal")
            if extracted_data.get("pakai_kapal") == "Ya":
                sequence.append("data_kapal")
        else:
            if "kapal" in jenis or "laut" in jenis or "perairan" in jenis:
                sequence.append("data_kapal")

        if "pesawat" in jenis or "udara" in jenis:
            sequence.append("data_pesawat")
        if "alat" in jenis or "lantas" in jenis or "kendaraan" in jenis:
            sequence.append("data_alat")

        # Eviden attachments
        if not extracted_data.get("eviden"):
            sequence.append("eviden")

        # Pelapor details
        sequence.append("pelapor_nama")
        sequence.append("pelapor_hp")
        sequence.append("pelapor_hubungan")

        # Logika: Jika pelapor adalah Korban, dan koordinat kejadian sudah terisi,
        # otomatis salin koordinat kejadian ke koordinat pelapor (pelapor_lat/pelapor_lng)
        # dan bypass verifikasi lokasi pelapor.
        if extracted_data.get("pelapor_hubungan") == "Korban":
            lat_val = extracted_data.get("koordinat_lat")
            lng_val = extracted_data.get("koordinat_lng")
            if lat_val is not None and lng_val is not None:
                extracted_data["pelapor_lat"] = lat_val
                extracted_data["pelapor_lng"] = lng_val
                extracted_data["is_current_location_shared"] = True
                extracted_data["reporter_location"] = "Sudah terverifikasi (Pelapor adalah Korban)"
                session.extracted_data = json.dumps(extracted_data)

        # Mandatory GPS verification
        if not extracted_data.get("is_current_location_shared"):
            sequence.append("reporter_location")

        return sequence

    async def _enter_confirming(
        self, session: ChatSession, extracted_data: dict, db: AsyncSession, autopilot: bool
    ) -> dict:
        session.state = "CONFIRMING"

        # 1. Run Unified LLM Refinement Pass once on all collected raw fields
        try:
            from app.services.llm_rag import LLMRagService
            llm_rag = LLMRagService()
            context = await llm_rag.get_dictionary_context(db)
            
            # Format current time as local reference timezone (WIB)
            from datetime import timezone, timedelta
            tz = timezone(timedelta(hours=7))
            current_time_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S WIB")
            
            logger.info("Executing single unified LLM draft refinement pass.")
            refined = await llm_rag.refine_full_report_draft(extracted_data, current_time_str, context, db)
            if refined and isinstance(refined, dict):
                extracted_data.update(refined)
                session.extracted_data = json.dumps(extracted_data)
                await db.commit()
                logger.info(f"Report draft refined successfully: {extracted_data}")
        except Exception as e:
            logger.error(f"Failed to execute final LLM draft refinement: {e}")

        # Double check critical fields
        missing_critical = []
        if self._is_field_missing(extracted_data.get("jenis_kejadian", "")):
            missing_critical.append("Jenis Kejadian")
        if self._is_field_missing(extracted_data.get("lokasi_teks", "")):
            missing_critical.append("Lokasi Kejadian")
        if self._is_field_missing(extracted_data.get("waktu", "")):
            missing_critical.append("Waktu Kejadian")

        if missing_critical:
            reply = (
                f"*Peringatan: Laporan Belum Lengkap*\n\n"
                f"Informasi penting berikut masih kosong: *{', '.join(missing_critical)}*.\n\n"
                f"Mohon lengkapi terlebih dahulu demi kelancaran proses penyelamatan.\n"
                f"Silakan ketuk *Lengkapi* untuk melengkapi data, atau *Batalkan* untuk menghapus draf."
            )
            self._update_history(session, "assistant", reply, buttons=["Lengkapi", "Batalkan"])
            await self._broadcast_session(session, autopilot, extracted_data)
            return {"text": reply, "buttons": ["Lengkapi", "Batalkan"]}

        # Prepare summary block with indicator icons
        summary_lines = ["*RINGKASAN DATA LAPORAN SAR*\n"]
        field_labels = {
            "jenis_kejadian": "Klasifikasi Musibah",
            "waktu": "Waktu Kejadian (PDTW)",
            "lokasi_teks": "Lokasi Kejadian",
            "korban": "Estimasi Korban",
            "korban_kondisi": "Kondisi Korban",
            "data_kapal": "Data Kapal",
            "data_pesawat": "Data Pesawat",
            "data_alat": "Data Kendaraan/Alat",
            "kronologi": "Kronologi"
        }

        for key, label in field_labels.items():
            val = extracted_data.get(key, "")
            if key == "kronologi" and val:
                val = val[:100] + "..." if len(val) > 100 else val
            
            if val and not self._is_field_missing(val):
                summary_lines.append(f"• *{label}:* {val}")
            elif key in ["data_kapal", "data_pesawat", "data_alat"]:
                continue
            else:
                summary_lines.append(f"• *{label}:* _(Belum terisi)_")

        summary_lines.append("\n━━━━━━━━━━━━━━━━━━━━━")
        summary_lines.append("*IDENTITAS PELAPOR*")
        summary_lines.append(f"• Nama: {extracted_data.get('pelapor_nama') or session.contact_name or 'Tidak tersedia'}")
        summary_lines.append(f"• No. Kontak: {extracted_data.get('pelapor_hp') or session.contact_phone or 'Tidak tersedia'}")
        summary_lines.append(f"• Hubungan: {extracted_data.get('pelapor_hubungan') or 'Masyarakat/Saksi'}")
        summary_lines.append(f"• Lokasi Pelapor: {'Terverifikasi GPS' if extracted_data.get('is_current_location_shared') else 'Belum terverifikasi GPS'}")

        summary = "\n".join(summary_lines)

        reply = (
            f"{summary}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "*KONFIRMASI PENGIRIMAN LAPORAN*\n\n"
            "Apakah seluruh data laporan di atas sudah benar?\n\n"
            "Pilih *Ya* untuk meneruskan laporan ke Command Center BASARNAS sekarang, pilih *Lengkapi* untuk memperbaiki rincian, atau pilih *Batalkan* untuk menghapus draf."
        )
        
        self._update_history(session, "assistant", reply, buttons=["Ya", "Lengkapi", "Batalkan"])
        await self._broadcast_session(session, autopilot, extracted_data, db=db)
        
        return {"text": reply, "buttons": ["Ya", "Lengkapi", "Batalkan"]}

    async def _handle_status_check(
        self, session: ChatSession, db: AsyncSession, autopilot: bool, extracted_data: dict, message_text: str = ""
    ) -> dict:
        from app.models.report import Report
        
        raw_text = (message_text or "").strip()
        report_no_match = re.search(r'\b(SAR-[A-Z0-9\-]+)\b', raw_text, re.IGNORECASE)
        target_report_no = report_no_match.group(1).upper() if report_no_match else None
        
        phone_match = re.search(r'\b(08\d{8,12}|62\d{8,12}|\+62\d{8,12})\b', raw_text)
        searched_phone = phone_match.group(1) if phone_match else None
        
        reports = []

        if target_report_no:
            result = await db.execute(
                select(Report).where(Report.report_number.ilike(target_report_no)).order_by(Report.id.desc())
            )
            reports = result.scalars().all()
            if not reports:
                session.state = "AWAITING_STATUS_QUERY"
                reply = (
                    "*Laporan Tidak Ditemukan*\n\n"
                    f"Tidak ditemukan laporan SAR dengan nomor registrasi `{target_report_no}`.\n\n"
                    "Mohon periksa kembali nomor laporan Anda, atau ketik nomor handphone yang Anda gunakan saat melapor."
                )
                buttons = ["Buat Laporan Baru", "Menu Utama"]
                self._update_history(session, "assistant", reply, buttons=buttons)
                await db.commit()
                await self._broadcast_session(session, autopilot, extracted_data, db=db)
                return {"text": reply, "buttons": buttons}
        else:
            # Resolve phone from message, session, or extracted_data
            phone = searched_phone or session.contact_phone
            if not phone:
                if session.user_id.startswith("wa_"):
                    phone = session.user_id[3:]
                elif session.user_id.startswith("tg_"):
                    phone = extracted_data.get("pelapor_hp")
            
            last_report_no = extracted_data.get("_last_report_no")
            
            if searched_phone or phone:
                target_phone = searched_phone or phone
                result = await db.execute(
                    select(Report).where(Report.reporter_phone == target_phone).order_by(Report.id.desc()).limit(3)
                )
                reports = result.scalars().all()
                if not reports:
                    session.state = "AWAITING_STATUS_QUERY"
                    reply = (
                        "*Tidak Ada Laporan Ditemukan*\n\n"
                        f"Kami tidak menemukan adanya laporan darurat aktif yang terdaftar menggunakan nomor telepon (*{target_phone}*).\n\n"
                        "Silakan ketik **Nomor Registrasi Laporan** Anda jika ada (contoh: `SAR-202610-001`), atau ketik */start* untuk membuat laporan baru."
                    )
                    buttons = ["Buat Laporan Baru", "Menu Utama"]
                    self._update_history(session, "assistant", reply, buttons=buttons)
                    await db.commit()
                    await self._broadcast_session(session, autopilot, extracted_data, db=db)
                    return {"text": reply, "buttons": buttons}
            elif last_report_no:
                result = await db.execute(
                    select(Report).where(Report.report_number.ilike(last_report_no)).order_by(Report.id.desc())
                )
                reports = result.scalars().all()
            else:
                session.state = "AWAITING_STATUS_QUERY"
                reply = (
                    "*PELACAKAN STATUS LAPORAN SAR*\n\n"
                    "Silakan ketik **Nomor Registrasi Laporan** Anda (contoh: `SAR-202610-001`) atau kirimkan **Nomor Handphone** yang digunakan saat melapor.\n\n"
                    "Petugas piket siaga memperbarui status penanganan secara berkala."
                )
                buttons = ["Menu Utama"]
                self._update_history(session, "assistant", reply, buttons=buttons)
                await db.commit()
                await self._broadcast_session(session, autopilot, extracted_data, db=db)
                return {"text": reply, "buttons": buttons}

        # If reports found, show formatted status and reset state to AWAITING_REPORT
        session.state = "AWAITING_REPORT"
        reply_lines = ["*STATUS PENANGANAN LAPORAN SAR*\n"]
        
        status_friendly = {
            "PENDING": "*PENDING* (Sedang Diverifikasi Petugas Piket)",
            "AKTIF": "*AKTIF* (Operasi SAR Sedang Berlangsung / Tim Dikerahkan)",
            "TIDAK_AKTIF": "*TIDAK AKTIF / SELESAI* (Operasi SAR Telah Ditutup)",
            "SALAH_LAPORAN": "*BATAL / DUPLIKAT* (Laporan Dibatalkan/Duplikat)"
        }

        for i, rep in enumerate(reports, 1):
            status_text = status_friendly.get(rep.status, f"*{rep.status}*")
            pos_sar = rep.pos_sar_terdekat or "Command Center Kantor SAR"
            
            dt = rep.created_at
            date_str = dt.strftime("%d %B %Y pukul %H:%M WIB") if dt else "Waktu tidak tercatat"
            lokasi = rep.lokasi_teks or "Perairan"
            
            rep_block = (
                f"{i}. *No Laporan:* `{rep.no_laporan}`\n"
                f"   • *Jenis Musibah:* {rep.jenis_kejadian or 'KMM'}\n"
                f"   • *Tanggal Lapor:* {date_str}\n"
                f"   • *Lokasi:* {lokasi}\n"
                f"   • *Unit Menangani:* {pos_sar}\n"
                f"   • *Status:* {status_text}\n"
            )
            reply_lines.append(rep_block)

        reply_lines.append("━━━━━━━━━━━━━━━━━━━━━\n"
                           "Petugas kami akan menghubungi Anda secara langsung jika diperlukan pendalaman informasi lebih lanjut di lapangan.\n\n"
                           "Ketik */start* atau klik tombol di bawah untuk membuat laporan baru.")

        reply = "\n".join(reply_lines)
        
        buttons = ["Buat Laporan Baru", "Cek Status Laporan"]
        self._update_history(session, "assistant", reply, buttons=buttons)
        await db.commit()
        await self._broadcast_session(session, autopilot, extracted_data, db=db)
        
        return {"text": reply, "buttons": buttons}

    async def _reset_session(self, session: ChatSession, db: AsyncSession, autopilot: bool) -> dict:
        session.state = "MAIN_MENU"
        
        # Ensure contact_phone is populated from user_id for WhatsApp
        if session.channel == "whatsapp" and session.user_id.startswith("wa_") and not session.contact_phone:
            session.contact_phone = session.user_id[3:]
            
        # Try to look up existing Contact if we have contact_phone but missing contact_name
        if session.contact_phone and not session.contact_name:
            try:
                from app.models.contact import Contact
                contact_res = await db.execute(
                    select(Contact).where(Contact.phone_number == session.contact_phone)
                )
                existing_contact = contact_res.scalar_one_or_none()
                if existing_contact:
                    session.contact_name = existing_contact.name
            except Exception as e:
                logger.warning(f"Failed to lookup contact during session reset: {e}")
                
        initial_data = {"_autopilot": autopilot}
        if session.contact_name:
            initial_data["pelapor_nama"] = session.contact_name
        if session.contact_phone:
            initial_data["pelapor_hp"] = session.contact_phone
            
        session.extracted_data = json.dumps(initial_data)
        session.conversation_history = "[]"
        await db.commit()

        reply = MAIN_MENU_TEXT
        buttons = MAIN_MENU_BUTTONS
        inline_kb = MAIN_MENU_INLINE_KEYBOARD
            
        self._update_history(session, "assistant", reply, buttons=buttons)
        await db.commit()
        await self._broadcast_session(session, autopilot, initial_data, db=db)

        return {"text": reply, "buttons": buttons, "inline_keyboard": inline_kb}

    async def _is_rate_limited(self, session: ChatSession, extracted_data: dict, db: AsyncSession) -> tuple[bool, str]:
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        
        completed_reports = extracted_data.get("_completed_reports", [])
        valid_timestamps = []
        for ts_str in completed_reports:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= one_hour_ago:
                    valid_timestamps.append(ts.isoformat())
            except Exception:
                pass
                
        extracted_data["_completed_reports"] = valid_timestamps
        session.extracted_data = json.dumps(extracted_data)
        
        if len(valid_timestamps) >= 3:
            return True, "Anda telah mencapai batas maksimal pembuatan laporan (maksimal 3 laporan per jam) untuk menghindari spam."
            
        phone = session.contact_phone or extracted_data.get("pelapor_hp")
        if phone:
            phone_clean = re.sub(r'\D', '', str(phone))
            if len(phone_clean) >= 8:
                try:
                    from app.models.report import Report
                    from sqlalchemy import func, literal
                    
                    cleaned_db_phone = func.regexp_replace(Report.reporter_phone, r'[^\d]', '', 'g')
                    stmt = select(func.count(Report.id)).where(
                        Report.created_at >= one_hour_ago,
                        Report.reporter_phone.is_not(None),
                        (cleaned_db_phone.like(f"%{phone_clean}%")) |
                        (literal(phone_clean).like(func.concat("%", cleaned_db_phone, "%")))
                    )
                    result = await db.execute(stmt)
                    val = result.scalar_one()
                    match_count = int(val) if isinstance(val, (int, float)) else 0
                            
                    if match_count >= 3:
                        return True, "Nomor telepon Anda telah digunakan untuk membuat laporan maksimal (3 laporan per jam) untuk menghindari spam."
                except Exception as e:
                    logger.warning(f"Database rate limit check non-critical failure: {e}")
                    
        return False, ""

    async def _is_outside_working_area(self, extracted_data: dict, db: AsyncSession) -> bool:
        lat = extracted_data.get("koordinat_lat")
        lng = extracted_data.get("koordinat_lng")
        
        if not lat or not lng:
            direct_coord = extracted_data.get("koordinat") or ""
            from app.services.geo_service import parse_coordinates
            coords = parse_coordinates(str(direct_coord))
            if coords:
                lat, lng = coords

        tenant_slug = "pusat"
        if db is not None:
            db_info = getattr(db, "info", None)
            if isinstance(db_info, dict):
                tenant_slug = db_info.get("tenant_slug", "pusat")
            else:
                tenant_slug = "natuna"

        if lat and lng:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
            except (ValueError, TypeError):
                lat_f, lng_f = None, None

            if lat_f is not None and lng_f is not None:
                # 1. Wilayah Teritorial Indonesia (-12 to 8 LU/LS, 94 to 142 BT)
                is_indonesia = (-12.0 <= lat_f <= 8.0 and 94.0 <= lng_f <= 142.0)
                if not is_indonesia:
                    return True

                # Tenant Pusat meng-cover seluruh Indonesia
                if tenant_slug == "pusat":
                    return False

                # 2. Cek jarak ke pos SAR terdekat dari tenant ini jika ada
                try:
                    from app.models.settings_models import Location
                    from app.services.geo_service import find_nearest_location
                    loc_result = await db.execute(select(Location))
                    locations = loc_result.scalars().all()
                    if isinstance(locations, list) and len(locations) > 0:
                        nearest = find_nearest_location(lat_f, lng_f, locations)
                        if nearest:
                            return nearest.get("distance_nm", 0) > 150.0
                except Exception:
                    pass

                # Fallback untuk tenant wilayah (misal mock / natuna) tanpa pos SAR di DB
                if tenant_slug in ("natuna", "test"):
                    if not (0.5 <= lat_f <= 5.5 and 104.5 <= lng_f <= 110.0):
                        return True

                return False
            
        lokasi_teks = str(extracted_data.get("lokasi_teks") or "").lower()
        if lokasi_teks:
            # Tenant Pusat tidak membatasi kota dalam negeri
            if tenant_slug == "pusat":
                out_foreign = ["singapura", "singapore", "malaysia", "thailand", "vietnam", "australia", "filipina"]
                if any(kw in lokasi_teks for kw in out_foreign):
                    return True
                return False

            if tenant_slug in ("natuna", "test"):
                out_keywords = [
                    "jakarta", "pontianak", "singkawang", "ketapang", "sambas", "batam", "tanjungpinang", 
                    "bintan", "karimun", "lingga", "riau daratan", "pekanbaru", "padang", "medan", "aceh", 
                    "jawa", "bali", "surabaya", "semarang", "bandung", "lampung", "palembang", "bengkulu", 
                    "jambi", "bangka", "belitung", "kalimantan", "sulawesi", "maluku", "papua"
                ]
                if any(kw in lokasi_teks for kw in out_keywords):
                    if "natuna" not in lokasi_teks and "anambas" not in lokasi_teks and "jemaja" not in lokasi_teks:
                        return True
                    
        return False

    def _is_generic_greeting(self, message: str, extracted_data: dict) -> bool:
        msg = message.strip().lower()
        
        greetings = {
            "report", "help", "lapor", "tolong", "basarnas", "tim sar", "halo", "misi", "p", "halo basarnas", "halo tim sar",
            "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "emergency", "assalamualaikum",
            "darurat", "sar", "sarbot", "bantu", "bantuan", "lapor basarnas", "lapor tim sar", "lapor sar", "start", "/start"
        }
        
        if msg in greetings or len(msg) < 6:
            if not extracted_data.get("lokasi_teks") and not extracted_data.get("waktu") and not extracted_data.get("korban"):
                return True
                
        return False



    @staticmethod
    def _is_field_missing(value: str) -> bool:
        if not value:
            return True
        missing_markers = ["tidak diketahui", "belum diketahui", "belum tahu", "unknown", "n/a", "-", "nihil", "tidak ada"]
        return str(value).strip().lower() in missing_markers


# Export singleton instance
chatbot_engine = ChatbotEngine()
