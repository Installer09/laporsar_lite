import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import (
    tenant_context,
    TenantPartitionedCache,
    TenantPartitionedSet,
    MultitenantServiceMeta,
)

from app.models.settings_models import Classification, Location

logger = logging.getLogger(__name__)


class RuleExtractor(metaclass=MultitenantServiceMeta):
    """
    Extracts report data based on predefined rules, regex, and database keywords.
    Reduces reliance on LLM by attempting to parse structured fields locally first.

    Extraction Pipeline:
      1. jenis_kejadian  → Classification DB keywords
      2. lokasi_teks     → Location DB names + regex patterns
      3. waktu           → Time keyword / regex
      4. korban           → Victim count regex
      5. koordinat        → DMS / decimal coordinate regex
      6. data_kapal       → Vessel type + name regex
      7. jumlah_korban    → Detailed MD/DP/Selamat breakdown
      8. dictionary hints → Enrich context with approved KB terms
    """

    # Cache for database dictionary words to support synchronous extraction, partitioned by tenant_slug
    _dictionary_cache = TenantPartitionedCache()
    _incident_verbs_cache = TenantPartitionedSet()

    # Pre-compiled dynamic regex patterns, partitioned by tenant_slug
    _vessel_pattern_compiled: Dict[str, Any] = {}
    _vessel_generic_compiled: Dict[str, Any] = {}
    _victim_status_patterns_compiled: Dict[str, Dict[str, Any]] = {}

    @classmethod
    async def load_cache(cls, db: AsyncSession):
        """Pre-warm dictionary cache by merging global approved words (Master DB) and regional approved words (Tenant DB)."""
        info = getattr(db, "info", None)
        tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else (tenant_context.get() or "global")
        
        # 1. Fetch approved words from Master DB
        master_words = []
        try:
            from app.models.knowledge_models import DictionaryWord, DictionaryStatus
            if tenant_slug == "global":
                result = await db.execute(
                    select(DictionaryWord).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED
                    )
                )
                master_words = result.scalars().all()
            else:
                from app.db.session import MasterSessionLocal
                async with MasterSessionLocal() as master_db:
                    result = await master_db.execute(
                        select(DictionaryWord).where(
                            DictionaryWord.status == DictionaryStatus.APPROVED
                        )
                    )
                    master_words = result.scalars().all()
        except Exception as e:
            logger.warning(f"[RuleExtractor] Failed to load global dictionary words: {e}")

        # 2. Fetch approved words from Tenant DB (if not global)
        tenant_words = []
        if tenant_slug != "global":
            try:
                from app.models.knowledge_models import DictionaryWord, DictionaryStatus
                result = await db.execute(
                    select(DictionaryWord).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED
                    )
                )
                tenant_words = result.scalars().all()
            except Exception as e:
                logger.warning(f"[RuleExtractor] Failed to load tenant dictionary words: {e}")

        # 3. Merge them. Tenant words override master words on duplicate keyword check.
        merged_dict = {}
        # Load master first
        for w in master_words:
            ner_type = getattr(w, "ner_type", None)
            word = getattr(w, "word", None)
            if not ner_type or not word:
                continue
            key = (ner_type, word.lower())
            merged_dict[key] = {
                "word": word,
                "ner_target": getattr(w, "ner_target", None)
            }
        # Load tenant words (overrides master if duplicate)
        for w in tenant_words:
            ner_type = getattr(w, "ner_type", None)
            word = getattr(w, "word", None)
            if not ner_type or not word:
                continue
            key = (ner_type, word.lower())
            merged_dict[key] = {
                "word": word,
                "ner_target": getattr(w, "ner_target", None)
            }

        # Structure cache: { ner_type: [ {word, ner_target} ] }
        cache = {}
        for (ner_type, _), val in merged_dict.items():
            if ner_type not in cache:
                cache[ner_type] = []
            cache[ner_type].append(val)

        # Sort each category by word length descending
        for ner_type in cache:
            cache[ner_type].sort(key=lambda item: len(item["word"] or ""), reverse=True)

        cls._dictionary_cache[tenant_slug] = cache
        
        # Load dynamic incident verbs for vessel name exclusion
        incident_verbs = {"terbakar", "tenggelam", "hanyut", "kelem", "mati", "mesin", "hilang", "meninggal", "selamat", "ditemukan", "pencarian", "evakuasi", "terbalik", "tubrukan", "tabrakan", "kandas", "pecah", "bocor", "rusak", "ledakan"}
        
        # Load from Master classifications
        try:
            from app.models.settings_models import Classification
            if tenant_slug == "global":
                class_res = await db.execute(select(Classification))
                classifications = class_res.scalars().all()
            else:
                from app.db.session import MasterSessionLocal
                async with MasterSessionLocal() as master_db:
                    class_res = await master_db.execute(select(Classification))
                    classifications = class_res.scalars().all()
            for c in classifications:
                if c.keywords:
                    for kw in c.keywords.split(","):
                        kw_clean = kw.strip().lower()
                        if kw_clean:
                            for part in kw_clean.split():
                                incident_verbs.add(part)
        except Exception as e:
            logger.warning(f"[RuleExtractor] Failed to load global classifications: {e}")

        # Load from Tenant classifications (if not global)
        if tenant_slug != "global":
            try:
                from app.models.settings_models import Classification
                class_res = await db.execute(select(Classification))
                classifications = class_res.scalars().all()
                for c in classifications:
                    if c.keywords:
                        for kw in c.keywords.split(","):
                            kw_clean = kw.strip().lower()
                            if kw_clean:
                                for part in kw_clean.split():
                                    incident_verbs.add(part)
            except Exception as e:
                logger.warning(f"[RuleExtractor] Failed to load tenant classifications: {e}")

        for item in cache.get("INCIDENT_KEYWORD", []):
            word = item.get("word", "").lower()
            if word:
                for part in word.split():
                    incident_verbs.add(part)

        cls._incident_verbs_cache[tenant_slug] = incident_verbs
        cls._cache_loaded[tenant_slug] = True
        
        # Precompile regexes for this tenant
        cls._precompile_regexes(tenant_slug)
        
        logger.info(f"[RuleExtractor] Cache loaded for tenant '{tenant_slug}' with {len(merged_dict)} merged words.")

    @classmethod
    def _precompile_regexes(cls, tenant_slug: str):
        """Pre-compile dictionary-dependent regex patterns to save CPU cycles."""
        cache = cls._dictionary_cache.get(tenant_slug, {})
        
        # 1. Vessel Prefixes & Types
        prefixes = ["KM", "KMN", "KRI", "TB", "RIB", "RHIB", "MV", "MT", "LCT", "TK", "BG"]
        if cache.get("VESSEL_PREFIX"):
            db_prefixes = [item["word"].upper() for item in cache["VESSEL_PREFIX"] if item.get("word") and item["word"].strip()]
            prefixes = list(set(prefixes + db_prefixes))
        prefixes.sort(key=len, reverse=True)
        vessel_prefixes_pattern = "|".join(re.escape(p) for p in prefixes)
        cls._vessel_pattern_compiled[tenant_slug] = re.compile(
            rf"({vessel_prefixes_pattern})[\.\s]+([A-Za-z][A-Za-z0-9\s]{{1,40}})",
            re.IGNORECASE,
        )

        vessel_types = ["kapal", "pompong", "perahu", "speedboat", "tongkang", "tugboat", "tanker"]
        if cache.get("VESSEL_TYPE"):
            db_vessel_types = [item["word"].lower() for item in cache["VESSEL_TYPE"] if item.get("word") and item["word"].strip()]
            vessel_types = list(set(vessel_types + db_vessel_types))
        vessel_types.sort(key=len, reverse=True)
        vessel_types_pattern = "|".join(re.escape(t) for t in vessel_types)
        cls._vessel_generic_compiled[tenant_slug] = re.compile(
            rf"(?:{vessel_types_pattern})"
            r"(?:\s+(?:motor|nelayan|penumpang|cargo|yacht))?"
            r"(?:\s+([A-Z][a-zA-Z0-9\s]{1,30}))?",
            re.IGNORECASE,
        )

        # 2. Victim Status Breakdown Patterns
        s_syns = ["selamat", "dievakuasi", "terselamatkan", "sehat", "hidup", "aman"]
        md_syns = ["meninggal", "tewas", "md", "mati", "jasad", "jenazah", "meninggal dunia"]
        dp_syns = ["hilang", "dp", "belum ditemukan", "dalam pencarian", "masih dalam pencarian", "tenggelam", "hanyut", "dicari", "terbawa arus"]
        
        if cache.get("VICTIM_STATUS_S"):
            s_syns = list(set(s_syns + [item["word"].lower() for item in cache["VICTIM_STATUS_S"] if item.get("word") and item["word"].strip()]))
        if cache.get("VICTIM_STATUS_MD"):
            md_syns = list(set(md_syns + [item["word"].lower() for item in cache["VICTIM_STATUS_MD"] if item.get("word") and item["word"].strip()]))
        if cache.get("VICTIM_STATUS_DP"):
            dp_syns = list(set(dp_syns + [item["word"].lower() for item in cache["VICTIM_STATUS_DP"] if item.get("word") and item["word"].strip()]))
            
        s_syns.sort(key=len, reverse=True)
        md_syns.sort(key=len, reverse=True)
        dp_syns.sort(key=len, reverse=True)
        
        s_pattern = "|".join(re.escape(s) for s in s_syns)
        md_pattern = "|".join(re.escape(m) for m in md_syns)
        dp_pattern = "|".join(re.escape(d) for d in dp_syns)
        
        cls._victim_status_patterns_compiled[tenant_slug] = {
            "selamat": re.compile(
                rf"(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:\w+\s+){{0,3}}(?:{s_pattern})",
                re.IGNORECASE,
            ),
            "meninggal": re.compile(
                rf"(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:\w+\s+){{0,3}}(?:{md_pattern})",
                re.IGNORECASE,
            ),
            "hilang": re.compile(
                rf"(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:\w+\s+){{0,3}}(?:{dp_pattern})",
                re.IGNORECASE,
            ),
        }


    # ── Regex: Coordinate patterns ────────────────────────────────
    # DMS format: 3°22'20.92"LU / 106°13'51.78"BT  (or N/S/E/W)
    _DMS_PATTERN = re.compile(
        r"(\d{1,3})\s*[°º]\s*(\d{1,2})\s*[''′]\s*"
        r"(\d{1,2}(?:[.,]\d+)?)?\s*[\"″]?\s*"
        r"([NSEW]|LU|LS|BT|BB)",
        re.IGNORECASE,
    )
    # Decimal format: -3.391282, 106.241521 or 3.391282 / 106.241521 or 3.391282°, 106.241521°
    _DECIMAL_COORD_PATTERN = re.compile(
        r"(-?\d{1,3}\.\d{3,8})[°º]?\s*[,/]\s*(-?\d{1,3}\.\d{3,8})[°º]?"
    )

    # ── Regex: Vessel / Ship ──────────────────────────────────────
    _VESSEL_PREFIXES = r"(?:KM|KMN|KRI|TB|RIB|RHIB|MV|MT|LCT|TK|BG)"
    _VESSEL_PATTERN = re.compile(
        rf"({_VESSEL_PREFIXES})[\.\s]+([A-Za-z][A-Za-z0-9\s]{{1,40}})",
        re.IGNORECASE,
    )
    _VESSEL_GENERIC = re.compile(
        r"(?:kapal|pompong|perahu|speedboat|tongkang|tugboat|tanker)"
        r"(?:\s+(?:motor|nelayan|penumpang|cargo|yacht))?"
        r"(?:\s+([A-Z][a-zA-Z0-9\s]{1,30}))?",
        re.IGNORECASE,
    )
    _GT_PATTERN = re.compile(r"(?:GT\s*[:\s]?\s*(\d+)|(\d+)\s*GT)", re.IGNORECASE)

    # ── Regex: Detailed victim breakdown ──────────────────────────
    _NUM_WORDS = {
        "satu": "1", "dua": "2", "tiga": "3", "empat": "4", "lima": "5",
        "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9",
        "sepuluh": "10", "sebelas": "11", "dua belas": "12",
        "sebanyak": "",  # prefix penanda jumlah, bukan angka
    }


    _VICTIM_STATUS_PATTERNS = {
        "selamat": re.compile(
            r"(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:\w+\s+){0,3}(?:selamat|dievakuasi|terselamatkan)",
            re.IGNORECASE,
        ),
        "meninggal": re.compile(
            r"(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:\w+\s+){0,3}(?:meninggal|tewas|MD|mati)",
            re.IGNORECASE,
        ),
        "hilang": re.compile(
            r"(\d+)\s*(?:\([a-z]+\)\s*)?(?:orang?\s*)?(?:\w+\s+){0,3}(?:hilang|DP|belum ditemukan|dalam pencarian|masih dalam pencarian)",
            re.IGNORECASE,
        ),
    }

    # =================================================================
    # Main extraction method
    # =================================================================

    @staticmethod
    async def extract_all(message: str, db: AsyncSession) -> Dict[str, Any]:
        """Run all rule-based extractors and return a dict of found fields."""
        info = getattr(db, "info", None)
        tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else (tenant_context.get() or "global")
        
        # Set active tenant context
        token = tenant_context.set(tenant_slug)
        try:
            if not RuleExtractor._cache_loaded:
                await RuleExtractor.load_cache(db)

            from app.services.autocorrect_service import AutoCorrectService
            normalized_msg = AutoCorrectService.normalize_colloquial_tokens(message) if message else ""

            extracted: Dict[str, Any] = {
                "kronologi": message,
                "chronology": message,
            }

            # 1. Incident Type (Classification) & Vessel Context
            jenis_kejadian = await RuleExtractor.extract_incident_type(normalized_msg, db)
            vessel_ctx = RuleExtractor.extract_vessel_context(normalized_msg)

            if jenis_kejadian:
                extracted["jenis_kejadian"] = jenis_kejadian
                extracted["incident_type"] = jenis_kejadian
            elif vessel_ctx and vessel_ctx.get("incident_type"):
                extracted["jenis_kejadian"] = vessel_ctx["incident_type"]
                extracted["incident_type"] = vessel_ctx["incident_type"]

            if vessel_ctx:
                if vessel_ctx.get("sub_incident_type"):
                    extracted["sub_jenis_kejadian"] = vessel_ctx["sub_incident_type"]
                    extracted["sub_incident_type"] = vessel_ctx["sub_incident_type"]
                if vessel_ctx.get("uses_vessel"):
                    extracted["pakai_kapal"] = vessel_ctx["uses_vessel"]
                    extracted["uses_vessel"] = vessel_ctx["uses_vessel"]
                if vessel_ctx.get("victim_condition"):
                    extracted["kondisi_korban"] = vessel_ctx["victim_condition"]
                    extracted["victim_condition"] = vessel_ctx["victim_condition"]

            # 2. Location (Lokasi)
            lokasi = await RuleExtractor.extract_location(normalized_msg, db)
            if lokasi:
                # If maritime/vessel context and location is an island without 'Perairan', normalize it
                if vessel_ctx and re.match(r"^Pulau\s+", lokasi, re.IGNORECASE):
                    lokasi = f"Perairan {lokasi}"
                extracted["lokasi_teks"] = lokasi
                extracted["location_text"] = lokasi

            # 3. Time (Waktu)
            waktu = RuleExtractor.extract_time(normalized_msg)
            if waktu:
                extracted["waktu"] = waktu
                extracted["incident_time"] = waktu

            # 4. Victim Count (Korban)
            korban = RuleExtractor.extract_victim_count(normalized_msg)
            if korban:
                extracted["korban"] = korban
                extracted["victim_summary"] = korban

            # 5. Coordinates (Koordinat)
            coords = RuleExtractor.extract_coordinates(message)
            if coords:
                extracted["koordinat_lat"] = coords[0]
                extracted["koordinat_lng"] = coords[1]
                extracted["latitude"] = coords[0]
                extracted["longitude"] = coords[1]
                extracted["koordinat"] = f"{coords[0]}, {coords[1]}"
                extracted["coordinates"] = f"{coords[0]}, {coords[1]}"
                extracted["_explicit_koordinat"] = True

            # 6. Vessel Data (Data Kapal)
            data_kapal = RuleExtractor.extract_vessel_data(normalized_msg)
            if data_kapal:
                extracted["data_kapal"] = data_kapal
                extracted["vessel_data"] = data_kapal
                extracted["pakai_kapal"] = "Ya"
                extracted["uses_vessel"] = "Ya"
            elif vessel_ctx and vessel_ctx.get("vessel_data"):
                extracted["data_kapal"] = vessel_ctx["vessel_data"]
                extracted["vessel_data"] = vessel_ctx["vessel_data"]

            # 7. Reporter Relation (Hubungan Pelapor dan Korban)
            relation = RuleExtractor.extract_reporter_relation(normalized_msg)
            if relation:
                extracted["pelapor_hubungan"] = relation
                extracted["reporter_relation"] = relation

            # 8. Victim Breakdown Detail (selamat / MD / DP)
            detail = RuleExtractor.extract_victim_breakdown(normalized_msg)
            if detail:
                extracted["korban_detail"] = detail

            # 9. Dictionary-aware enrichment (expand abbreviations)
            try:
                hints = await RuleExtractor.enrich_with_dictionary(normalized_msg, db)
                if hints:
                    extracted["_dictionary_hints"] = hints
            except Exception as e:
                logger.warning(f"[RuleExtractor] Dictionary enrichment non-critical: {e}")

            return extracted
        finally:
            tenant_context.reset(token)

    # =================================================================
    # Individual extractors (English Primary Names + Indonesian Aliases)
    # =================================================================

    @staticmethod
    def extract_vessel_context(message: str) -> Optional[Dict[str, str]]:
        """
        Detect maritime vessel + problem context (e.g. 'pompongnya mati', 'kapal mogok',
        'perahu tenggelam') and infer incident_type, sub_incident_type, uses_vessel, and vessel_data.
        Prevents 'mati' after a vessel from being misclassified as victim death (MD).
        """
        if not message:
            return None

        from app.services.autocorrect_service import AutoCorrectService
        msg_norm = AutoCorrectService.normalize_colloquial_tokens(message).lower()

        vessel_types = [
            "speedboat", "ketinting", "tongkang", "pompong", "tugboat",
            "perahu", "sampan", "jukung", "pancung", "kapal"
        ]
        vt_pattern = "|".join(vessel_types)

        # Pattern A: Vessel followed by engine failure ('pompongnya mati', 'kapal mati mesin', 'pompong mogok')
        engine_fail_match = re.search(
            rf"\b({vt_pattern})(?:nya|ku|mu)?\s+(?:saya\s+|kami\s+|itu\s+|sedang\s+|mengalami\s+)?(mati\s+mesin|mati|mogok|rusak\s+mesin|patah\s+as|patah\s+kemudi|kehabisan\s+(?:bbm|solar|bensin|minyak))\b",
            msg_norm,
            re.IGNORECASE
        )
        if engine_fail_match:
            vessel_raw = engine_fail_match.group(1).title()
            problem_raw = engine_fail_match.group(2).lower()
            if problem_raw in ("mati", "mati mesin", "mogok", "rusak mesin"):
                sub_type = f"{vessel_raw} Mati Mesin"
            elif "patah" in problem_raw:
                sub_type = f"{vessel_raw} {problem_raw.title()}"
            else:
                sub_type = f"{vessel_raw} Kehabisan BBM"
            return {
                "incident_type": "LAKA KAPAL",
                "sub_incident_type": sub_type,
                "uses_vessel": "Ya",
                "vessel_data": f"Jenis: {vessel_raw}",
                "victim_condition": sub_type,
            }

        # Pattern B: Vessel followed by maritime accident ('pompong tenggelam', 'kapal terbalik', 'perahu hanyut')
        accident_match = re.search(
            rf"\b({vt_pattern})(?:nya|ku|mu)?\s+(?:saya\s+|kami\s+|itu\s+|sedang\s+|mengalami\s+)?(tenggelam|karam|terbalik|hanyut|kandas|terbakar|kebakaran|tabrakan|bocor|hilang\s+kontak|lost\s+contact|belum\s+kembali|belum\s+pulang)\b",
            msg_norm,
            re.IGNORECASE
        )
        if accident_match:
            vessel_raw = accident_match.group(1).title()
            problem_raw = accident_match.group(2).lower()
            if problem_raw == "karam":
                problem_title = "Tenggelam"
            else:
                problem_title = problem_raw.title()
            sub_type = f"{vessel_raw} {problem_title}"
            return {
                "incident_type": "LAKA KAPAL",
                "sub_incident_type": sub_type,
                "uses_vessel": "Ya",
                "vessel_data": f"Jenis: {vessel_raw}",
                "victim_condition": sub_type,
            }

        return None

    @staticmethod
    def extract_reporter_relation(message: str) -> str:
        """
        Extract the relationship between the reporter and the victim(s) from conversational text.
        Examples:
          - 'Kakak saya pomponya mati' -> 'Keluarga Korban (Kakak)'
          - 'Teman saya belum pulang melaut' -> 'Rekan Korban'
          - 'Saya melihat kapal terbalik' -> 'Saksi Mata'
        """
        if not message:
            return ""

        msg_lower = message.lower()

        # 1. Self-identification patterns: Pelapor menyebutkan posisi dirinya terhadap korban
        #    Contoh: "Saya kakaknya", "Saya kakak korban", "Saya ayahnya"
        self_id_map = [
            (r"\b(?:saya|aku)\s+(?:adalah\s+)?(?:kakak|abang)(?:nya|\s+korban)\b", "Kakak Korban"),
            (r"\b(?:saya|aku)\s+(?:adalah\s+)?(?:adik|adek)(?:nya|\s+korban)\b", "Adik Korban"),
            (r"\b(?:saya|aku)\s+(?:adalah\s+)?(?:ayah|bapak|papa|ibu|mama|orang\s+tua)(?:nya|\s+korban)\b", "Orang Tua Korban"),
            (r"\b(?:saya|aku)\s+(?:adalah\s+)?(?:anak|putra|putri)(?:nya|\s+korban)\b", "Anak Korban"),
            (r"\b(?:saya|aku)\s+(?:adalah\s+)?suami(?:nya|\s+korban)\b", "Suami Korban"),
            (r"\b(?:saya|aku)\s+(?:adalah\s+)?istri(?:nya|\s+korban)\b", "Istri Korban"),
        ]
        for pattern, label in self_id_map:
            if re.search(pattern, msg_lower):
                return label

        # 2. Reciprocal kinship patterns: Pelapor menyebutkan siapa korbannya ("<Kerabat> saya [mengalami musibah]")
        #    Jika korban adalah Kakak saya -> maka Pelapor adalah Adik Korban!
        reciprocal_family_map = [
            (r"\b(kakak|abang|kk)\s+(?:kandung\s+|laki-laki\s+|perempuan\s+|ipar\s+)?(?:saya|aku|kami|kita)\b", "Adik Korban"),
            (r"\b(adik|adek)\s+(?:kandung\s+|laki-laki\s+|perempuan\s+|ipar\s+)?(?:saya|aku|kami|kita)\b", "Kakak Korban"),
            (r"\b(ayah|bapak|bapa|papa|abi|ibu|emak|mamak|mama|bunda|orang\s+tua)\s+(?:kandung\s+|mertua\s+)?(?:saya|aku|kami|kita)\b", "Anak Korban"),
            (r"\b(anak|putra|putri)\s+(?:kandung\s+|laki-laki\s+|perempuan\s+)?(?:saya|aku|kami|kita)\b", "Orang Tua Korban"),
            (r"\b(suami)\s+(?:saya|aku)\b", "Istri Korban"),
            (r"\b(istri)\s+(?:saya|aku)\b", "Suami Korban"),
            (r"\b(paman|om|pakcik|pakde|bibi|tante|makcik|bude)\s+(?:saya|aku|kami|kita)\b", "Keponakan Korban"),
            (r"\b(keponakan)\s+(?:saya|aku|kami|kita)\b", "Paman/Bibi Korban"),
            (r"\b(kakek|nenek)\s+(?:saya|aku|kami|kita)\b", "Cucu Korban"),
            (r"\b(sepupu|ipar|mertua|menantu|keluarga|saudara|kerabat)\s+(?:saya|aku|kami|kita)\b", "Keluarga Korban"),
        ]
        for pattern, label in reciprocal_family_map:
            if re.search(pattern, msg_lower):
                return label

        colleague_patterns = [
            (r"\b(teman|rekan|kawan|sahabat|abk|anak\s+buah|anggota)\s+(?:kerja\s+|melaut\s+)?(?:saya|aku|kami|kita)\b", "Rekan Korban"),
            (r"\b(tetangga)\s+(?:saya|aku|kami|kita)\b", "Tetangga / Warga"),
            (r"\b(?:saya|kami)\s+melihat\b", "Saksi Mata"),
        ]
        for pattern, label in colleague_patterns:
            if re.search(pattern, msg_lower):
                return label

        # Direct victim patterns (only if no third-person relation was matched above)
        direct_victim_patterns = [
            r"\b(?:kapal|pompong|perahu|speedboat|sampan|ketinting)\s+(?:saya|kami|kita)\b",
            r"\b(?:kami|saya)\s+(?:mengalami|terjebak|terombang[\s-]*ambing|mati\s+mesin|hanyut|tenggelam|butuh\s+evakuasi)\b",
        ]
        for pattern in direct_victim_patterns:
            if re.search(pattern, msg_lower):
                return "Korban Langsung"

        return ""

    # Backward compatibility alias
    extract_hubungan_pelapor = extract_reporter_relation

    @staticmethod
    async def extract_incident_type(message: str, db: AsyncSession) -> str:
        """Match against Classification keywords in DB."""
        from app.services.autocorrect_service import AutoCorrectService
        msg_lower = AutoCorrectService.normalize_colloquial_tokens(message).lower() if message else ""
        try:
            result = await db.execute(select(Classification))
            classifications = result.scalars().all()
            for cls in classifications:
                if not cls.keywords:
                    continue
                keywords = [kw.strip().lower() for kw in cls.keywords.split(",") if kw.strip()]
                for keyword in keywords:
                    if keyword in msg_lower:
                        return cls.category.upper()

                if cls.category.lower() in msg_lower:
                    return cls.category.upper()
        except Exception as e:
            logger.error(f"[RuleExtractor] Failed to extract jenis kejadian: {e}")

        # Check approved incident keywords in DictionaryWord (Cache or DB)
        if RuleExtractor._cache_loaded:
            cache_words = RuleExtractor._dictionary_cache.get("INCIDENT_KEYWORD", [])
            for item in cache_words:
                word = item["word"]
                target = item["ner_target"]
                if word and word.lower() in msg_lower and target:
                    return target.upper()
        else:
            try:
                from app.models.knowledge_models import DictionaryWord, DictionaryStatus
                result = await db.execute(
                    select(DictionaryWord).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED,
                        DictionaryWord.ner_type.in_(["Nama Kejadian", "Klasifikasi Kejadian", "INCIDENT_KEYWORD"])
                    )
                )
                dict_incidents = result.scalars().all()
                for dw in dict_incidents:
                    if dw.word and dw.word.lower() in msg_lower and dw.ner_target:
                        return dw.ner_target.upper()
            except Exception as e:
                logger.error(f"[RuleExtractor] Failed to extract jenis kejadian from DictionaryWord: {e}")

        return ""

    # Backward compatibility alias
    extract_jenis_kejadian = extract_incident_type

    @staticmethod
    async def extract_location(message: str, db: AsyncSession) -> str:
        """Match against Location DB and common location patterns."""
        from app.services.autocorrect_service import AutoCorrectService
        msg_normalized = AutoCorrectService.normalize_colloquial_tokens(message) if message else ""
        msg_lower = msg_normalized.lower()

        # Check explicit Location names from DB
        try:
            result = await db.execute(select(Location))
            locations = result.scalars().all()
            for loc in locations:
                if loc.name and loc.name.lower() in msg_lower:
                    return loc.name
        except Exception as e:
            logger.error(f"[RuleExtractor] Failed to extract lokasi from DB: {e}")

        # Check approved location names in DictionaryWord (Cache or DB)
        if RuleExtractor._cache_loaded:
            cache_words = []
            for k in ["Nama Tempat", "Lokasi", "Geografi", "LOCATION", "MEDAN_PERAIRAN"]:
                cache_words.extend(RuleExtractor._dictionary_cache.get(k, []))
            cache_words.sort(key=lambda x: len(x["word"] or ""), reverse=True)
            for item in cache_words:
                word = item["word"]
                if word and word.lower() in msg_lower:
                    return word.title()
        else:
            try:
                from app.models.knowledge_models import DictionaryWord, DictionaryStatus
                result = await db.execute(
                    select(DictionaryWord).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED,
                        DictionaryWord.ner_type.in_(["Nama Tempat", "Lokasi", "Geografi", "LOCATION", "MEDAN_PERAIRAN"])
                    )
                )
                dict_locations = result.scalars().all()
                for dw in dict_locations:
                    if dw.word and dw.word.lower() in msg_lower:
                        return dw.word.title()
            except Exception as e:
                logger.error(f"[RuleExtractor] Failed to extract lokasi from DictionaryWord: {e}")

        # Fetch Location Prefixes from Dictionary (merge with default prefixes so compound prefixes aren't lost)
        default_prefixes = ["di dekat", "di sekitar", "dekat", "sekitar", "di", "pada"]
        prefixes = list(default_prefixes)
        if RuleExtractor._cache_loaded:
            db_prefixes = [item["word"].strip().lower() for item in RuleExtractor._dictionary_cache.get("LOCATION_PREFIX", []) if item.get("word") and item["word"].strip()]
            if db_prefixes:
                prefixes = list(set(default_prefixes + db_prefixes))
        else:
            try:
                from app.models.knowledge_models import DictionaryWord, DictionaryStatus
                result = await db.execute(
                    select(DictionaryWord.word).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED,
                        DictionaryWord.ner_type == "LOCATION_PREFIX"
                    )
                )
                db_prefixes = [row.strip().lower() for row in result.scalars().all() if row.strip()]
                if db_prefixes:
                    prefixes = list(set(default_prefixes + db_prefixes))
            except Exception as e:
                logger.warning(f"[RuleExtractor] Failed to load location prefixes from dictionary: {e}")

        prefixes.sort(key=len, reverse=True)

        # Build regex group for prefixes: (?:di dekat|di sekitar|dekat|sekitar|di|pada)
        prefix_group = r"(?:" + "|".join(re.escape(p) for p in prefixes) + r")\s+"

        # Location types from pre-warmed cache or fallback
        loc_types = []
        if RuleExtractor._dictionary_cache.get("LOCATION_TYPE"):
            db_loc_types = [item["word"].lower() for item in RuleExtractor._dictionary_cache["LOCATION_TYPE"] if item.get("word") and item["word"].strip()]
            loc_types = list(set(loc_types + db_loc_types))
        if not loc_types:
            loc_types = ["perairan", "sungai", "gunung", "laut", "pantai", "danau", "selat", "hutan", "tanjung", "bukit", "desa", "kelurahan", "kecamatan", "jalan", "jembatan", "pulau"]
        elif "pulau" not in loc_types:
            loc_types.append("pulau")
        loc_types.sort(key=len, reverse=True)

        patterns = []
        for loc_type in loc_types:
            patterns.append(rf"{prefix_group}{loc_type}\s+([a-z0-9\s]+)")

        # Generic fallback
        patterns.extend([
            r"lokasi\s+di\s+([a-z0-9\s]+)",
            r"lokasi\s*:\s*([a-z0-9\s]+)",
        ])

        # Get stop words for location trimming (hybrid approach)
        stop_words = ["kejadiannya", "kejadian", "status", "korban", "kondisi", "kronologi", "dan", "sarana", "alut", "kapal", "pesawat"]
        if RuleExtractor._cache_loaded:
            db_stops = [item["word"].strip().lower() for item in RuleExtractor._dictionary_cache.get("LOCATION_STOP_WORD", []) if item.get("word") and item["word"].strip()]
            if db_stops:
                stop_words = list(set(stop_words + db_stops))
        stop_words.sort(key=len, reverse=True)

        stop_pattern_str = r"\b(?:" + "|".join(re.escape(sw) for sw in stop_words) + r")\b|\bpukul\s*\d+|\bjam\s*\d+|\bpada\s+jam\b"
        stop_regex = re.compile(stop_pattern_str, re.IGNORECASE)

        known_islands = {"senoa", "jemaja", "subi", "midai", "serasan", "panjang", "tiga", "sedanau", "bunguran", "laut"}
        if RuleExtractor._cache_loaded and RuleExtractor._dictionary_cache.get("ISLAND"):
            for item in RuleExtractor._dictionary_cache["ISLAND"]:
                if item.get("word"):
                    known_islands.add(item["word"].strip().lower())

        for p in patterns:
            match = re.search(p, msg_lower)
            if match:
                raw = match.group(0).strip()
                # Check if proximity prefix ('di dekat', 'dekat', 'di sekitar', 'sekitar') was used with an island/water body
                is_proximity = bool(re.match(r"^(?:di\s+)?(?:dekat|sekitar)\s+", raw, flags=re.IGNORECASE))

                # Strip navigation prefix: "lokasi di ", "lokasi: ", "di dekat ", "dekat ", "di sekitar ", "sekitar ", "di ", "pada "
                raw = re.sub(
                    r'^(?:lokasi\s+di\s+|lokasi\s*:\s*|(?:di\s+)?(?:dekat|sekitar)\s+|di\s+|pada\s+)',
                    '', raw, flags=re.IGNORECASE
                )

                # Trim location text if a boundary transition word is found
                boundary_match = stop_regex.search(raw)
                if boundary_match:
                    raw = raw[:boundary_match.start()].strip()

                # Take at most 4 words (avoid capturing long sentences)
                words = raw.split()
                location = " ".join(words[:4]).strip(",.:; ")
                if len(location) >= 3:
                    loc_title = location.title()
                    # Normalize proximity to an island ('dekat pulau senoa' -> 'Perairan Pulau Senoa')
                    if is_proximity and (
                        location.lower().startswith("pulau ")
                        or any(isl in location.lower().split() for isl in known_islands)
                    ):
                        if not loc_title.lower().startswith("perairan "):
                            loc_title = f"Perairan {loc_title}"
                    return loc_title

        return ""

    # Backward compatibility alias
    extract_lokasi = extract_location


    @staticmethod
    def extract_time(message: str) -> str:
        """Extract time references using regex.
        Guard: hasil harus <= 60 karakter, lebih dari itu dianggap false positive.
        """
        msg_lower = message.lower()
        MAX_WAKTU_LEN = 60  # Guard: waktu tidak boleh lebih panjang dari ini

        # Date patterns first (more specific)
        date_patterns = [
            # "30 April 2026 pukul 06.00 WIB"
            r"(\d{1,2}\s+(?:januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s+\d{4}(?:\s+(?:pukul|jam)?\s*\d{1,2}[.:]\d{2}(?:\s*(?:wib|wita|wit))?)?)",
            # "2026-05-29 pukul 20:20" or "2026-05-29 20:20"
            r"(\d{4}[/\-]\d{1,2}[/\-]\d{1,2}(?:\s+(?:pukul|jam)?\s*\d{1,2}[.:]\d{2}(?:\s*(?:wib|wita|wit))?)?)",
            # "30/04/2026" atau "30-04-2026"
            r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}(?:\s+(?:pukul|jam)?\s*\d{1,2}[.:]\d{2}(?:\s*(?:wib|wita|wit))?)?)",
        ]
        for p in date_patterns:
            match = re.search(p, msg_lower)
            if match:
                result = match.group(0).strip().title()
                if len(result) <= MAX_WAKTU_LEN:
                    return result

        # Specific time formats: "jam 10", "pukul 14:00", "08.00 WIB"
        time_patterns = [
            r"(?:jam|pukul)\s+(\d{1,2}[.:]\d{2}\s*(?:wib|wita|wit)?)",
            r"jam\s+(\d{1,2}(?:\s*(?:pagi|siang|sore|malam))?)",
            r"pukul\s+(\d{1,2}(?:\s*(?:pagi|siang|sore|malam|wib|wita|wit))?)",
            r"sekitar\s+(?:jam\s+|pukul\s+)?(\d{1,2}[.:]\d{2}\s*(?:wib|wita|wit)?)",
            r"(\d{1,2}[.:]\d{2})\s*(?:wib|wita|wit)",  # "08.00 WIB" or "10:00 WIB" standalone
        ]
        for p in time_patterns:
            match = re.search(p, msg_lower)
            if match:
                result = f"Pukul {match.group(1).upper().strip()}"
                if len(result) <= MAX_WAKTU_LEN:
                    return result

        # Simple relative time keywords from pre-warmed cache or fallback
        keywords = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("TIME_MARKER", [])] if RuleExtractor._dictionary_cache.get("TIME_MARKER") else [
            "kemarin malam", "kemarin sore", "kemarin pagi", "kemarin siang",
            "tadi malam", "tadi pagi", "tadi sore", "tadi siang",
            "malam tadi", "siang tadi", "pagi tadi",
            "dini hari tadi", "subuh tadi", "semalam",
            "hari ini", "pagi ini", "sore ini", "kemarin",
        ]
        for kw in keywords:
            if kw in msg_lower:
                return kw.title()

        return ""

    # Backward compatibility alias
    extract_waktu = extract_time

    @staticmethod
    def _normalize_num_format(text: str) -> str:
        """
        Normalisasi format angka Indonesia sebelum regex matching.
        Contoh: '6 (enam) orang' → '6 orang'
                '3 (tiga) orang anak-anak' → '3 orang anak'
        Menghilangkan tanda kurung kata angka agar regex digit bisa cocok.
        """
        # Hapus pola '(kata-angka)' setelah digit
        normalized = re.sub(
            r"(\d+)\s*\([a-zA-Z\s-]+\)",
            r"\1",
            text,
            flags=re.IGNORECASE,
        )
        # Normalisasi 'anak-anak' → 'anak'
        normalized = re.sub(r"anak-anak", "anak", normalized, flags=re.IGNORECASE)
        return normalized

    @staticmethod
    def extract_victim_count(message: str) -> str:
        """Extract victim counts. Prefers victim-specific count (tenggelam/hilang)
        over total involved. Handles format 'N (kata) orang' via normalization.
        Also handles named victim format: 'Identitas korban, Arman Laki-laki 46 Tahun'.
        """
        # Normalisasi format '6 (enam) orang' → '6 orang' sebelum matching
        msg_normalized = RuleExtractor._normalize_num_format(message).lower()

        # Standalone group words: check if the normalized text contains any quantifier word
        group_words = ["berdua", "bertiga", "berempat", "berlima", "berenam", "bertujuh", "berdelapan", "bersembilan", "bersepuluh"]
        db_group_words = []
        db_mapping = {}
        if RuleExtractor._dictionary_cache.get("QUANTIFIER"):
            for item in RuleExtractor._dictionary_cache["QUANTIFIER"]:
                word = item["word"].lower()
                target = item["ner_target"]
                if word.startswith("ber") and target.isdigit():
                    db_group_words.append(word)
                    db_mapping[word] = f"{target} Orang"
        
        group_words_list = list(set(group_words + db_group_words))
        group_words_list.sort(key=len, reverse=True)
        
        group_pattern = r"\b(" + "|".join(re.escape(w) for w in group_words_list) + r")\b"
        group_match = re.search(group_pattern, msg_normalized)
        if group_match:
            word = group_match.group(1)
            default_mapping = {
                "berdua": "2 Orang", "bertiga": "3 Orang", "berempat": "4 Orang", "berlima": "5 Orang",
                "berenam": "6 Orang", "bertujuh": "7 Orang", "berdelapan": "8 Orang", "bersembilan": "9 Orang",
                "bersepuluh": "10 Orang"
            }
            combined_mapping = {**default_mapping, **db_mapping}
            if word in combined_mapping:
                return combined_mapping[word]

        # Get dynamic _NUM_WORDS mapping
        num_words = {
            "satu": "1", "dua": "2", "tiga": "3", "empat": "4", "lima": "5",
            "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9",
            "sepuluh": "10", "sebelas": "11", "dua belas": "12",
            "sebanyak": "",
        }
        if RuleExtractor._dictionary_cache.get("QUANTIFIER"):
            for item in RuleExtractor._dictionary_cache["QUANTIFIER"]:
                word = item["word"].lower()
                target = item["ner_target"]
                if target.isdigit():
                    num_words[word] = target
                elif target == "":
                    num_words[word] = ""

        # Compound subject counting: e.g. "Kakak saya bersama 2 temannya" -> 1 + 2 = 3 Orang
        word_num_keys = "|".join(re.escape(w) for w in num_words.keys() if w != "sebanyak")
        compound_with_num = re.search(
            rf"\b(?:(?:kakak|abang|adik|adek|ayah|bapak|ibu|suami|istri|anak|paman|om|bibi|tante|kakek|nenek|teman|rekan|tetangga)\s+(?:saya|aku|kami)|saya|aku)\s+"
            rf"(?:bersama|sama|dengan|dan)\s+(?:dengan\s+)?(\d+|{word_num_keys})\s*(?:orang\s+)?"
            rf"(?:teman|rekan|kawan|sahabat|abk|anak\s*buah|anggota|orang|anak|saudara|kerabat|tetangga)(?:nya|\s+saya|\s+kami)?\b",
            msg_normalized,
        )
        if compound_with_num:
            raw_n = compound_with_num.group(1)
            n_str = num_words.get(raw_n, raw_n)
            if n_str and n_str.isdigit():
                return f"{1 + int(n_str)} Orang"

        # Compound subject with single companion: e.g. "Kakak saya sama temannya", "Ayah saya dan ibunya" -> 2 Orang
        compound_single = re.search(
            r"\b(?:(?:kakak|abang|adik|adek|ayah|bapak|ibu|suami|istri|anak|paman|om|bibi|tante|kakek|nenek|teman|rekan|tetangga)\s+(?:saya|aku|kami)|saya|aku)\s+"
            r"(?:bersama|sama|dengan|dan)\s+(?:seorang\s+)?(?:teman|rekan|kawan|sahabat|adik|adek|kakak|abang|anak|istri|suami|ayah|bapak|ibu)(?:nya|\s+saya|\s+kami)?\b",
            msg_normalized,
        )
        if compound_single:
            return "2 Orang"

        # Get dynamic roles & generics
        default_roles = ["abk", "pemancing", "nelayan", "penumpang", "pendaki", "wisatawan", "anak", "balita", "korban", "orang", "jiwa", "warga", "personel"]
        db_roles = default_roles.copy()
        if RuleExtractor._dictionary_cache:
            roles_from_db = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("VICTIM_ROLE", []) if item.get("word") and item["word"].strip()]
            quantifiers_as_roles = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("QUANTIFIER", []) if not item["ner_target"].isdigit() and item.get("word") and item["word"].strip()]
            db_roles = list(set(db_roles + roles_from_db + quantifiers_as_roles))
        db_roles.sort(key=len, reverse=True)
            
        ROLES = "|".join(re.escape(r) for r in db_roles)
        
        default_generics = ["orang", "korban", "jiwa", "abk", "penumpang", "nelayan", "pemancing", "pendaki", "wisatawan", "anak", "balita", "warga", "personel"]
        db_generics = default_generics.copy()
        if RuleExtractor._dictionary_cache:
            generics_from_db = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("VICTIM_ROLE", []) if item.get("word") and item["word"].strip()]
            quantifiers_from_db = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("QUANTIFIER", []) if item.get("word") and item["word"].strip()]
            db_generics = list(set(db_generics + generics_from_db + quantifiers_from_db))
        db_generics.sort(key=len, reverse=True)
            
        GENERIC = "|".join(re.escape(g) for g in db_generics)

        # First: look for victim-specific patterns (tenggelam, hilang, korban)
        victim_patterns = [
            r"(\d+)\s+(?:orang?\s+)?(?:[a-z\-]+\s+)*?(?:tenggelam|hilang|korban)",
        ]
        victim_match = None
        victim_num = 0
        for p in victim_patterns:
            for match in re.finditer(p, msg_normalized):
                try:
                    n = int(match.group(1))
                    if n > victim_num:
                        victim_num = n
                        victim_match = match.group(0).strip()
                except ValueError:
                    pass
        if victim_match and victim_num > 0:
            return f"{victim_num} Orang".title()

        # Word numbers regex group dynamically
        word_num_pattern = "|".join(re.escape(w) for w in num_words.keys() if w != "sebanyak")

        # More specific: '6 orang anak', '2 orang nelayan'
        specific_patterns = [
            rf"(\d+)\s+orang\s+({ROLES})",
            rf"({word_num_pattern})\s+orang\s+({ROLES})",
        ]
        for p in specific_patterns:
            match = re.search(p, msg_normalized)
            if match:
                num = match.group(1)
                num = num_words.get(num, num)
                if num:  # skip empty (e.g. 'sebanyak')
                    return f"{num} Orang {match.group(2).title()}"

        # Generic: '6 orang', '3 korban'
        generic_patterns = [
            rf"(\d+)\s+({GENERIC})",
            rf"({word_num_pattern})\s+({GENERIC})",
        ]
        # Cari yang terbesar (total korban biasanya angka terbesar dalam pesan)
        best_match = None
        best_num = 0
        for p in generic_patterns:
            for match in re.finditer(p, msg_normalized):
                num_str = match.group(1)
                num_str = num_words.get(num_str, num_str)
                if not num_str:
                    continue
                try:
                    n = int(num_str)
                    if n > best_num:
                        best_num = n
                        best_match = (num_str, match.group(2))
                except ValueError:
                    pass
        if best_match:
            return f"{best_match[0]} {best_match[1]}".title()

        # ── Named victim patterns (formal SAR report format) ──
        # "Identitas korban, Arman Laki-laki 46 Tahun"
        # "korban bernama Arman" / "korban an. Budi"
        named_patterns = [
            # "identitas korban[,:] Name Gender Age Tahun"
            r"identitas\s+korban\s*[,:\-]\s*([A-Za-z][A-Za-z\s]+?)"
            r"\s+(laki[\s-]*laki|perempuan|pria|wanita)"
            r"\s+(\d{1,3})\s*(?:tahun|thn|th)",
            # "identitas korban[,:] Name Gender" (no age)
            r"identitas\s+korban\s*[,:\-]\s*([A-Za-z][A-Za-z\s]+?)"
            r"\s+(laki[\s-]*laki|perempuan|pria|wanita)",
            # "korban bernama/an./atas nama Name"
            r"korban\s+(?:bernama|atas\s+nama|an\.?)\s+([A-Za-z][A-Za-z\s]{1,40})",
            # "identitas korban[,:] Name" (name only)
            r"identitas\s+korban\s*[,:\-]\s*([A-Za-z][A-Za-z\s]{1,40})",
        ]

        for p in named_patterns:
            match = re.search(p, message, re.IGNORECASE)
            if match:
                groups = match.groups()
                name = groups[0].strip().rstrip(".,;:!?")
                # Build description
                parts = [name.title()]
                if len(groups) >= 2 and groups[1]:
                    gender = groups[1].strip().title()
                    parts.append(gender)
                if len(groups) >= 3 and groups[2]:
                    age = groups[2].strip()
                    parts.append(f"{age} Tahun")
                return f"1 Orang ({', '.join(parts)})"

        return ""

    # Backward compatibility alias
    extract_korban = extract_victim_count

    # ── Coordinates ───────────────────────────────────────────────

    @staticmethod
    def extract_coordinates(message: str) -> Optional[Tuple[float, float]]:
        """
        Extract coordinates from message text.
        Supports:
          - DMS:  3°22'20.92"LU / 106°13'51.78"BT
          - Decimal: -3.391282, 106.241521
        Returns (lat, lng) or None.
        """
        # Try DMS first (look for two DMS values)
        dms_matches = list(RuleExtractor._DMS_PATTERN.finditer(message))
        if len(dms_matches) >= 2:
            try:
                # Check direction suffixes
                dir0 = dms_matches[0].group(4).upper()
                dir1 = dms_matches[1].group(4).upper()
                
                # If first is longitude (E/W/BT/BB) and second is latitude (N/S/LU/LS), swap them
                if dir0 in ("E", "W", "BT", "BB") and dir1 in ("N", "S", "LU", "LS"):
                    lat = RuleExtractor._dms_to_decimal(dms_matches[1])
                    lng = RuleExtractor._dms_to_decimal(dms_matches[0])
                else:
                    lat = RuleExtractor._dms_to_decimal(dms_matches[0])
                    lng = RuleExtractor._dms_to_decimal(dms_matches[1])
                
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    logger.info(f"[RuleExtractor] Coordinates from DMS: {lat}, {lng}")
                    return (lat, lng)
            except (ValueError, IndexError) as e:
                logger.warning(f"[RuleExtractor] DMS parse error: {e}")

        # Try Google Maps data URL format: !3d-3.391282!4d106.241521
        gdata_match = re.search(r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)", message)
        if gdata_match:
            try:
                lat = float(gdata_match.group(1))
                lng = float(gdata_match.group(2))
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    logger.info(f"[RuleExtractor] Coordinates from Google Maps data URL: {lat}, {lng}")
                    return (lat, lng)
            except ValueError:
                pass

        # Try decimal format
        dec_match = RuleExtractor._DECIMAL_COORD_PATTERN.search(message)
        if dec_match:
            try:
                val1 = float(dec_match.group(1))
                val2 = float(dec_match.group(2))
                
                # Check if first value is out of valid latitude bounds [-90, 90] but within longitude bounds
                if (not (-90 <= val1 <= 90)) and (-90 <= val2 <= 90) and (-180 <= val1 <= 180):
                    lat, lng = val2, val1
                else:
                    lat, lng = val1, val2
                
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    logger.info(f"[RuleExtractor] Coordinates from decimal: {lat}, {lng}")
                    return (lat, lng)
            except ValueError:
                pass

        # Try space-separated decimal format: -3.391282 106.241521
        space_match = re.search(r"(-?\d{1,3}\.\d{3,8})[°º]?\s+(-?\d{1,3}\.\d{3,8})[°º]?", message)
        if space_match:
            try:
                val1 = float(space_match.group(1))
                val2 = float(space_match.group(2))
                if (not (-90 <= val1 <= 90)) and (-90 <= val2 <= 90) and (-180 <= val1 <= 180):
                    lat, lng = val2, val1
                else:
                    lat, lng = val1, val2
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    logger.info(f"[RuleExtractor] Coordinates from space-separated decimal: {lat}, {lng}")
                    return (lat, lng)
            except ValueError:
                pass

        return None

    # Backward compatibility alias
    extract_koordinat = extract_coordinates

    @staticmethod
    def _dms_to_decimal(match: re.Match) -> float:
        """Convert a DMS regex match to decimal degrees."""
        degrees = int(match.group(1))
        minutes = int(match.group(2))
        raw_seconds = match.group(3)
        seconds = float(raw_seconds.replace(",", ".")) if raw_seconds else 0.0
        direction = match.group(4).upper()

        decimal = degrees + minutes / 60 + seconds / 3600

        # South (S/LS) and West (W/BB) are negative
        if direction in ("S", "LS", "W", "BB"):
            decimal = -decimal

        return round(decimal, 6)

    # ── Vessel Data ───────────────────────────────────────────────

    @staticmethod
    def extract_vessel_data(message: str) -> str:
        """
        Extract vessel/ship info from message.
        Captures: vessel type, prefix, name, GT, and color from the dynamically loaded dictionary.
        All matching is fully case-insensitive to handle panicking reporters typing in lowercase.
        Supports multiple vessel extractions and enclitic suffixes (-nya, -ku, -mu).
        """
        from app.services.autocorrect_service import AutoCorrectService
        msg_norm = AutoCorrectService.normalize_colloquial_tokens(message) if message else ""
        msg_lower = msg_norm.lower()

        # 1. Load keywords from database dictionary cache (fallbacks to guarantee execution safety)
        vessel_types = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("VESSEL_TYPE", [])]
        if not vessel_types:
            vessel_types = ["pompong", "speedboat", "perahu", "kapal", "yacht", "tugboat", "tongkang", "sampan", "ketinting", "jukung", "pancung"]

        vessel_prefixes = [item["word"].upper() for item in RuleExtractor._dictionary_cache.get("VESSEL_PREFIX", [])]
        if not vessel_prefixes:
            vessel_prefixes = ["KM", "KMN", "KRI", "TB", "RIB", "RHIB", "MV", "MT", "LCT", "TK", "BG"]

        vessel_colors = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("VESSEL_COLOR", [])]
        if not vessel_colors:
            vessel_colors = ["biru", "merah", "putih", "hitam", "kuning", "hijau", "oranye", "jingga", "silver", "abu-abu", "cokelat"]

        color_prefixes = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("VESSEL_COLOR_PREFIX", [])]
        if not color_prefixes:
            color_prefixes = ["warna", "warne"]

        location_prefixes = [item["word"].lower() for item in RuleExtractor._dictionary_cache.get("LOCATION_PREFIX", [])]
        if not location_prefixes:
            location_prefixes = ["di", "pada", "dekat", "sekitar"]

        # Sort all arrays by length descending to match longest matches first
        vessel_types.sort(key=len, reverse=True)
        vessel_prefixes.sort(key=len, reverse=True)
        vessel_colors.sort(key=len, reverse=True)
        color_prefixes.sort(key=len, reverse=True)
        location_prefixes.sort(key=len, reverse=True)

        # 2. Find all occurrences of vessel prefixes or types in the message
        candidates = []
        # Find prefixes
        for vp in vessel_prefixes:
            for match in re.finditer(rf"\b{re.escape(vp)}\b", msg_norm, re.IGNORECASE):
                candidates.append({
                    "start": match.start(),
                    "end": match.end(),
                    "word": match.group(0),
                    "type": "PREFIX"
                })
        # Find types (including optional possessive suffix -nya/-ku/-mu)
        for vt in vessel_types:
            for match in re.finditer(rf"\b({re.escape(vt)})(?:nya|ku|mu)?\b", msg_lower):
                candidates.append({
                    "start": match.start(),
                    "end": match.end(),
                    "word": match.group(1),
                    "type": "TYPE"
                })

        # Sort candidates by start index ascending, then length descending
        candidates.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))

        # Filter overlapping matches and merge immediately adjacent compound vessel mentions (e.g. "kapal pompong" -> single Pompong match)
        generic_vessels = {"kapal", "perahu", "boat", "motor"}
        vessel_matches = []
        last_end = -1
        for cand in candidates:
            if cand["start"] >= last_end:
                if vessel_matches and (cand["start"] - vessel_matches[-1]["end"]) <= 2:
                    prev = vessel_matches[-1]
                    if prev["word"].lower() in generic_vessels and cand["word"].lower() not in generic_vessels:
                        # Upgrade the previous generic match (e.g. "kapal") to the specific vessel (e.g. "pompong")
                        vessel_matches[-1] = cand
                        last_end = cand["end"]
                        continue
                    elif cand["word"].lower() in generic_vessels:
                        last_end = cand["end"]
                        continue
                vessel_matches.append(cand)
                last_end = cand["end"]

        # If no vessel matched, return empty
        if not vessel_matches:
            return ""

        vessel_strings: List[str] = []

        # 3. For each vessel match, extract details from its corresponding text window
        for idx, match_info in enumerate(vessel_matches):
            # Calculate the window of text for this vessel
            start_pos = match_info["end"]
            # The window ends at the start of the next vessel match, or end of message
            next_start = vessel_matches[idx + 1]["start"] if idx + 1 < len(vessel_matches) else len(msg_norm)
            substring = msg_norm[start_pos:next_start]

            # Parse GT (Gross Tonnage) within this substring
            gt_val = ""
            gt_match = RuleExtractor._GT_PATTERN.search(substring)
            if gt_match:
                gt_val = gt_match.group(1) or gt_match.group(2)
                # Remove GT pattern from substring to avoid name pollution
                substring = substring[:gt_match.start()] + " " + substring[gt_match.end():]

            # Parse Color (Warna) within this substring
            warna_val = ""
            color_prefix_pattern = "|".join(re.escape(cp) for cp in color_prefixes)
            color_names_pattern = "|".join(re.escape(col) for col in vessel_colors)
            color_explicit_match = re.search(
                rf"\b(?:{color_prefix_pattern})\s+({color_names_pattern})\b",
                substring.lower()
            )
            if color_explicit_match:
                warna_val = color_explicit_match.group(1).title()
                substring = substring[:color_explicit_match.start()] + " " + substring[color_explicit_match.end():]
            else:
                for col in vessel_colors:
                    col_match = re.search(rf"\b{col}\b", substring.lower())
                    if col_match:
                        warna_val = col.title()
                        substring = substring[:col_match.start()] + " " + substring[col_match.end():]
                        break

            # Parse Name (Nama) from the remaining substring
            nama_val = ""
            sub_low = substring.lower()
            # Check for negative expressions ("tidak ada namanya", "tanpa nama", etc.)
            has_no_name = any(neg in sub_low for neg in [
                "tidak ada nama", "tanpa nama", "belum ada nama", "ga ada nama", "gak ada nama",
                "cuma sampan biasa", "sampan biasa", "kayu biasa"
            ])
            
            if not has_no_name:
                words = substring.strip().split()
                name_words = []

                # Dynamic separator words
                narrative_stopwords = [
                    "nelayan", "kayu", "fiber", "besi", "karet", "baja", "biasa",
                    "milik", "punya", "bapak", "pak", "ibu", "belum", "pulang", "kembali",
                    "melaut", "pergi", "mencari", "ikan", "tadi", "kemarin", "siang", "pagi",
                    "sore", "malam", "ada", "cuma", "hanya", "tidak", "tdk", "bukan",
                    "seorang", "orang", "abk", "awak", "kru", "penumpang"
                ]
                separator_words = set(
                    color_prefixes + location_prefixes + narrative_stopwords +
                    [vp.lower() for vp in vessel_prefixes] +
                    [vt.lower() for vt in vessel_types] +
                    ["gt", "gts", "g.t", "dan", "yang", "dari", "ke", "pukul", "jam", "di", "pada", "dekat", "sekitar", "saya", "kami", "kita", "mogok"]
                )
                # Add colors
                for col in vessel_colors:
                    separator_words.add(col.lower())
                # Add common incident verbs to stop name extraction before them
                incident_verbs = list(RuleExtractor._incident_verbs_cache) if RuleExtractor._incident_verbs_cache else ["terbakar", "tenggelam", "hanyut", "kelem", "mati", "mesin", "hilang", "meninggal", "selamat", "ditemukan", "pencarian", "evakuasi", "terbalik", "tubrukan", "tabrakan", "kandas", "pecah", "bocor", "rusak", "ledakan"]
                for iv in incident_verbs:
                    separator_words.add(iv.lower())

                for word in words:
                    word_clean = word.lower().strip(".,;:!?()\"'")
                    if word_clean in separator_words or re.match(r"^\d+", word_clean):
                        break
                    name_words.append(word)

                if name_words:
                    candidate_name = " ".join(name_words).strip(".,;:!?()\"' ").title()
                    # Reject candidate if it is just single common word
                    if candidate_name.lower() not in narrative_stopwords:
                        nama_val = candidate_name

            # Format this vessel's info
            v_parts = []
            if match_info["type"] == "PREFIX":
                v_parts.append(f"Jenis: {match_info['word'].upper()}")
            elif match_info["type"] == "TYPE":
                v_parts.append(f"Jenis: {match_info['word'].title()}")

            if nama_val:
                v_parts.append(f"Nama: {nama_val}")
            if gt_val:
                v_parts.append(f"GT: {gt_val}")
            if warna_val:
                v_parts.append(f"Warna: {warna_val}")

            if v_parts:
                vessel_strings.append("\n".join(v_parts))

        if vessel_strings:
            return "\n".join(vessel_strings)
        return ""

    # Backward compatibility alias
    extract_data_kapal = extract_vessel_data

    # ── Victim Breakdown Detail ───────────────────────────────────

    @staticmethod
    def extract_victim_breakdown(message: str) -> Optional[Dict[str, str]]:
        """
        Extract detailed victim breakdown: selamat, meninggal (MD), hilang (DP).
        Handles format 'N (kata) orang selamat' via normalization.
        Returns dict like {"selamat": "3", "meninggal": "0", "hilang": "2"}
        or None if no detail found.
        """
        # Normalisasi format '3 (tiga) orang selamat' → '3 orang selamat'
        normalized = RuleExtractor._normalize_num_format(message)
        detail: Dict[str, str] = {}

        tenant_slug = tenant_context.get()
        if tenant_slug not in RuleExtractor._victim_status_patterns_compiled:
            RuleExtractor._precompile_regexes(tenant_slug)
            
        victim_status_patterns = RuleExtractor._victim_status_patterns_compiled.get(tenant_slug, {})

        for status, pattern in victim_status_patterns.items():
            match = pattern.search(normalized)
            if match:
                detail[status] = match.group(1)

        return detail if detail else None

    # Backward compatibility alias
    extract_jumlah_korban_detail = extract_victim_breakdown


    # ── NEW: Dictionary Enrichment ────────────────────────────────

    @staticmethod
    async def enrich_with_dictionary(
        message: str, db: AsyncSession
    ) -> List[Dict[str, str]]:
        """
        Check message against APPROVED dictionary words.
        Returns list of matched terms with their definitions
        so the engine can use them as context without calling AI.
        """
        hints: List[Dict[str, str]] = []
        msg_upper = message.upper()

        try:
            from app.models.knowledge_models import DictionaryWord, DictionaryStatus
            result = await db.execute(
                select(DictionaryWord).where(
                    DictionaryWord.status == DictionaryStatus.APPROVED
                )
            )
            words = result.scalars().all()

            for w in words:
                if w.word and w.word.upper() in msg_upper and w.definition:
                    hints.append({
                        "word": w.word,
                        "definition": w.definition,
                    })
        except Exception as e:
            logger.warning(f"[RuleExtractor] Dictionary enrichment error: {e}")

        return hints


rule_extractor = RuleExtractor()
