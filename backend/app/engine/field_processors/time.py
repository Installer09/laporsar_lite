import re
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class TimeFieldProcessor(BaseFieldProcessor):
    """Processes and validates the incident time ('waktu') field with smart relative-time resolution."""

    WORD_TO_NUM = {
        "satu": 1, "sejam": 1, "semenit": 1, "sehari": 1,
        "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
        "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
        "sepuluh": 10, "sebelas": 11, "dua belas": 12, "lima belas": 15,
        "dua puluh": 20, "tiga puluh": 30, "empat puluh lima": 45,
    }

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        answer_lower = answer_clean.lower()

        # 1. Check if user says they don't know the time
        unknown_keywords = [
            "tidak tahu", "belum tahu", "ndak tahu", "belum tau", "tidak tau",
            "kurang tahu", "belum jelas", "nihil", "n/a", "tidak tahu jamnya", "belum tahu jamnya"
        ]
        normalized_answer = re.sub(r'[.,;:!?]+$', '', answer_lower).strip()
        if normalized_answer in unknown_keywords or any(
            kw in normalized_answer for kw in ["tidak tahu", "belum tahu", "tidak tau", "belum tau", "ndak tahu"]
        ):
            extracted_data["waktu"] = "Waktu Kejadian Tidak Diketahui"
            extracted_data["_explicit_waktu"] = True
            return True, extracted_data

        # Guard against overly long non-time dumps
        if len(answer_clean) > 100 and not self._looks_like_time_answer(answer_lower):
            reply = (
                "*Keterangan Waktu Terlalu Panjang*\n\n"
                "Mohon sebutkan perkiraan waktu kejadian secara singkat (contoh: _baru saja_, _2 jam lalu_, atau _kemarin sore_)."
            )
            return False, {"text": reply, "buttons": ["Belum Tahu"]}

        # 2. If user previously selected a calendar date (_temp_date backward compatibility)
        if "_temp_date" in extracted_data and self._looks_like_time_answer(answer_lower):
            temp_date = extracted_data.pop("_temp_date", None)
            try:
                dt = datetime.strptime(temp_date, "%Y-%m-%d")
                from app.services.telegram_calendar import WEEKDAYS_FULL, MONTH_NAMES_ID
                day_name = WEEKDAYS_FULL[dt.weekday()]
                month_name = MONTH_NAMES_ID[dt.month]
                formatted_date = f"{day_name}, {dt.day} {month_name} {dt.year}"
            except Exception:
                formatted_date = temp_date
            extracted_data["waktu"] = f"{formatted_date} pukul {answer_clean}"
            extracted_data["_explicit_waktu"] = True
            return True, extracted_data

        # 3. Smart Relative & Natural Time Resolution
        resolved_time = self.resolve_natural_time(answer_clean)
        if resolved_time:
            extracted_data["waktu"] = resolved_time
            extracted_data["_explicit_waktu"] = True
            extracted_data.pop("_temp_date", None)
            return True, extracted_data

        # 4. If input does not contain any recognizable time/date expression
        reply = (
            "*Perkiraan Waktu Belum Jelas*\n\n"
            "Mohon sebutkan kapan kejadiannya berlangsung (contoh: _baru saja_, _2 jam lalu_, _tadi pagi jam 8_, atau _kemarin sore_)."
        )
        return False, {"text": reply, "buttons": ["Belum Tahu"]}

    @classmethod
    def _format_wib_date(cls, dt: datetime) -> str:
        from app.services.telegram_calendar import WEEKDAYS_FULL, MONTH_NAMES_ID
        day_name = WEEKDAYS_FULL[dt.weekday()]
        month_name = MONTH_NAMES_ID[dt.month]
        return f"{day_name}, {dt.day} {month_name} {dt.year}"

    @classmethod
    def resolve_natural_time(cls, text: str, now_wib: datetime = None) -> str | None:
        """
        Resolves natural Indonesian time expressions into a clear, human-readable
        and standardized date-time string anchored to current WIB time.
        """
        from app.services.telegram_calendar import get_wib_now
        if now_wib is None:
            now_wib = get_wib_now()

        clean = text.strip()
        low = clean.lower()

        # A. Immediate / "Just now" expressions
        if any(term in low for term in ["baru saja", "barusan", "sekarang", "saat ini", "detik ini"]):
            date_part = cls._format_wib_date(now_wib)
            return f"{date_part} pukul {now_wib.strftime('%H:%M')} WIB (Baru saja)"

        # B. Relative duration: "setengah jam yang lalu" / "setengah jam lalu"
        if re.search(r'\bsetengah\s+jam\s+(?:yang\s+)?lalu\b', low):
            target_dt = now_wib - timedelta(minutes=30)
            date_part = cls._format_wib_date(target_dt)
            return f"{date_part} pukul {target_dt.strftime('%H:%M')} WIB ({clean})"

        # C. Relative duration: "<N> menit/jam/hari (yang) lalu" or "sejam lalu"
        if "sejam lalu" in low or "sejam yang lalu" in low:
            target_dt = now_wib - timedelta(hours=1)
            date_part = cls._format_wib_date(target_dt)
            return f"{date_part} pukul {target_dt.strftime('%H:%M')} WIB ({clean})"

        rel_match = re.search(
            r'\b(\d+|satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|sebelas|dua belas|lima belas|dua puluh|tiga puluh|empat puluh lima)\s*(menit|jam|hari)\s*(?:yang\s+)?lalu\b',
            low
        )
        if rel_match:
            raw_num, unit = rel_match.group(1), rel_match.group(2)
            num_val = int(raw_num) if raw_num.isdigit() else cls.WORD_TO_NUM.get(raw_num, 1)
            if unit == "menit":
                target_dt = now_wib - timedelta(minutes=num_val)
                date_part = cls._format_wib_date(target_dt)
                return f"{date_part} pukul {target_dt.strftime('%H:%M')} WIB ({clean})"
            elif unit == "jam":
                target_dt = now_wib - timedelta(hours=num_val)
                date_part = cls._format_wib_date(target_dt)
                return f"{date_part} pukul {target_dt.strftime('%H:%M')} WIB ({clean})"
            elif unit == "hari":
                target_dt = now_wib - timedelta(days=num_val)
                date_part = cls._format_wib_date(target_dt)
                return f"{date_part} ({clean})"

        # D. Determine base date if relative day words are present
        target_dt = now_wib
        has_explicit_date = cls._has_date_indicator(low)
        has_explicit_time = cls._has_time_indicator(low)

        if "kemarin lusa" in low or "2 hari lalu" in low:
            target_dt = now_wib - timedelta(days=2)
        elif any(w in low for w in ["kemarin", "kemaren", "semalam", "tadi malam"]):
            target_dt = now_wib - timedelta(days=1) if ("kemarin" in low or "kemaren" in low or ("semalam" in low and now_wib.hour < 18)) else now_wib

        # E. Check if specific hour is mentioned (e.g., "jam 8 pagi", "pukul 14:30", "17.00", or bare hour "jam 5")
        hour_val = None
        minute_val = 0
        hhmm_match = re.search(r'\b(\d{1,2})[.:](\d{2})\b', low)
        if hhmm_match:
            h_cand, m_cand = int(hhmm_match.group(1)), int(hhmm_match.group(2))
            if 0 <= h_cand <= 24 and 0 <= m_cand < 60:
                hour_val = h_cand % 24
                minute_val = m_cand
        else:
            jam_match = re.search(r'\b(?:jam|pukul|pkl|sekitar\s+jam)\s*(\d{1,2})\b', low)
            if jam_match:
                h_cand = int(jam_match.group(1))
                if 0 <= h_cand <= 24:
                    hour_val = h_cand
            elif re.match(r'^\s*(\d{1,2})\s*(pagi|siang|sore|malam|subuh|wib|wita|wit)?\s*$', low):
                m_bare = re.match(r'^\s*(\d{1,2})', low)
                h_cand = int(m_bare.group(1))
                if 0 <= h_cand <= 24:
                    hour_val = h_cand

        if hour_val is not None:
            # Adjust 12-hour clock based on time-of-day words
            if any(w in low for w in ["sore", "petang"]) and 1 <= hour_val <= 11:
                hour_val += 12
            elif "malam" in low and 1 <= hour_val <= 11:
                hour_val = (hour_val + 12) % 24
            elif "siang" in low and 1 <= hour_val <= 5:
                hour_val += 12

            # If user didn't specify a date word and the specified hour is still in the future today, assume yesterday
            if not has_explicit_date and hour_val > now_wib.hour:
                target_dt = now_wib - timedelta(days=1)

            # If user already gave an explicit full date string (like "16 Oktober 2026..."), preserve clean text
            if re.search(r'\b\d{1,2}\s+(?:januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\b', low) or re.search(r'\b\d{1,2}[/\-]\d{1,2}', low):
                return clean

            date_part = cls._format_wib_date(target_dt)
            return f"{date_part} pukul {hour_val:02d}:{minute_val:02d} WIB ({clean})"

        # F. Has date indicator and/or time-of-day indicator (e.g. "Kemarin Sore", "Tadi pagi", "Subuh tadi", "Hari ini", "Kemarin")
        if has_explicit_date or has_explicit_time or cls._looks_like_time_answer(low):
            if re.search(r'\b\d{1,2}\s+(?:januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\b', low) or re.search(r'\b\d{1,2}[/\-]\d{1,2}', low):
                return clean
            date_part = cls._format_wib_date(target_dt)
            return f"{date_part} ({clean})"

        return None

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        return self._get_question_text(), ["Belum Tahu"]

    def _get_question_text(self) -> str:
        return (
            "*Kapan kejadiannya berlangsung?*\n"
            "Sebutkan perkiraan waktu kejadian (contoh: _baru saja_, _2 jam lalu_, _tadi pagi jam 8_, atau _kemarin sore_)."
        )

    @classmethod
    def _has_date_indicator(cls, text: str) -> bool:
        relative_days = [
            "hari ini", "kemarin", "kemaren", "lusa", "semalam", "tadi malam",
            "tadi pagi", "tadi sore", "tadi siang", "dini hari tadi",
            "subuh tadi", "siang tadi", "pagi tadi", "sore tadi", "baru saja", "barusan"
        ]
        if any(rd in text for rd in relative_days):
            return True

        days_of_week = ["senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu"]
        if any(d in text for d in days_of_week):
            return True

        months = [
            "januari", "februari", "maret", "april", "mei", "juni",
            "juli", "agustus", "september", "oktober", "november", "desember",
            "jan", "feb", "mar", "apr", "mei", "jun", "jul", "agu", "sep", "okt", "nov", "des"
        ]
        for m in months:
            if re.search(rf"\b{m}\b", text):
                return True

        numeric_patterns = [
            r"\b\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?\b",
            r"\b\d{4}[/\-]\d{1,2}[/\-]\d{1,2}\b"
        ]
        for p in numeric_patterns:
            if re.search(p, text):
                return True

        return False

    @classmethod
    def _has_time_indicator(cls, text: str) -> bool:
        time_keywords = ["pukul", "jam", "pkl", "wib", "wita", "wit"]
        if any(tk in text for tk in time_keywords):
            return True

        time_of_day = ["subuh", "pagi", "siang", "sore", "petang", "malam", "dini hari", "tengah malam", "maghrib", "magrib", "isya", "ashar", "dzuhur"]
        if any(tod in text for tod in time_of_day):
            return True

        if re.search(r"\b\d{1,2}[.:]\d{2}\b", text):
            return True

        if "lalu" in text or "menit" in text or "sejak" in text or "dari" in text:
            return True

        return False

    @classmethod
    def _looks_like_time_answer(cls, message: str) -> bool:
        msg = message.strip().lower()

        digit_match = re.search(r"\b\d{1,2}\b", msg)
        if digit_match:
            val = int(digit_match.group(0))
            if 0 <= val <= 24:
                return True

        indonesian_hours = [
            "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan",
            "sepuluh", "sebelas", "dua belas", "tengah malam", "tengah hari"
        ]
        if any(re.search(rf"\b{w}\b", msg) for w in indonesian_hours):
            return True

        time_keywords = [
            "jam", "pukul", "wib", "wita", "wit", "pdtw", "lt",
            "pagi", "siang", "sore", "malam", "dini hari", "subuh",
            "tadi", "kemarin", "kemaren", "semalam", "hari ini", "baru saja",
            "barusan", "sebelum", "sesudah", "sekitar", "lalu", "menit", "sejak"
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

