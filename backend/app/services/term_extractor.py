"""
Term Extractor Service
======================
Detects and saves domain-specific SAR terms (abbreviations, jargon) from
reporter messages using regex pattern matching, then matches them against
a built-in SAR glossary.

Detection Flow:
  1. Regex → capture uppercase abbreviations (2-8 chars) from message
  2. Match against SAR_GLOSSARY → APPROVED with known definition
  3. Unrecognized terms → PENDING for admin review
  4. Both saved to dictionary_words table for future LLM prompt injection
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# =====================================================================
# Built-in SAR Glossary
# Kata yang ada di sini akan langsung di-APPROVED saat ditemukan
# =====================================================================

SAR_GLOSSARY: dict[str, str] = {
    "KMM": "Kondisi Membahayakan Manusia",
    "KPK": "Kecelakaan Penanganan Khusus",
    "SAR": "Search and Rescue",
    "SMC": "SAR Mission Coordinator",
    "OSC": "On Scene Coordinator",
    "SRU": "Search and Rescue Unit",
    "LCR": "Landing Craft Rubber",
    "RIB": "Rigid Inflatable Boat",
    "RHIB": "Rigid Hull Inflatable Boat",
    "KM": "Kapal Motor",
    "KMN": "Kapal Motor Nelayan",
    "TB": "Tug Boat",
    "MV": "Motor Vessel",
    "MT": "Motor Tanker"
}

# Kamus Kategori Standar SAR (Titik mula NLP)
SEED_CATEGORIES = {
    "VESSEL_PREFIX": ["KM", "KMN", "KRI", "TB", "RIB", "RHIB", "MV", "MT", "LCT", "TK", "BG"],
    "VESSEL_TYPE": [
        "kapal", "pompong", "perahu", "speedboat", "tongkang", "tugboat", "tanker", "yacht",
        "kelong", "bagan", "sampan", "ketinting", "jukung", "pancung", "boat pancung", "perahu karet", "speed lidah", "kapal kayu"
    ],
    "VICTIM_STATUS_S": ["selamat", "dievakuasi", "terselamatkan", "sehat", "hidup", "aman"],
    "VICTIM_STATUS_MD": ["meninggal", "tewas", "md", "mati", "jasad", "jenazah", "meninggal dunia"],
    "VICTIM_STATUS_DP": ["hilang", "dp", "belum ditemukan", "dalam pencarian", "masih dalam pencarian", "tenggelam", "hanyut", "dicari", "terbawa arus"],
    "LOCATION_TYPE": ["perairan", "laut", "selat", "teluk", "tanjung", "pantai", "pelabuhan", "dermaga", "muara", "sungai", "danau", "waduk", "kolam", "pulau", "desa", "kelurahan", "kecamatan", "gunung", "bukit", "hutan", "jalan", "jembatan", "tebing", "sekitar"],
    "VICTIM_ROLE": ["nelayan", "penumpang", "abk", "anak", "warga", "awak", "kru", "wisatawan", "pekerja", "pelajar", "mahasiswa", "pendaki", "korban"],
    "VESSEL_COLOR": ["biru", "merah", "putih", "hitam", "kuning", "hijau", "oranye", "jingga", "silver", "abu-abu", "cokelat"],
    "VESSEL_COLOR_PREFIX": ["warna", "warne"],
    "LOCATION_PREFIX": ["di", "pada", "dekat", "sekitar"],
    "INCIDENT_KEYWORD": ["bertabrakan", "tabrakan", "tenggelam", "hilang", "hanyut", "kandas", "terbakar", "mengalami", "mati"],
    "QUANTIFIER": ["berdua", "bertiga", "berempat", "berlima", "berenam", "bertujuh", "berdelapan", "bersembilan", "bersepuluh"]
}

# =====================================================================
# Regex Patterns
# =====================================================================

# Pola 1: Singkatan uppercase 2-8 karakter (opsional titik di antara huruf: G.P.S)
ABBREV_PATTERN = re.compile(
    r'\b([A-Z]{2,8}(?:\.[A-Z])*)\b'
)

# Pola 2: Kata Indonesia diikuti singkatan dalam kurung: "Lintang Utara (LU)"
DEFINITION_PATTERN = re.compile(
    r'([A-Za-z][a-zA-Z\s]{3,40})\s*[(/]([A-Z]{2,8})[)/]'
)

# Pola 3: Singkatan diikuti definisi setelah tanda sama dengan/titik dua
EQUATION_PATTERN = re.compile(
    r'\b([A-Z]{2,8})\s*[=:]\s*([A-Za-z][a-zA-Z\s]{3,60})'
)

# Stop words — singkatan umum yang TIDAK ingin kita simpan
STOP_ABBREVS = {
    "OK", "OKE", "YA", "NO", "ID", "DAN", "ADA", "INI", "ITU",
    "DI", "KE", "DP", "MD", "OR", "AN", "IS", "AI", "API", "URL",
    "HTTP", "HTTPS", "JSON", "HTML", "PDF", "KM", "CM", "MM",
    "THE", "AND", "FOR", "NOT", "ARE", "WAS", "HAS", "HAD",
}


# =====================================================================
# Core Functions
# =====================================================================

def extract_terms(message: str) -> list[dict]:
    """
    Extract SAR-relevant terms and abbreviations from a message.

    Returns a list of dicts:
      [{"word": "LU", "definition": "Lintang Utara — ...", "context": "...", "word_type": "ABBREVIATION"}]

    - Words found in SAR_GLOSSARY → definition filled, will be saved as APPROVED
    - Unknown uppercase words → definition=None, will be saved as PENDING
    """
    found: dict[str, dict] = {}  # word → term dict (dedup by word)

    # --- Pattern 1: Standalone uppercase abbreviations ---
    for match in ABBREV_PATTERN.finditer(message):
        abbrev = match.group(1).replace(".", "")  # Normalize G.P.S → GPS
        if abbrev in STOP_ABBREVS:
            continue
        if len(abbrev) < 2 or len(abbrev) > 8:
            continue
        if abbrev not in found:
            definition = SAR_GLOSSARY.get(abbrev)
            found[abbrev] = {
                "word": abbrev,
                "definition": definition,
                "context": f"Ditemukan dalam pesan: ...{_snippet(message, match.start())}...",
                "word_type": "ABBREVIATION",
            }

    # --- Pattern 2: "Full Name (ABBREV)" format ---
    for match in DEFINITION_PATTERN.finditer(message):
        full_name = match.group(1).strip()
        abbrev = match.group(2).strip()
        if abbrev in STOP_ABBREVS:
            continue
        # This gives us a strong hint — pelapor defined it themselves
        inferred_def = f"{full_name} — istilah dari pelapor"
        if abbrev not in found or found[abbrev]["definition"] is None:
            found[abbrev] = {
                "word": abbrev,
                "definition": SAR_GLOSSARY.get(abbrev, inferred_def),
                "context": f"Pelapor menyebutkan: '{match.group(0)}'",
                "word_type": "ABBREVIATION",
            }

    # --- Pattern 3: "ABBREV = definition" or "ABBREV: definition" format ---
    for match in EQUATION_PATTERN.finditer(message):
        abbrev = match.group(1).strip()
        definition_text = match.group(2).strip()
        if abbrev in STOP_ABBREVS:
            continue
        if abbrev not in found or found[abbrev]["definition"] is None:
            found[abbrev] = {
                "word": abbrev,
                "definition": SAR_GLOSSARY.get(abbrev, f"{definition_text} — istilah dari pelapor"),
                "context": f"Pelapor mendefinisikan: '{match.group(0)}'",
                "word_type": "ABBREVIATION",
            }

    return list(found.values())


async def resolve_and_save_terms(
    terms: list[dict],
    message: str,
    user_id: str,
    db,
) -> int:
    """
    Save extracted terms to the dictionary_words table.

    - Terms matching SAR_GLOSSARY → saved/updated as APPROVED
    - Unknown terms → saved as PENDING (for admin review)
    - If word already exists → increment frequency counter only

    Returns the count of newly inserted words.
    """
    if not terms:
        return 0

    saved_count = 0
    try:
        from sqlalchemy.future import select
        from sqlalchemy import func as sa_func
        from app.models.knowledge_models import DictionaryWord, DictionaryStatus

        async with db.begin_nested():
            for term in terms:
                word_text = term.get("word", "").strip()
                if not word_text or len(word_text) < 2 or len(word_text) > 100:
                    continue

                # Check if word already exists (case-insensitive)
                result = await db.execute(
                    select(DictionaryWord).where(
                        sa_func.upper(DictionaryWord.word) == word_text.upper()
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Increment frequency
                    existing.frequency = (existing.frequency or 1) + 1
                    # If we now have a definition but existing doesn't, update it
                    if term.get("definition") and not existing.definition:
                        existing.definition = term["definition"]
                        existing.status = DictionaryStatus.APPROVED
                else:
                    # Auto-approve if term has a glossary or inferred definition (e.g. from equations or parentheses)
                    has_def = term.get("definition") is not None
                    new_status = DictionaryStatus.APPROVED if has_def else DictionaryStatus.PENDING
     
                    new_word = DictionaryWord(
                        word=word_text,
                        definition=term.get("definition"),
                        context_example=term.get("context", ""),
                        source_message=message[:500],
                        source_user=user_id,
                        status=new_status,
                        frequency=1,
                        word_type=term.get("word_type", "ABBREVIATION"),
                        is_auto_detected=True,
                    )
                    db.add(new_word)
                    saved_count += 1

            await db.commit()
        if saved_count:
            logger.info(f"[TermExtractor] Saved {saved_count} new term(s) from message by {user_id}")

    except Exception as e:
        logger.warning(f"[TermExtractor] Note: Term saving bypassed: {e}")

    return saved_count


async def seed_sar_glossary(db) -> dict:
    """
    Seed all SAR_GLOSSARY and SEED_CATEGORIES terms into the dictionary_words table as APPROVED.
    Used by the admin 'Seed Glossary SAR' button.
    Skips words that already exist.

    Returns {"inserted": N, "skipped": N}
    """
    inserted = 0
    skipped = 0

    try:
        from sqlalchemy.future import select
        from sqlalchemy import func as sa_func
        from app.models.knowledge_models import DictionaryWord, DictionaryStatus

        # 1. Seed Abbreviations
        for abbrev, definition in SAR_GLOSSARY.items():
            result = await db.execute(
                select(DictionaryWord).where(
                    sa_func.upper(DictionaryWord.word) == abbrev.upper()
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                if not existing.definition:
                    existing.definition = definition
                    existing.status = DictionaryStatus.APPROVED
                skipped += 1
            else:
                new_word = DictionaryWord(
                    word=abbrev,
                    definition=definition,
                    context_example=f"Istilah baku SAR Indonesia",
                    source_message="Seed dari glossary bawaan SARBot",
                    source_user="system",
                    status=DictionaryStatus.APPROVED,
                    frequency=0,
                    word_type="ABBREVIATION",
                    ner_type="Singkatan",
                    is_auto_detected=False,
                )
                db.add(new_word)
                inserted += 1

        # 2. Seed Categories
        for category, words in SEED_CATEGORIES.items():
            for word_text in words:
                result = await db.execute(
                    select(DictionaryWord).where(
                        sa_func.upper(DictionaryWord.word) == word_text.upper()
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    skipped += 1
                else:
                    new_word = DictionaryWord(
                        word=word_text,
                        definition=f"Kata dasar kategori {category}",
                        context_example="Kosa kata baku",
                        source_message="Seed dari kategori SARBot",
                        source_user="system",
                        status=DictionaryStatus.APPROVED,
                        frequency=0,
                        word_type=category,
                        ner_type=category,
                        is_auto_detected=False,
                    )
                    db.add(new_word)
                    inserted += 1

        # 3. Seed Regional Maritime Slang & Dialects
        SLANG_MAPPINGS = {
            "karam": {"synonym": "tenggelam", "def": "Kondisi kapal atau perahu masuk ke dalam air"},
            "enjin": {"synonym": "mesin", "def": "Mesin penggerak kapal atau kendaraan"},
            "mati enjin": {"synonym": "mati mesin", "def": "Kerusakan motor penggerak perahu di laut"},
            "hanyot": {"synonym": "hanyut", "def": "Terbawa arus air atau gelombang"},
            "pakcik": {"synonym": "paman", "def": "Paman atau kerabat laki-laki"},
            "makcik": {"synonym": "bibi", "def": "Bibi atau kerabat perempuan"},
            "ketinting": {"synonym": "perahu ketinting", "def": "Perahu kayu bermesin tempel poros panjang"},
            "pompong": {"synonym": "kapal pompong", "def": "Perahu motor kayu tradisional nelayan pesisir"},
            "kelong": {"synonym": "bagan kelong", "def": "Bangunan apung atau pancang penangkap ikan di laut"},
            "unjam": {"synonym": "rumpon unjam", "def": "Rumpon atau karang buatan tempat berkumpulnya ikan"},
            "tenggelem": {"synonym": "tenggelam", "def": "Bentuk typo atau cakapan dari tenggelam"},
        }
        for slang, meta in SLANG_MAPPINGS.items():
            result = await db.execute(
                select(DictionaryWord).where(
                    sa_func.upper(DictionaryWord.word) == slang.upper()
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                skipped += 1
            else:
                new_word = DictionaryWord(
                    word=slang,
                    definition=meta["def"],
                    synonym_target=meta["synonym"],
                    is_typo_or_slang=True,
                    category="SLANG_DIALEK",
                    context_example="Dialek lokal pesisir maritim",
                    source_message="Seed dialek maritim SARBot",
                    source_user="system",
                    status=DictionaryStatus.APPROVED,
                    frequency=0,
                    word_type="SLANG",
                    ner_type="SLANG_DIALEK",
                    is_auto_detected=False,
                )
                db.add(new_word)
                inserted += 1

        await db.commit()
        logger.info(f"[TermExtractor] Glossary seed: {inserted} inserted, {skipped} skipped")

    except Exception as e:
        logger.error(f"[TermExtractor] Error seeding glossary: {e}")
        try:
            await db.rollback()
        except Exception:
            pass

    return {"inserted": inserted, "skipped": skipped}


# =====================================================================
# Helpers
# =====================================================================

def _snippet(text: str, pos: int, radius: int = 20) -> str:
    """Extract a short snippet around a position in text."""
    start = max(0, pos - radius)
    end = min(len(text), pos + radius)
    return text[start:end].replace("\n", " ")
