import re
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class TimeFieldProcessor(BaseFieldProcessor):
    """Processes and validates the incident time ('waktu') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        answer_lower = answer_clean.lower()
        
        # 1. Check if user says they don't know the time
        unknown_keywords = ["tidak tahu", "belum tahu", "ndak tahu", "belum tau", "tidak tau", "kurang tahu", "belum jelas", "nihil", "n/a", "tidak tahu jamnya", "belum tahu jamnya"]
        normalized_answer = re.sub(r'[.,;:!?]+$', '', answer_lower).strip()
        if normalized_answer in unknown_keywords or any(kw in normalized_answer for kw in ["tidak tahu", "belum tahu", "tidak tau", "belum tau", "ndak tahu"]):
            extracted_data["waktu"] = "Waktu Kejadian Tidak Diketahui"
            extracted_data["_explicit_waktu"] = True
            return True, extracted_data
            
        # 2. Check for direct relative terms that imply both date and time (accepted immediately)
        direct_relative_terms = ["baru saja", "barusan", "1 jam yang lalu", "sekarang"]
        if any(term in answer_lower for term in direct_relative_terms):
            extracted_data["waktu"] = answer_clean
            extracted_data["_explicit_waktu"] = True
            return True, extracted_data

        # Guard against raw message dumps for waktu
        if len(answer_clean) > 80:
            reply = "Penjelasan waktu terlalu panjang. " + self._get_question_text()
            buttons = ["Baru Saja", "1 Jam yang Lalu", "Belum Tahu"]
            return False, {"text": reply, "buttons": buttons}

        # 3. Perform soft validation for date and time elements
        has_temp_date = "_temp_date" in extracted_data
        has_date = self._has_date_indicator(answer_lower) or has_temp_date
        has_time = self._has_time_indicator(answer_lower)

        if has_date and has_time:
            if has_temp_date and not self._has_date_indicator(answer_lower):
                temp_date = extracted_data["_temp_date"]
                try:
                    dt = datetime.strptime(temp_date, "%Y-%m-%d")
                    from app.services.telegram_calendar import WEEKDAYS_FULL, MONTH_NAMES_ID
                    day_name = WEEKDAYS_FULL[dt.weekday()]
                    month_name = MONTH_NAMES_ID[dt.month]
                    formatted_date = f"{day_name}, {dt.day} {month_name} {dt.year}"
                except Exception:
                    formatted_date = temp_date
                extracted_data["waktu"] = f"{formatted_date} pukul {answer_clean}"
            else:
                extracted_data["waktu"] = answer_clean
            extracted_data["_explicit_waktu"] = True
            extracted_data.pop("_temp_date", None)
            return True, extracted_data

        if has_date and not has_time:
            reply = (
                "*Jam kejadian belum lengkap.*\n\n"
                "Mohon sebutkan jam perkiraan kejadiannya (Contoh: _Jam 4 sore_ atau _Jam 10 pagi_)."
            )
            buttons = ["Baru Saja", "Belum Tahu"]
            return False, {"text": reply, "buttons": buttons}

        if not has_date and has_time:
            reply = (
                "*Hari/tanggal kejadian belum lengkap.*\n\n"
                "Mohon sebutkan harinya (Contoh: _Hari ini_, _Kemarin_, atau _Senin_)."
            )
            buttons = ["Baru Saja", "Belum Tahu"]
            return False, {"text": reply, "buttons": buttons}

        # If neither is found
        reply = (
            "*Format waktu tidak valid.*\n\n"
            "Mohon sebutkan kapan kejadiannya (hari dan jam).\n"
            "Contoh: _Baru saja_, _Hari ini jam 10 pagi_, atau _Kemarin sore jam 5_."
        )
        buttons = ["Baru Saja", "1 Jam yang Lalu", "Belum Tahu"]
        return False, {"text": reply, "buttons": buttons}

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        return self._get_question_text(), ["Baru Saja", "1 Jam yang Lalu", "Belum Tahu"]

    def _get_question_text(self) -> str:
        return (
            "*Kapan kejadiannya?*\n\n"
            "Sebutkan jamnya atau kapan musibah itu terjadi.\n"
            "Contoh:\n"
            "• _Baru saja_\n"
            "• _10 menit yang lalu_\n"
            "• _Hari ini jam 10 pagi_\n"
            "• _Kemarin sore jam 5_"
        )

    def _has_date_indicator(self, text: str) -> bool:
        # Relative day terms
        relative_days = [
            "hari ini", "kemarin", "lusa", "semalam", "tadi malam", 
            "tadi pagi", "tadi sore", "tadi siang", "dini hari tadi", 
            "subuh tadi", "siang tadi", "pagi tadi", "baru saja", "barusan"
        ]
        if any(rd in text for rd in relative_days):
            return True
            
        # Days of week
        days_of_week = ["senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu"]
        if any(d in text for d in days_of_week):
            return True
            
        # Months of year (long and short)
        months = [
            "januari", "februari", "maret", "april", "mei", "juni", 
            "juli", "agustus", "september", "oktober", "november", "desember",
            "jan", "feb", "mar", "apr", "mei", "jun", "jul", "agu", "sep", "okt", "nov", "des"
        ]
        for m in months:
            if re.search(rf"\b{m}\b", text):
                return True
                
        # Numeric date patterns like DD/MM, DD-MM, DD/MM/YYYY, YYYY-MM-DD
        numeric_patterns = [
            r"\b\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?\b",
            r"\b\d{4}[/\-]\d{1,2}[/\-]\d{1,2}\b"
        ]
        for p in numeric_patterns:
            if re.search(p, text):
                return True
                
        return False

    def _has_time_indicator(self, text: str) -> bool:
        # Direct time keywords
        time_keywords = ["pukul", "jam", "wib", "wita", "wit"]
        if any(tk in text for tk in time_keywords):
            return True
            
        # Time-of-day nouns
        time_of_day = ["subuh", "pagi", "siang", "sore", "malam", "dini hari", "tengah malam"]
        if any(tod in text for tod in time_of_day):
            return True
            
        # Numeric time patterns like HH.MM or HH:MM
        if re.search(r"\b\d{1,2}[.:]\d{2}\b", text):
            return True
            
        # Check if it says 'lalu' or 'menit' (e.g. "10 menit lalu" or "2 jam lalu")
        if "lalu" in text or "menit" in text:
            return True
            
        return False

    def _looks_like_time_answer(self, message: str) -> bool:
        msg = message.strip().lower()
        
        # Check if it represents an hour/digit directly (e.g. "8", "12", "08")
        digit_match = re.search(r"\b\d{1,2}\b", msg)
        if digit_match:
            val = int(digit_match.group(0))
            if 0 <= val <= 24:
                return True
                
        # Check number words in Indonesian
        indonesian_hours = [
            "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan",
            "sepuluh", "sebelas", "dua belas", "tengah malam", "tengah hari"
        ]
        if any(f"\\b{w}\\b" in msg for w in indonesian_hours) or any(w == msg for w in indonesian_hours):
            return True

        time_keywords = [
            "jam", "pukul", "wib", "wita", "wit", "pdtw", "lt",
            "pagi", "siang", "sore", "malam", "dini hari", "subuh",
            "tadi", "kemarin", "semalam", "hari ini", "baru saja",
            "barusan", "sebelum", "sesudah", "sekitar", "lalu", "menit"
        ]
        for kw in time_keywords:
            if kw in msg:
                return True
        if re.search(r"\bg\b", msg):
            return True
        if re.search(r"\b\d{4}\b", msg):
            return True
        if re.search(r"\d{1,2}[.:]\d{2}", msg) or re.search(r"\d{1,2}[/\-]\d{1,2}", msg):
            return True
        return False


WaktuFieldProcessor = TimeFieldProcessor
