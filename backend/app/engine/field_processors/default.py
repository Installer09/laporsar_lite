import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class DefaultFieldProcessor(BaseFieldProcessor):
    """Processes and validates generic fallback fields (e.g. 'pelapor_nama', 'pelapor_hp', 'pelapor_hubungan')."""

    def __init__(self, field_name: str):
        self.field_name = field_name

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        
        # Specific handling for pelapor_hp (Phone Number Validation)
        if self.field_name == "pelapor_hp":
            val_lower = answer_clean.lower()
            
            # Check if one-tap button was selected
            if val_lower == "gunakan nomor aktif ini" and session.contact_phone:
                extracted_data["pelapor_hp"] = session.contact_phone
                extracted_data["_explicit_pelapor_hp"] = True
                return True, extracted_data
                
            # Otherwise, perform robust syntax validation and normalization
            # 1. Clean non-digits (keep leading '+' if present)
            import re
            is_plus_prefix = answer_clean.startswith("+")
            cleaned = re.sub(r"\D", "", answer_clean)
            if is_plus_prefix:
                cleaned = "+" + cleaned
                
            # 2. Normalize standard prefix (08 / 628 / +628) or allow satellite phones (+88)
            digit_only = re.sub(r"\D", "", cleaned)
            is_sat_phone = cleaned.startswith("+88") or cleaned.startswith("88")
            
            if not is_sat_phone:
                starts_valid = (
                    cleaned.startswith("08") or 
                    cleaned.startswith("628") or 
                    cleaned.startswith("+628")
                )
                if not starts_valid:
                    reply = (
                        "⚠️ *Nomor Telepon Tidak Valid*\n\n"
                        "Mohon masukkan nomor telepon/WhatsApp yang aktif.\n"
                        "Contoh: _081234567890_"
                    )
                    buttons = ["Gunakan Nomor Aktif Ini"] if session.contact_phone else []
                    return False, {"text": reply, "buttons": buttons}
            
            # 3. Check digit count limits (between 10 and 15 digits)
            if len(digit_only) < 10 or len(digit_only) > 15:
                reply = (
                    "⚠️ *Nomor Telepon Kurang/Lebih Panjang*\n\n"
                    "Mohon periksa kembali nomor telepon yang Anda masukkan."
                )
                buttons = ["Gunakan Nomor Aktif Ini"] if session.contact_phone else []
                return False, {"text": reply, "buttons": buttons}
                
            # Save normalized phone number
            extracted_data["pelapor_hp"] = cleaned
            extracted_data["_explicit_pelapor_hp"] = True
            session.contact_phone = cleaned
            return True, extracted_data

        # Specific handling for pakai_kapal
        if self.field_name == "pakai_kapal":
            val_lower = answer_clean.lower()
            if any(yes_w in val_lower for yes_w in ["ya", "y", "betul", "benar", "ada", "pakai", "pake", "pompong", "perahu", "kapal", "boat", "jongkong"]):
                extracted_data["pakai_kapal"] = "Ya"
                prev_jenis = extracted_data.get("jenis_kejadian")
                if not prev_jenis or prev_jenis in ("KMM", "Kondisi Membahayakan Manusia", "Kecelakaan Kapal", "Laka Kapal"):
                    extracted_data["jenis_kejadian"] = "Kecelakaan Kapal"
            elif any(no_w in val_lower for no_w in ["tidak", "tidak ada", "bukan", "enggak", "gak", "nggak", "ndak", "tdk"]):
                extracted_data["pakai_kapal"] = "Tidak"
                prev_jenis = extracted_data.get("jenis_kejadian")
                if not prev_jenis or prev_jenis in ("KMM", "Kondisi Membahayakan Manusia", "Kecelakaan Kapal", "Laka Kapal"):
                    extracted_data["jenis_kejadian"] = "Kondisi Membahayakan Manusia"
            else:
                extracted_data["pakai_kapal"] = "Belum Tahu"
            extracted_data["_explicit_pakai_kapal"] = True
            return True, extracted_data

        # Fallback to standard logic for other fields (pelapor_nama, pelapor_hubungan)
        nlp_val = None
        try:
            import json
            from app.services.incident_data_service import extract_incident_data
            try:
                history_list = json.loads(session.conversation_history)
            except Exception:
                history_list = []
            nlp_data = await extract_incident_data(message, db, session.user_id, history_list, use_llm=False)
            if nlp_data and nlp_data.get(self.field_name):
                nlp_val = nlp_data[self.field_name]
        except Exception as e:
            logger.warning(f"NLP fallback extraction failed for {self.field_name}: {e}")
            
        val = nlp_val if nlp_val is not None else answer_clean
        extracted_data[self.field_name] = val
        extracted_data[f"_explicit_{self.field_name}"] = True
        if self.field_name == "pelapor_nama":
            session.contact_name = val
        return True, extracted_data

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        from app.engine.chatbot_engine import FIELD_QUESTIONS
        question = FIELD_QUESTIONS.get(self.field_name, {})
        q_text = question.get("text", "")
        buttons = list(question.get("buttons", []))
        
        # If it is pelapor_hp and we have session.contact_phone, offer a one-tap button
        if self.field_name == "pelapor_hp" and session.contact_phone:
            q_text = (
                f"📱 *Berapa nomor telepon/WhatsApp Anda yang aktif?*\n\n"
                f"Kami mendeteksi nomor Anda: *{session.contact_phone}*.\n"
                f"Apakah kami bisa menggunakan nomor ini untuk menghubungi Anda?"
            )
            buttons = ["Gunakan Nomor Aktif Ini"]
            
        return q_text, buttons
