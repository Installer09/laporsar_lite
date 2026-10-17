import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class VictimConditionFieldProcessor(BaseFieldProcessor):
    """Processes and validates the victim status conditions ('korban_kondisi') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        
        s_syns = [
            "selamat", "aman", "dievakuasi", "sehat", "hidup", "baik-baik saja", "tidak luka",
            "berhasil berenang", "sampai ke tepi", "sampai di tepi", "sudah di darat", "sudah ketemu",
            "sudah ditemukan selamat", "berhasil menyelamatkan diri", "kondisi baik"
        ]
        md_syns = ["meninggal", "tewas", "mati", "md", "jasad", "jenazah", "wafat", "tak bernyawa", "tidak bernyawa"]
        dp_syns = [
            "hilang", "belum ditemukan", "pencarian", "dicari", "tenggelam", "hanyut", "dp", "terbawa arus",
            "belum ketemu", "belum pulang", "belum kembali", "masih di laut", "terombang-ambing", "terombang ambing",
            "terjebak", "tersesat", "butuh evakuasi", "butuh pertolongan", "minta tolong", "belum dievakuasi",
            "belum kelihatan", "tidak kelihatan", "belum ada kabar", "tidak ada kabar", "hilang kontak", "lost contact"
        ]
        
        from app.services.rule_extractor import RuleExtractor
        if RuleExtractor._dictionary_cache:
            if RuleExtractor._dictionary_cache.get("VICTIM_STATUS_S"):
                s_syns = list(set(s_syns + [item["word"].lower() for item in RuleExtractor._dictionary_cache["VICTIM_STATUS_S"]]))
            if RuleExtractor._dictionary_cache.get("VICTIM_STATUS_MD"):
                md_syns = list(set(md_syns + [item["word"].lower() for item in RuleExtractor._dictionary_cache["VICTIM_STATUS_MD"]]))
            if RuleExtractor._dictionary_cache.get("VICTIM_STATUS_DP"):
                dp_syns = list(set(dp_syns + [item["word"].lower() for item in RuleExtractor._dictionary_cache["VICTIM_STATUS_DP"]]))
                
        val_str = answer_clean.lower()
        # Normalize Indonesian number words ("satu", "dua", "tiga", etc.) into digits for breakdown parsing
        word_to_digit = {
            "satu": "1", "seorang": "1", "dua": "2", "tiga": "3", "empat": "4", "lima": "5",
            "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9", "sepuluh": "10"
        }
        normalized_for_match = answer_clean
        for w, d in word_to_digit.items():
            normalized_for_match = re.sub(rf"\b{w}\b", d, normalized_for_match, flags=re.IGNORECASE)

        # Hindari false positive 'mati' pada 'mati mesin' / 'pompong mati' / 'kapal mati'
        val_str_no_engine = re.sub(r'\b(?:mati\s+mesin|mesin\s+mati|pompong(?:nya)?\s+mati|kapal(?:nya)?\s+mati|perahu(?:nya)?\s+mati)\b', 'mogok', val_str)
        has_s = any(s in val_str_no_engine for s in s_syns) or bool(re.search(r'\b(selamat|slmt|hidup|sehat|aman)\b', val_str_no_engine))
        has_md = any(m in val_str_no_engine for m in md_syns) or bool(re.search(r'\b(md|meninggal|tewas|mati)\b', val_str_no_engine))
        has_dp = any(d in val_str_no_engine for d in dp_syns) or bool(re.search(r'\b(dp|hilang|tenggelam|hanyut)\b', val_str_no_engine)) or "mogok" in val_str_no_engine
        
        if re.search(r'-\s*\d+', answer_clean):
            reply = (
                "*Format Angka Tidak Valid*\n\n"
                "Jumlah korban tidak boleh bernilai negatif. Mohon masukkan angka yang valid atau pilih *Belum Tahu*."
            )
            return False, {"text": reply, "buttons": ["Belum Tahu"]}

        if not (has_s or has_md or has_dp):
            # Try AI contextual extraction before rejecting natural language condition descriptions
            try:
                import json
                from app.services.incident_data_service import extract_incident_data
                try:
                    history_list = json.loads(session.conversation_history)
                except Exception:
                    history_list = []
                nlp_data = await extract_incident_data(message, db, session.user_id, history_list, use_llm=True)
                if nlp_data and (nlp_data.get("kondisi_korban") or nlp_data.get("korban_kondisi")):
                    extracted_cond = nlp_data.get("kondisi_korban") or nlp_data.get("korban_kondisi")
                    if str(extracted_cond).strip() not in ("", "Nihil", "Belum ada data", "-"):
                        extracted_data["korban_kondisi"] = str(extracted_cond).strip()
                        return True, extracted_data
            except Exception as ex:
                logger.warning(f"AI fallback in VictimConditionFieldProcessor failed: {ex}")

            reply = (
                "*Format Kondisi Korban Tidak Dikenali*\n\n"
                "Mohon sebutkan kondisi korban yang Anda ketahui (contoh: _masih dalam pencarian_, _selamat_, atau _2 selamat, 1 hilang_) atau pilih *Belum Tahu*."
            )
            return False, {"text": reply, "buttons": ["Belum Tahu"]}
            
        s_pattern = "|".join(re.escape(s) for s in s_syns)
        md_pattern = "|".join(re.escape(m) for m in md_syns)
        dp_pattern = "|".join(re.escape(d) for d in dp_syns)
        
        # Two-way matching: status then digit, OR digit then status (with optional "orang" / words in between)
        # 1. Status then digit (e.g. "Selamat: 2", "MD 1", "Meninggal dunia 3 orang")
        s_match_after = re.search(rf'(?i)(?:s|{s_pattern})\s*(?:[:=]|[^\d\W]+\s+){{0,4}}\s*(\d+)', normalized_for_match)
        md_match_after = re.search(rf'(?i)(?:md|{md_pattern})\s*(?:[:=]|[^\d\W]+\s+){{0,4}}\s*(\d+)', normalized_for_match)
        dp_match_after = re.search(rf'(?i)(?:dp|{dp_pattern})\s*(?:[:=]|[^\d\W]+\s+){{0,4}}\s*(\d+)', normalized_for_match)
        
        # 2. Digit then status (e.g. "2 orang selamat", "1 hilang", "1 berhasil berenang ke tepi")
        s_match_before = re.search(rf'(?i)(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:[^\d\W]+\s+){{0,4}}(?:{s_pattern})', normalized_for_match)
        md_match_before = re.search(rf'(?i)(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:[^\d\W]+\s+){{0,4}}(?:{md_pattern})', normalized_for_match)
        dp_match_before = re.search(rf'(?i)(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:[^\d\W]+\s+){{0,4}}(?:{dp_pattern})', normalized_for_match)
        
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
            if not digit_match and extracted_data.get("korban"):
                digit_match = re.search(r'\d+', str(extracted_data.get("korban")))
            num = digit_match.group(0) if digit_match else "1"
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
            "*Bagaimana kondisi korban saat ini?*\n"
            "Sebutkan apakah korban masih dalam pencarian (hilang), butuh evakuasi, selamat, atau meninggal dunia (contoh: _masih dalam pencarian_ atau _2 selamat, 1 hilang_)."
        )
        return q_text, ["Belum Tahu"]


KorbanKondisiFieldProcessor = VictimConditionFieldProcessor
