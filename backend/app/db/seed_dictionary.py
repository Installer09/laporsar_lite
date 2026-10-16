import asyncio
import logging
from sqlalchemy.future import select
from app.models.knowledge_models import DictionaryWord, DictionaryStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default BASARNAS grammatical and structural terms (no duplicates)
DEFAULT_WORDS = [
    # ── 1. QUANTIFIER (Kata Bilangan) ──
    {"word": "satu", "ner_type": "QUANTIFIER", "ner_target": "1"},
    {"word": "seorang", "ner_type": "QUANTIFIER", "ner_target": "1"},
    {"word": "seorang diri", "ner_type": "QUANTIFIER", "ner_target": "1"},
    {"word": "dua", "ner_type": "QUANTIFIER", "ner_target": "2"},
    {"word": "berdua", "ner_type": "QUANTIFIER", "ner_target": "2"},
    {"word": "tiga", "ner_type": "QUANTIFIER", "ner_target": "3"},
    {"word": "bertiga", "ner_type": "QUANTIFIER", "ner_target": "3"},
    {"word": "empat", "ner_type": "QUANTIFIER", "ner_target": "4"},
    {"word": "berempat", "ner_type": "QUANTIFIER", "ner_target": "4"},
    {"word": "lima", "ner_type": "QUANTIFIER", "ner_target": "5"},
    {"word": "berlima", "ner_type": "QUANTIFIER", "ner_target": "5"},
    {"word": "enam", "ner_type": "QUANTIFIER", "ner_target": "6"},
    {"word": "berenam", "ner_type": "QUANTIFIER", "ner_target": "6"},
    {"word": "tujuh", "ner_type": "QUANTIFIER", "ner_target": "7"},
    {"word": "bertujuh", "ner_type": "QUANTIFIER", "ner_target": "7"},
    {"word": "delapan", "ner_type": "QUANTIFIER", "ner_target": "8"},
    {"word": "berdelapan", "ner_type": "QUANTIFIER", "ner_target": "8"},
    {"word": "sembilan", "ner_type": "QUANTIFIER", "ner_target": "9"},
    {"word": "bersembilan", "ner_type": "QUANTIFIER", "ner_target": "9"},
    {"word": "sepuluh", "ner_type": "QUANTIFIER", "ner_target": "10"},
    {"word": "bersepuluh", "ner_type": "QUANTIFIER", "ner_target": "10"},
    {"word": "sebelas", "ner_type": "QUANTIFIER", "ner_target": "11"},
    {"word": "dua belas", "ner_type": "QUANTIFIER", "ner_target": "12"},
    {"word": "abk", "ner_type": "QUANTIFIER", "ner_target": "1"},
    {"word": "penumpang", "ner_type": "QUANTIFIER", "ner_target": "1"},
    {"word": "kru", "ner_type": "QUANTIFIER", "ner_target": "1"},
    {"word": "awak", "ner_type": "QUANTIFIER", "ner_target": "1"},
    {"word": "korban", "ner_type": "QUANTIFIER", "ner_target": "1"},

    # ── 2. TIME_MARKER (Penanda Waktu) ──
    {"word": "kemarin malam", "ner_type": "TIME_MARKER", "ner_target": "kemarin malam"},
    {"word": "kemarin sore", "ner_type": "TIME_MARKER", "ner_target": "kemarin sore"},
    {"word": "kemarin pagi", "ner_type": "TIME_MARKER", "ner_target": "kemarin pagi"},
    {"word": "kemarin siang", "ner_type": "TIME_MARKER", "ner_target": "kemarin siang"},
    {"word": "tadi malam", "ner_type": "TIME_MARKER", "ner_target": "tadi malam"},
    {"word": "tadi pagi", "ner_type": "TIME_MARKER", "ner_target": "tadi pagi"},
    {"word": "tadi sore", "ner_type": "TIME_MARKER", "ner_target": "tadi sore"},
    {"word": "tadi siang", "ner_type": "TIME_MARKER", "ner_target": "tadi siang"},
    {"word": "malam tadi", "ner_type": "TIME_MARKER", "ner_target": "malam tadi"},
    {"word": "siang tadi", "ner_type": "TIME_MARKER", "ner_target": "siang tadi"},
    {"word": "pagi tadi", "ner_type": "TIME_MARKER", "ner_target": "pagi tadi"},
    {"word": "dini hari tadi", "ner_type": "TIME_MARKER", "ner_target": "dini hari tadi"},
    {"word": "subuh tadi", "ner_type": "TIME_MARKER", "ner_target": "subuh tadi"},
    {"word": "semalam", "ner_type": "TIME_MARKER", "ner_target": "semalam"},
    {"word": "hari ini", "ner_type": "TIME_MARKER", "ner_target": "hari ini"},
    {"word": "pagi ini", "ner_type": "TIME_MARKER", "ner_target": "pagi ini"},
    {"word": "sore ini", "ner_type": "TIME_MARKER", "ner_target": "sore ini"},
    {"word": "kemarin", "ner_type": "TIME_MARKER", "ner_target": "kemarin"},

    # ── 3. VICTIM_STATUS (Sinonim Kondisi Korban) ──
    {"word": "selamat", "ner_type": "VICTIM_STATUS_S", "ner_target": "selamat"},
    {"word": "aman", "ner_type": "VICTIM_STATUS_S", "ner_target": "selamat"},
    {"word": "dievakuasi", "ner_type": "VICTIM_STATUS_S", "ner_target": "selamat"},
    {"word": "sehat", "ner_type": "VICTIM_STATUS_S", "ner_target": "selamat"},
    {"word": "hidup", "ner_type": "VICTIM_STATUS_S", "ner_target": "selamat"},
    
    {"word": "meninggal", "ner_type": "VICTIM_STATUS_MD", "ner_target": "meninggal"},
    {"word": "meninggal dunia", "ner_type": "VICTIM_STATUS_MD", "ner_target": "meninggal"},
    {"word": "tewas", "ner_type": "VICTIM_STATUS_MD", "ner_target": "meninggal"},
    {"word": "mati", "ner_type": "VICTIM_STATUS_MD", "ner_target": "meninggal"},
    {"word": "md", "ner_type": "VICTIM_STATUS_MD", "ner_target": "meninggal"},
    {"word": "jasad", "ner_type": "VICTIM_STATUS_MD", "ner_target": "meninggal"},
    {"word": "jenazah", "ner_type": "VICTIM_STATUS_MD", "ner_target": "meninggal"},
    
    {"word": "belum ditemukan", "ner_type": "VICTIM_STATUS_DP", "ner_target": "hilang"},
    {"word": "pencarian", "ner_type": "VICTIM_STATUS_DP", "ner_target": "hilang"},
    {"word": "dalam pencarian", "ner_type": "VICTIM_STATUS_DP", "ner_target": "hilang"},
    {"word": "dicari", "ner_type": "VICTIM_STATUS_DP", "ner_target": "hilang"},
    {"word": "dp", "ner_type": "VICTIM_STATUS_DP", "ner_target": "hilang"},
    {"word": "terbawa arus", "ner_type": "VICTIM_STATUS_DP", "ner_target": "hilang"},

    # ── 4. VICTIM_ROLE (Peran Korban) ──
    {"word": "nelayan", "ner_type": "VICTIM_ROLE", "ner_target": "Nelayan"},
    {"word": "warga", "ner_type": "VICTIM_ROLE", "ner_target": "Warga"},
    {"word": "wisatawan", "ner_type": "VICTIM_ROLE", "ner_target": "Wisatawan"},
    {"word": "pekerja", "ner_type": "VICTIM_ROLE", "ner_target": "Pekerja"},
    {"word": "pelajar", "ner_type": "VICTIM_ROLE", "ner_target": "Pelajar"},
    {"word": "mahasiswa", "ner_type": "VICTIM_ROLE", "ner_target": "Mahasiswa"},
    {"word": "pendaki", "ner_type": "VICTIM_ROLE", "ner_target": "Pendaki"},

    # ── 5. VESSEL_PREFIX (Prefiks Kapal) ──
    {"word": "KM", "ner_type": "VESSEL_PREFIX", "ner_target": "KM"},
    {"word": "KMN", "ner_type": "VESSEL_PREFIX", "ner_target": "KMN"},
    {"word": "KRI", "ner_type": "VESSEL_PREFIX", "ner_target": "KRI"},
    {"word": "TB", "ner_type": "VESSEL_PREFIX", "ner_target": "TB"},
    {"word": "RIB", "ner_type": "VESSEL_PREFIX", "ner_target": "RIB"},
    {"word": "RHIB", "ner_type": "VESSEL_PREFIX", "ner_target": "RHIB"},
    {"word": "MV", "ner_type": "VESSEL_PREFIX", "ner_target": "MV"},
    {"word": "MT", "ner_type": "VESSEL_PREFIX", "ner_target": "MT"},
    {"word": "LCT", "ner_type": "VESSEL_PREFIX", "ner_target": "LCT"},
    {"word": "TK", "ner_type": "VESSEL_PREFIX", "ner_target": "TK"},
    {"word": "BG", "ner_type": "VESSEL_PREFIX", "ner_target": "BG"},

    # ── 6. LOCATION_TYPE (Tipe Tempat) ──
    {"word": "perairan", "ner_type": "LOCATION_TYPE", "ner_target": "perairan"},
    {"word": "laut", "ner_type": "LOCATION_TYPE", "ner_target": "laut"},
    {"word": "selat", "ner_type": "LOCATION_TYPE", "ner_target": "selat"},
    {"word": "teluk", "ner_type": "LOCATION_TYPE", "ner_target": "teluk"},
    {"word": "tanjung", "ner_type": "LOCATION_TYPE", "ner_target": "tanjung"},
    {"word": "pantai", "ner_type": "LOCATION_TYPE", "ner_target": "pantai"},
    {"word": "pelabuhan", "ner_type": "LOCATION_TYPE", "ner_target": "pelabuhan"},
    {"word": "dermaga", "ner_type": "LOCATION_TYPE", "ner_target": "dermaga"},
    {"word": "muara", "ner_type": "LOCATION_TYPE", "ner_target": "muara"},
    {"word": "sungai", "ner_type": "LOCATION_TYPE", "ner_target": "sungai"},
    {"word": "danau", "ner_type": "LOCATION_TYPE", "ner_target": "danau"},
    {"word": "waduk", "ner_type": "LOCATION_TYPE", "ner_target": "waduk"},
    {"word": "kolam", "ner_type": "LOCATION_TYPE", "ner_target": "kolam"},
    {"word": "pulau", "ner_type": "LOCATION_TYPE", "ner_target": "pulau"},
    {"word": "desa", "ner_type": "LOCATION_TYPE", "ner_target": "desa"},
    {"word": "kelurahan", "ner_type": "LOCATION_TYPE", "ner_target": "kelurahan"},
    {"word": "kecamatan", "ner_type": "LOCATION_TYPE", "ner_target": "kecamatan"},
    {"word": "gunung", "ner_type": "LOCATION_TYPE", "ner_target": "gunung"},
    {"word": "bukit", "ner_type": "LOCATION_TYPE", "ner_target": "bukit"},
    {"word": "hutan", "ner_type": "LOCATION_TYPE", "ner_target": "hutan"},
    {"word": "jalan", "ner_type": "LOCATION_TYPE", "ner_target": "jalan"},
    {"word": "jembatan", "ner_type": "LOCATION_TYPE", "ner_target": "jembatan"},
    {"word": "tebing", "ner_type": "LOCATION_TYPE", "ner_target": "tebing"},
    {"word": "sekitar", "ner_type": "LOCATION_TYPE", "ner_target": "sekitar"},

    # ── 7. INCIDENT_PROBLEM (Masalah Kejadian) ──
    {"word": "mati mesin", "ner_type": "INCIDENT_PROBLEM", "ner_target": "MATI MESIN"},
    {"word": "tenggelam", "ner_type": "INCIDENT_PROBLEM", "ner_target": "TENGGELAM"},
    {"word": "terbalik", "ner_type": "INCIDENT_PROBLEM", "ner_target": "TERBALIK"},
    {"word": "hanyut", "ner_type": "INCIDENT_PROBLEM", "ner_target": "HANYUT"},
    {"word": "kandas", "ner_type": "INCIDENT_PROBLEM", "ner_target": "KANDAS"},
    {"word": "terbakar", "ner_type": "INCIDENT_PROBLEM", "ner_target": "TERBAKAR"},
    {"word": "kebakaran", "ner_type": "INCIDENT_PROBLEM", "ner_target": "KEBAKARAN"},
    {"word": "tabrakan", "ner_type": "INCIDENT_PROBLEM", "ner_target": "TABRAKAN"},
    {"word": "hilang kontak", "ner_type": "INCIDENT_PROBLEM", "ner_target": "HILANG KONTAK"},
    {"word": "lost contact", "ner_type": "INCIDENT_PROBLEM", "ner_target": "LOST CONTACT"},
    {"word": "belum kembali", "ner_type": "INCIDENT_PROBLEM", "ner_target": "BELUM KEMBALI"},
    {"word": "belum pulang", "ner_type": "INCIDENT_PROBLEM", "ner_target": "BELUM PULANG"},
    {"word": "tidak bisa dihubungi", "ner_type": "INCIDENT_PROBLEM", "ner_target": "TIDAK BISA DIHUBUNGI"},
    {"word": "terjebak", "ner_type": "INCIDENT_PROBLEM", "ner_target": "TERJEBAK"},
    {"word": "terjepit", "ner_type": "INCIDENT_PROBLEM", "ner_target": "TERJEPIT"},
    {"word": "hilang", "ner_type": "INCIDENT_PROBLEM", "ner_target": "HILANG"},
    
    # ── 8. ISLAND (Daftar Pulau untuk Normalisasi Lokasi) ──
    {"word": "senoa", "ner_type": "ISLAND", "ner_target": "SENOA"},
    {"word": "jemaja", "ner_type": "ISLAND", "ner_target": "JEMAJA"},
    {"word": "subi", "ner_type": "ISLAND", "ner_target": "SUBI"},
    {"word": "midai", "ner_type": "ISLAND", "ner_target": "MIDAI"},
    {"word": "serasan", "ner_type": "ISLAND", "ner_target": "SERASAN"},
    {"word": "panjang", "ner_type": "ISLAND", "ner_target": "PANJANG"},
    {"word": "sedanau", "ner_type": "ISLAND", "ner_target": "SEDANAU"},
    {"word": "bunguran", "ner_type": "ISLAND", "ner_target": "BUNGURAN"},
    {"word": "laut", "ner_type": "ISLAND", "ner_target": "LAUT"},
    {"word": "tiga", "ner_type": "ISLAND", "ner_target": "TIGA"},

    # ── 9. VESSEL_TYPE (Jenis Sarana Air / Kapal) ──
    {"word": "pompong", "ner_type": "VESSEL_TYPE", "ner_target": "Pompong", "category": "SARANA_ALUT", "definition": "Perahu motor kayu tradisional nelayan"},
    {"word": "kapal", "ner_type": "VESSEL_TYPE", "ner_target": "Kapal", "category": "SARANA_ALUT", "definition": "Sarana angkutan air / kapal laut"},
    {"word": "perahu", "ner_type": "VESSEL_TYPE", "ner_target": "Perahu", "category": "SARANA_ALUT", "definition": "Perahu tradisional atau nelayan"},
    {"word": "speedboat", "ner_type": "VESSEL_TYPE", "ner_target": "Speedboat", "category": "SARANA_ALUT", "definition": "Perahu cepat bermesin tempel"},
    {"word": "sampan", "ner_type": "VESSEL_TYPE", "ner_target": "Sampan", "category": "SARANA_ALUT", "definition": "Perahu kayu kecil dayung/mesin"},
    {"word": "ketinting", "ner_type": "VESSEL_TYPE", "ner_target": "Ketinting", "category": "SARANA_ALUT", "definition": "Perahu bermesin tempel poros panjang"},
    {"word": "tongkang", "ner_type": "VESSEL_TYPE", "ner_target": "Tongkang", "category": "SARANA_ALUT", "definition": "Kapal tongkang pengangkut muatan"},
    {"word": "tugboat", "ner_type": "VESSEL_TYPE", "ner_target": "Tugboat", "category": "SARANA_ALUT", "definition": "Kapal tunda penarik tongkang"},
    {"word": "jukung", "ner_type": "VESSEL_TYPE", "ner_target": "Jukung", "category": "SARANA_ALUT", "definition": "Perahu bercadik tradisional"},
    {"word": "pancung", "ner_type": "VESSEL_TYPE", "ner_target": "Boat Pancung", "category": "SARANA_ALUT", "definition": "Perahu motor cepat antar pulau"},

    # ── 10. REPORTER_RELATION (Hubungan Pelapor dan Korban) ──
    {"word": "kakak", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Kakak)"},
    {"word": "abang", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Kakak)"},
    {"word": "adik", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Adik)"},
    {"word": "ayah", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Ayah)"},
    {"word": "bapak", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Ayah)"},
    {"word": "ibu", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Ibu)"},
    {"word": "anak", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Anak)"},
    {"word": "suami", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Suami)"},
    {"word": "istri", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Istri)"},
    {"word": "paman", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Paman)"},
    {"word": "bibi", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban (Bibi)"},
    {"word": "keluarga", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban"},
    {"word": "saudara", "ner_type": "REPORTER_RELATION", "ner_target": "Keluarga Korban"},
    {"word": "teman", "ner_type": "REPORTER_RELATION", "ner_target": "Rekan Korban"},
    {"word": "rekan", "ner_type": "REPORTER_RELATION", "ner_target": "Rekan Korban"},
    {"word": "tetangga", "ner_type": "REPORTER_RELATION", "ner_target": "Tetangga / Warga"},

    # ── 11. SLANG_DIALEK (Variasi Lisan / Typo Umum) ──
    {"word": "pomponya", "ner_type": "VESSEL_TYPE", "ner_target": "Pompong", "synonym_target": "pompongnya", "is_typo_or_slang": True, "category": "SLANG_DIALEK", "definition": "Bentuk lisan/typo dari pompongnya (kapal pompong)"},
    {"word": "pompon", "ner_type": "VESSEL_TYPE", "ner_target": "Pompong", "synonym_target": "pompong", "is_typo_or_slang": True, "category": "SLANG_DIALEK", "definition": "Bentuk lisan/typo dari pompong"},
    {"word": "didekat", "ner_type": "LOCATION_PREFIX", "ner_target": "di dekat", "synonym_target": "di dekat", "is_typo_or_slang": True, "category": "SLANG_DIALEK", "definition": "Penulisan gabung dari preposisi di dekat"},
    {"word": "disekitar", "ner_type": "LOCATION_PREFIX", "ner_target": "di sekitar", "synonym_target": "di sekitar", "is_typo_or_slang": True, "category": "SLANG_DIALEK", "definition": "Penulisan gabung dari preposisi di sekitar"},
]

async def seed_default_dictionary(db = None):
    if db is None:
        import os
        from app.db.session import get_tenant_sessionmaker
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL is not set in environment. Seeding aborted.")
            return
        session_maker = get_tenant_sessionmaker(db_url)
        async with session_maker() as session:
            await _run_seed(session)
    else:
        await _run_seed(db)

async def _run_seed(db):
    logger.info("Starting default BASARNAS dictionary seed...")
    added_count = 0
    
    # Deduplicate locally just in case
    unique_words = {}
    for w in DEFAULT_WORDS:
        unique_words[w["word"]] = w
        
    for word, w_data in unique_words.items():
        # Check if word already exists in database
        result = await db.execute(
            select(DictionaryWord).where(DictionaryWord.word == word)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            new_word = DictionaryWord(
                word=word,
                ner_type=w_data.get("ner_type"),
                ner_target=w_data.get("ner_target"),
                synonym_target=w_data.get("synonym_target"),
                is_typo_or_slang=w_data.get("is_typo_or_slang", False),
                category=w_data.get("category", "OPERASIONAL_SAR"),
                definition=w_data.get("definition"),
                status=DictionaryStatus.APPROVED,
                word_type=w_data.get("word_type", "GENERAL"),
                is_auto_detected=False
            )
            db.add(new_word)
            added_count += 1
            
    try:
        await db.commit()
        logger.info(f"Successfully seeded {added_count} words into DictionaryWord.")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to commit database seed: {e}")

if __name__ == "__main__":
    asyncio.run(seed_default_dictionary())
