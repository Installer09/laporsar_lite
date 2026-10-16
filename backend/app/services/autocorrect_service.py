import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.knowledge_models import DictionaryWord, DictionaryStatus
from app.db.session import (
    tenant_context,
    TenantPartitionedCache,
    MultitenantServiceMeta,
)

logger = logging.getLogger(__name__)

class AutoCorrectService(metaclass=MultitenantServiceMeta):
    """
    Service to handle auto-correction of reporter messages.
    Replaces approved typos, slang, and informal synonyms with standard SAR vocabulary
    prior to running the extraction pipeline.
    """
    _synonym_mappings = TenantPartitionedCache()

    @classmethod
    async def load_cache(cls, db: AsyncSession):
        """
        Pre-warm autocorrect synonym mappings from database.
        Loads all APPROVED words with a valid synonym_target by merging
        global approved synonyms (Master DB) and regional approved synonyms (Tenant DB).
        """
        info = getattr(db, "info", None)
        tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else (tenant_context.get() or "global")
        
        # 1. Fetch approved synonyms from Master DB
        master_synonyms = []
        try:
            if tenant_slug == "global":
                result = await db.execute(
                    select(DictionaryWord).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED,
                        DictionaryWord.synonym_target != None,
                        DictionaryWord.synonym_target != ""
                    )
                )
                master_synonyms = result.scalars().all()
            else:
                from app.db.session import MasterSessionLocal
                async with MasterSessionLocal() as master_db:
                    result = await master_db.execute(
                        select(DictionaryWord).where(
                            DictionaryWord.status == DictionaryStatus.APPROVED,
                            DictionaryWord.synonym_target != None,
                            DictionaryWord.synonym_target != ""
                        )
                    )
                    master_synonyms = result.scalars().all()
        except Exception as e:
            logger.warning(f"[AutoCorrectService] Failed to load global synonyms: {e}")

        # 2. Fetch approved synonyms from Tenant DB (if not global)
        tenant_synonyms = []
        if tenant_slug != "global":
            try:
                result = await db.execute(
                    select(DictionaryWord).where(
                        DictionaryWord.status == DictionaryStatus.APPROVED,
                        DictionaryWord.synonym_target != None,
                        DictionaryWord.synonym_target != ""
                    )
                )
                tenant_synonyms = result.scalars().all()
            except Exception as e:
                logger.warning(f"[AutoCorrectService] Failed to load tenant synonyms: {e}")

        # 3. Merge them. Tenant synonyms override master synonyms.
        mappings = {}
        for w in master_synonyms:
            if w.word and w.synonym_target:
                mappings[w.word.lower().strip()] = w.synonym_target.strip()
        for w in tenant_synonyms:
            if w.word and w.synonym_target:
                mappings[w.word.lower().strip()] = w.synonym_target.strip()

        cls._synonym_mappings[tenant_slug] = mappings
        cls._cache_loaded[tenant_slug] = True
        logger.info(f"[AutoCorrectService] Cache loaded for tenant '{tenant_slug}' with {len(mappings)} synonym mappings.")

    # Merged prepositions and common colloquial contractions
    MERGED_PREPOSITIONS = {
        "didekat": "di dekat",
        "disekitar": "di sekitar",
        "dipulau": "di pulau",
        "dilaut": "di laut",
        "diperairan": "di perairan",
        "disungai": "di sungai",
        "dipantai": "di pantai",
        "dihutan": "di hutan",
        "digunung": "di gunung",
        "dijalan": "di jalan",
        "diatas": "di atas",
        "dibawah": "di bawah",
        "didalam": "di dalam",
        "diluar": "di luar",
        "didermaga": "di dermaga",
        "dipelabuhan": "di pelabuhan",
        "diselat": "di selat",
        "diteluk": "di teluk",
        "dimuara": "di muara",
    }

    # Phonetic/colloquial vessel stems when followed by enclitics (-nya, -ku, -mu) or standalone
    COLLOQUIAL_STEM_MAP = {
        "pomponya": "pompongnya",
        "pompon": "pompong",
        "pompo": "pompong",
        "perahunya": "perahu",
        "kapalnya": "kapal",
        "pompongnya": "pompong",
        "speednya": "speedboat",
        "sampannya": "sampan",
        "ketintingnya": "ketinting",
    }

    # Standard Indonesian & SAR core vocabulary that should not be flagged as unknown jargon
    STANDARD_INDONESIAN_VOCAB = {
        # Pronouns & family/relations
        "saya", "aku", "kami", "kita", "dia", "mereka", "anda", "beliau", "ini", "itu",
        "kakak", "abang", "adik", "adek", "ayah", "bapak", "ibu", "emak", "anak", "suami",
        "istri", "paman", "bibi", "kakek", "nenek", "keluarga", "saudara", "teman", "rekan",
        "tetangga", "warga", "nelayan", "korban", "orang", "penumpang", "awak", "kru", "abk",
        "laki", "perempuan", "pria", "wanita", "dewasa", "balita", "lansia", "saksi", "mata",
        # Prepositions, conjunctions, auxiliaries
        "dan", "atau", "yang", "di", "ke", "dari", "pada", "dalam", "untuk", "dengan",
        "karena", "jika", "kalau", "bila", "saat", "ketika", "sejak", "sampai", "hingga",
        "sudah", "telah", "belum", "sedang", "masih", "akan", "bisa", "dapat", "tidak",
        "tak", "bukan", "ada", "tiada", "jadi", "terjadi", "mengalami", "melihat", "mohon",
        "tolong", "bantu", "bantuan", "lapor", "laporan", "info", "informasi", "sar",
        "dekat", "sekitar", "arah", "utara", "selatan", "timur", "barat", "tengah", "atas", "bawah",
        # Time & numbers
        "jam", "pukul", "wib", "wita", "wit", "pagi", "siang", "sore", "malam", "subuh",
        "dini", "hari", "kemarin", "tadi", "besok", "lusa", "menit", "detik", "lalu", "sekitar",
        "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh",
        "seorang", "berdua", "bertiga", "berempat", "berlima", "tahun", "umur", "usia",
        # Geography & maritime standard words
        "pulau", "laut", "perairan", "selat", "teluk", "tanjung", "pantai", "pelabuhan",
        "dermaga", "muara", "sungai", "danau", "waduk", "desa", "kelurahan", "kecamatan",
        "kabupaten", "kota", "gunung", "bukit", "hutan", "jalan", "jembatan", "lokasi",
        "titik", "koordinat", "lintang", "bujur", "derajat", "mil", "meter", "kilometer",
        "senoa", "jemaja", "subi", "midai", "serasan", "panjang", "sedanau", "natuna", "ranai",
        "bunguran", "tarempa", "anambas", "bintan", "batam", "karimun", "lingga", "tanjungpinang",
        # Standard SAR vessels & conditions
        "kapal", "perahu", "pompong", "speedboat", "sampan", "ketinting", "tongkang", "tugboat",
        "jukung", "pancung", "motor", "kayu", "karet", "mesin", "mati", "mogok", "rusak",
        "patah", "kemudi", "bocor", "tenggelam", "terbalik", "hanyut", "kandas", "terbakar",
        "kebakaran", "tabrakan", "hilang", "kontak", "selamat", "meninggal", "dunia", "tewas",
        "evakuasi", "pencarian", "ditemukan", "terombang", "ambing", "ombak", "angin", "cuaca",
        "hujan", "badai", "arus", "gelombang", "besar", "kencang", "tinggi", "warna", "putih",
        "biru", "merah", "kuning", "hijau", "hitam", "cokelat", "abu", "nama", "jenis",
        "nomor", "telepon", "hp", "wa", "alamat", "rumah", "pergi", "melaut", "memancing",
        "mancing", "jaring", "ikan", "pulang", "kembali", "dihubungi", "sinyal", "habis", "bbm",
        "minyak", "bensin", "solar", "baling", "as", "propeller", "jangkar", "tali",
    }

    @classmethod
    def normalize_colloquial_tokens(cls, message: str) -> str:
        """
        Normalize merged prepositions (e.g. 'didekat' -> 'di dekat') and
        known colloquial/morphological variants (e.g. 'pomponya' -> 'pompongnya')
        without altering unknown words.
        """
        if not message:
            return message

        result = message

        # 1. Normalize merged prepositions (case-insensitive word boundaries)
        prep_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in cls.MERGED_PREPOSITIONS.keys()) + r')\b',
            re.IGNORECASE
        )
        result = prep_pattern.sub(
            lambda m: cls.MERGED_PREPOSITIONS.get(m.group(1).lower(), m.group(0)),
            result
        )

        # 2. Normalize known colloquial vessel/enclitic tokens (e.g., 'pomponya' -> 'pompongnya')
        stem_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in cls.COLLOQUIAL_STEM_MAP.keys()) + r')\b',
            re.IGNORECASE
        )
        result = stem_pattern.sub(
            lambda m: cls.COLLOQUIAL_STEM_MAP.get(m.group(1).lower(), m.group(0)),
            result
        )

        return result

    @classmethod
    def clean_message(cls, message: str) -> str:
        """
        Replace known typos/slangs with their standard approved synonym targets.
        First normalizes merged prepositions and colloquial enclitics, then applies
        approved synonym mappings from the database.
        """
        if not message:
            return message

        cleaned = cls.normalize_colloquial_tokens(message)

        if not cls._synonym_mappings:
            if cleaned != message:
                logger.info(f"[AutoCorrectService] Normalized message: '{message}' -> '{cleaned}'")
            return cleaned

        # Extract sorted keys by length descending to match longer phrases first
        sorted_keys = sorted(cls._synonym_mappings.keys(), key=len, reverse=True)
        if not sorted_keys:
            return cleaned

        # Compile regex with word boundaries, also allowing optional possessive suffixes (-nya, -ku, -mu)
        pattern = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in sorted_keys) + r')(nya|ku|mu)?\b',
            re.IGNORECASE
        )

        def replace_match(match):
            matched_base = match.group(1).lower().strip()
            suffix = match.group(2) or ""
            target = cls._synonym_mappings.get(matched_base)
            if not target:
                return match.group(0)
            # Avoid doubling suffix if target already ends with it
            if suffix and not target.lower().endswith(suffix.lower()):
                return f"{target}{suffix}"
            return target

        cleaned = pattern.sub(replace_match, cleaned)

        if cleaned != message:
            logger.info(f"[AutoCorrectService] Cleaned message: '{message}' -> '{cleaned}'")

        return cleaned

    @classmethod
    async def detect_and_log_unknown_terms(
        cls,
        message: str,
        db: AsyncSession,
        user_id: str = "system"
    ) -> list[str]:
        """
        Zero-Hallucination Unknown Word Detector & Logger:
        Scans the raw reporter message for unrecognized terms or colloquial typos
        that are not yet verified in DictionaryWord.
        - Preserves original words in the message if unknown.
        - Records unknown words as PENDING in DictionaryWord for operator review.
        """
        if not message or not db:
            return []

        tokens = re.findall(r'\b[a-zA-Z]{3,25}\b', message)
        if not tokens:
            return []

        candidate_unknowns = []
        seen = set()

        for raw_token in tokens:
            token_lower = raw_token.lower()
            if token_lower in seen:
                continue
            seen.add(token_lower)

            # Strip possessive/enclitic suffix to check stem
            stem = re.sub(r'(nya|ku|mu|lah|kah)$', '', token_lower)
            if len(stem) < 3:
                stem = token_lower

            # Check if token is a colloquial/typo form that should be flagged if not in DB
            is_colloquial_variant = (
                token_lower in ("pomponya", "pompon", "pompo")
                or token_lower in cls.MERGED_PREPOSITIONS
            )

            if not is_colloquial_variant:
                if token_lower in cls.STANDARD_INDONESIAN_VOCAB or stem in cls.STANDARD_INDONESIAN_VOCAB:
                    continue
                if cls._synonym_mappings and (token_lower in cls._synonym_mappings or stem in cls._synonym_mappings):
                    continue

            candidate_unknowns.append(raw_token)

        if not candidate_unknowns:
            return []

        logged_unknowns = []
        try:
            from sqlalchemy import func as sa_func
            async with db.begin_nested():
                for raw_token in candidate_unknowns:
                    token_lower = raw_token.lower()
                    stem = re.sub(r'(nya|ku|mu|lah|kah)$', '', token_lower)
                    if len(stem) < 3:
                        stem = token_lower

                    # Check if word or stem already exists in DictionaryWord
                    result = await db.execute(
                        select(DictionaryWord).where(
                            sa_func.lower(DictionaryWord.word).in_([token_lower, stem])
                        )
                    )
                    scalars_obj = result.scalars() if result else None
                    existing_rows = scalars_obj.all() if scalars_obj else []
                    if not isinstance(existing_rows, list):
                        existing_rows = []

                    if existing_rows:
                        # If it exists as PENDING, increment frequency and report it as pending
                        for row in existing_rows:
                            if getattr(row, "status", None) == DictionaryStatus.PENDING:
                                row.frequency = (row.frequency or 1) + 1
                                logged_unknowns.append(row.word)
                        continue

                    # Word is genuinely not in DictionaryWord -> record as PENDING for operator correction
                    suggested_synonym = cls.COLLOQUIAL_STEM_MAP.get(token_lower)
                    new_word = DictionaryWord(
                        word=token_lower,
                        definition=None,
                        synonym_target=suggested_synonym,
                        is_typo_or_slang=True,
                        category="SLANG_DIALEK",
                        context_example=f"Ditemukan dalam pesan pelapor: '{message[:200]}'",
                        source_message=message[:500],
                        source_user=user_id,
                        status=DictionaryStatus.PENDING,
                        frequency=1,
                        word_type="JARGON",
                        is_auto_detected=True,
                    )
                    db.add(new_word)
                    logged_unknowns.append(token_lower)

                await db.commit()
        except Exception as e:
            logger.warning(f"[AutoCorrectService] Unknown word logging skipped: {e}")

        return logged_unknowns

# Singleton instance
autocorrect_service = AutoCorrectService()

