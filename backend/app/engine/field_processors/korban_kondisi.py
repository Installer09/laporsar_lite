import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class KorbanKondisiFieldProcessor(BaseFieldProcessor):
    """Processes and validates the victim status conditions ('korban_kondisi') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        
        s_syns = ["selamat", "aman", "dievakuasi", "sehat", "hidup"]
        md_syns = ["meninggal", "tewas", "mati", "md", "jasad", "jenazah"]
        dp_syns = ["hilang", "belum ditemukan", "pencarian", "dicari", "tenggelam", "hanyut", "dp", "terbawa arus"]
        
        from app.services.rule_extractor import RuleExtractor
        if RuleExtractor._dictionary_cache:
            if RuleExtractor._dictionary_cache.get("VICTIM_STATUS_S"):
                s_syns = list(set(s_syns + [item["word"].lower() for item in RuleExtractor._dictionary_cache["VICTIM_STATUS_S"]]))
            if RuleExtractor._dictionary_cache.get("VICTIM_STATUS_MD"):
                md_syns = list(set(md_syns + [item["word"].lower() for item in RuleExtractor._dictionary_cache["VICTIM_STATUS_MD"]]))
            if RuleExtractor._dictionary_cache.get("VICTIM_STATUS_DP"):
                dp_syns = list(set(dp_syns + [item["word"].lower() for item in RuleExtractor._dictionary_cache["VICTIM_STATUS_DP"]]))
                
        val_str = answer_clean.lower()
        has_s = any(s in val_str for s in s_syns) or re.search(r'\b[s]\b', val_str)
        has_md = any(m in val_str for m in md_syns) or re.search(r'\b[m][d]\b', val_str)
        has_dp = any(d in val_str for d in dp_syns) or re.search(r'\b[d][p]\b', val_str)
        
        if re.search(r'-\s*\d+', answer_clean):
            reply = (
                "⚠️ *Format Angka Tidak Valid*\n\n"
                "Jumlah korban tidak boleh bernilai negatif. Mohon masukkan angka yang valid atau ketuk **Belum Tahu**."
            )
            return False, {"text": reply, "buttons": ["Belum Tahu"]}

        if not (has_s or has_md or has_dp):
            reply = (
                "⚠️ *Format Kondisi Korban Tidak Dikenali*\n\n"
                "Mohon sebutkan kondisi korban yang Anda ketahui.\n"
                "Contoh: _2 selamat, 1 hilang_ atau ketuk tombol **Belum Tahu**."
            )
            return False, {"text": reply, "buttons": ["Belum Tahu"]}
            
        s_pattern = "|".join(re.escape(s) for s in s_syns)
        md_pattern = "|".join(re.escape(m) for m in md_syns)
        dp_pattern = "|".join(re.escape(d) for d in dp_syns)
        
        # Two-way matching: status then digit, OR digit then status (with optional "orang" / words in between)
        # 1. Status then digit (e.g. "Selamat: 2", "MD 1", "Meninggal dunia 3 orang")
        s_match_after = re.search(rf'(?i)(?:s|{s_pattern})\s*(?:[:=]|[^\d\W]+\s+){{0,3}}\s*(\d+)', answer_clean)
        md_match_after = re.search(rf'(?i)(?:md|{md_pattern})\s*(?:[:=]|[^\d\W]+\s+){{0,3}}\s*(\d+)', answer_clean)
        dp_match_after = re.search(rf'(?i)(?:dp|{dp_pattern})\s*(?:[:=]|[^\d\W]+\s+){{0,3}}\s*(\d+)', answer_clean)
        
        # 2. Digit then status (e.g. "2 orang selamat", "1 hilang", "1 orang masih hilang")
        s_match_before = re.search(rf'(?i)(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:[^\d\W]+\s+){{0,3}}(?:{s_pattern})', answer_clean)
        md_match_before = re.search(rf'(?i)(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:[^\d\W]+\s+){{0,3}}(?:{md_pattern})', answer_clean)
        dp_match_before = re.search(rf'(?i)(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:[^\d\W]+\s+){{0,3}}(?:{dp_pattern})', answer_clean)
        
        s_val = "0"
        if s_match_before:
            s_val = s_match_before.group(1)
        elif s_match_after:
            s_val = s_match_after.group(1)
            
        md_val = "0"
        if md_match_before:
            md_val = md_match_before.group(1)
        elif md_match_after:
            md_val = md_match_after.group(1)
            
        dp_val = "0"
        if dp_match_before:
            dp_val = dp_match_before.group(1)
        elif dp_match_after:
            dp_val = dp_match_after.group(1)
        
        if s_val == "0" and md_val == "0" and dp_val == "0":
            digit_match = re.search(r'\d+', answer_clean)
            if digit_match:
                num = digit_match.group(0)
                if has_s and not has_md and not has_dp:
                    s_val = num
                elif has_md and not has_s and not has_dp:
                    md_val = num
                elif has_dp and not has_s and not has_md:
                    dp_val = num
                    
        extracted_data["korban_s"] = s_val
        extracted_data["korban_md"] = md_val
        extracted_data["korban_dp"] = dp_val
        extracted_data["korban_kondisi"] = answer_clean
        return True, extracted_data

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        q_text = (
            "📊 *Bagaimana rincian kondisi korban saat ini?*\n"
            "Berapa korban yang selamat, meninggal, atau masih dalam pencarian (hilang)?\n"
            "Contoh: _2 selamat, 1 hilang_ atau _selamat semua_"
        )
        return q_text, ["Belum Tahu"]
