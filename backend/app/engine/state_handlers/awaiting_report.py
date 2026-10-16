import json
import logging
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.state_handlers.base import BaseStateHandler

if TYPE_CHECKING:
    from app.engine.chatbot_engine import ChatbotEngine

logger = logging.getLogger(__name__)

class AwaitingReportStateHandler(BaseStateHandler):
    """Handles the first message reporting an incident (AWAITING_REPORT state)."""

    async def handle(
        self, engine: "ChatbotEngine", session: ChatSession, message: str, extracted_data: dict, db: AsyncSession, autopilot: bool
    ) -> dict:
        from app.engine.chatbot_engine import SHORT_REPORT_WARNING, extract_incident_data
        
        msg_clean = message.strip().lower()
        
        # 1. Check if the user selected one of the 5 categories (clicked button or typed)
        category_map = {
            "kecelakaan kapal": "Laka Kapal",
            "kapal": "Laka Kapal",
            "musibah laut": "Laka Kapal",
            "kecelakaan pesawat": "Laka Pesawat",
            "pesawat": "Laka Pesawat",
            "udara": "Laka Pesawat",
            "kecelakaan penanganan khusus (kpk)": "KPK",
            "kecelakaan khusus": "KPK",
            "kpk": "KPK",
            "bencana": "Bencana",
            "bencana alam": "Bencana",
            "kondisi membahayakan manusia (kmm)": "KMM",
            "kmm": "KMM",
            "kondisi membahayakan manusia": "KMM"
        }
        
        selected_category = None
        for key, val in category_map.items():
            if msg_clean == key:
                selected_category = val
                break
                
        if selected_category:
            extracted_data["jenis_kejadian"] = selected_category
            session.extracted_data = json.dumps(extracted_data)
            await db.commit()
            
            friendly_names = {
                "Laka Kapal": "*Kategori Terpilih:* Laka Kapal.",
                "Laka Pesawat": "*Kategori Terpilih:* Laka Pesawat.",
                "KPK": "*Kategori Terpilih:* KPK (Kecelakaan dengan Penanganan Khusus).",
                "Bencana": "*Kategori Terpilih:* Bencana Alam.",
                "KMM": "*Kategori Terpilih:* KMM (Kondisi Membahayakan Manusia)."
            }
            confirm_msg = friendly_names[selected_category]
            
            # Pre-fill profile info if not already captured
            if session.contact_name and not extracted_data.get("pelapor_nama"):
                extracted_data["pelapor_nama"] = session.contact_name
            if session.contact_phone and not extracted_data.get("pelapor_hp"):
                extracted_data["pelapor_hp"] = session.contact_phone
            session.extracted_data = json.dumps(extracted_data)
            
            route_res = await engine._validate_and_route(session, extracted_data, db, autopilot)
            route_res["text"] = f"{confirm_msg}\n\n{route_res['text']}"
            return route_res

        # 2. Check if the message is a shared GPS coordinate (bypass LLM for fast SOS geolocation)
        from app.services.rule_extractor import RuleExtractor
        coords = RuleExtractor.extract_koordinat(message.strip())
        if coords:
            extracted_data["koordinat_lat"] = coords[0]
            extracted_data["koordinat_lng"] = coords[1]
            extracted_data["koordinat"] = message.strip()
            if not extracted_data.get("kronologi"):
                extracted_data["kronologi"] = "Melaporkan SOS lokasi GPS."
            
            # Pre-fill profile info if not already captured
            if session.contact_name and not extracted_data.get("pelapor_nama"):
                extracted_data["pelapor_nama"] = session.contact_name
            if session.contact_phone and not extracted_data.get("pelapor_hp"):
                extracted_data["pelapor_hp"] = session.contact_phone
                
            session.extracted_data = json.dumps(extracted_data)
            await db.commit()
            return await engine._validate_and_route(session, extracted_data, db, autopilot)

        # 3. Run Pipeline Extraction (Use AI/LLM for initial report chronology)
        try:
            history_list = json.loads(session.conversation_history)
        except Exception:
            history_list = []
            
        new_data = await extract_incident_data(message, db, session.user_id, history_list, use_llm=True)
        extracted_data.update(new_data)
        
        # 3. Check if the message is a generic opening greeting/phrase
        if engine._is_generic_greeting(message, extracted_data):
            reply = (
                "*Pusat Pelayanan Darurat - Layanan Siaga Pencarian dan Pertolongan (SAR)*\n\n"
                "Ada keadaan darurat atau musibah apa yang ingin Anda laporkan?\n\n"
                "Jelaskan kejadiannya secara singkat dan sebutkan lokasinya saat ini.\n"
                "_(Anda juga dapat mengirimkan rekaman suara)_"
            )
            engine._update_history(session, "assistant", reply, buttons=[])
            await db.commit()
            await engine._broadcast_session(session, autopilot, extracted_data)
            return {"text": reply, "buttons": []}

        # 4. Check if the message is too short
        if len(message.strip()) < 5 and message.strip() not in ("", "msg"):
            reply = SHORT_REPORT_WARNING
            engine._update_history(session, "assistant", reply)
            await db.commit()
            await engine._broadcast_session(session, autopilot, extracted_data)
            return {"text": reply}

        # Force kronologi to be the original report story
        if not extracted_data.get("kronologi"):
            extracted_data["kronologi"] = message
            
        # Automatically classify the incident based on the chronology text against DB classifications
        try:
            from app.services.classification_service import match_classification
            matched_cls = await match_classification(message, db)
            if matched_cls:
                extracted_data["jenis_kejadian"] = matched_cls
            elif not extracted_data.get("jenis_kejadian"):
                extracted_data["jenis_kejadian"] = "KMM"  # Fallback to KMM if no keywords match
        except Exception as e:
            logger.warning(f"Failed to auto-classify chronology: {e}")
            if not extracted_data.get("jenis_kejadian"):
                extracted_data["jenis_kejadian"] = "KMM"
            
        # Pre-fill profile info if not already captured
        try:
            c_name = getattr(session, "contact_name", None)
            c_phone = getattr(session, "contact_phone", None)
        except Exception:
            c_name = None
            c_phone = None

        if c_name and not extracted_data.get("pelapor_nama"):
            extracted_data["pelapor_nama"] = c_name
        if c_phone and not extracted_data.get("pelapor_hp"):
            extracted_data["pelapor_hp"] = c_phone

        # Save extracted
        session.extracted_data = json.dumps(extracted_data)

        # Validate and route to next missing question
        return await engine._validate_and_route(session, extracted_data, db, autopilot)
