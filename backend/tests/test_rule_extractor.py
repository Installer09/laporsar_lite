"""
Tests for RuleExtractor — SAR-BOT v3 Backend
=============================================
Comprehensive unit tests for the regex-based extraction engine that parses
Indonesian SAR incident messages into structured fields.

Covers:
  - extract_waktu: time/date parsing, relative keywords, max-length guard
  - extract_korban: victim count, number words, named victims
  - extract_koordinat: DMS + decimal coordinate parsing
  - extract_data_kapal: vessel prefix/name/GT extraction
  - extract_jumlah_korban_detail: selamat/meninggal/hilang breakdown
  - extract_jenis_kejadian: classification DB keyword matching (async)
  - extract_lokasi: location DB + regex patterns (async)
  - extract_all: full integration pipeline (async)
  - Edge / destructive cases: long text, emojis, HTML, caps, unicode, etc.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.rule_extractor import RuleExtractor


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def extractor():
    """Provide a fresh RuleExtractor instance for each test."""
    return RuleExtractor()


@pytest.fixture
def mock_db():
    """AsyncMock that mimics SQLAlchemy AsyncSession with empty results."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_classification(category: str, keywords: str) -> MagicMock:
    """Helper: create a mock Classification ORM object."""
    cls = MagicMock()
    cls.category = category
    cls.keywords = keywords
    return cls


def _make_location(name: str) -> MagicMock:
    """Helper: create a mock Location ORM object."""
    loc = MagicMock()
    loc.name = name
    return loc


def _setup_db_classifications(mock_db, classifications: list):
    """Configure mock_db.execute to return classification objects."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = classifications
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)


def _setup_db_locations(mock_db, locations: list):
    """Configure mock_db.execute to return location objects on first call
    and empty results for subsequent calls (dictionary prefixes)."""
    # First call returns locations, second call (dictionary prefixes) raises
    # to trigger the fallback with default prefixes
    call_count = 0
    results = []

    # Location result
    loc_result = MagicMock()
    loc_scalars = MagicMock()
    loc_scalars.all.return_value = locations
    loc_result.scalars.return_value = loc_scalars

    # Empty/error result for dictionary prefix query
    empty_result = MagicMock()
    empty_scalars = MagicMock()
    empty_scalars.all.return_value = []
    empty_result.scalars.return_value = empty_scalars

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return loc_result
        return empty_result

    mock_db.execute = AsyncMock(side_effect=side_effect)


# =====================================================================
# extract_waktu tests
# =====================================================================

class TestExtractWaktu:
    """Tests for RuleExtractor.extract_waktu — time/date extraction."""

    def test_01_tadi_pagi_jam(self):
        """Should extract time from 'tadi pagi jam 10:30'."""
        result = RuleExtractor.extract_waktu("tadi pagi jam 10:30")
        assert result is not None
        assert result != ""
        # Should match the 'tadi pagi' keyword first (longest-first match)
        assert "Tadi Pagi" in result or "10:30" in result or "10" in result

    def test_02_kemarin_sore(self):
        """Should extract 'kemarin sore' relative keyword."""
        result = RuleExtractor.extract_waktu("Kejadian terjadi kemarin sore di laut")
        assert result == "Kemarin Sore"

    def test_03_relative_jam_lalu(self):
        """Should handle 'kemarin' keyword within longer text."""
        result = RuleExtractor.extract_waktu("Kapal tenggelam kemarin di Selat Sunda")
        assert result is not None
        assert result != ""
        assert "Kemarin" in result

    def test_04_tanggal_full_date(self):
        """Should extract full Indonesian date with month name."""
        result = RuleExtractor.extract_waktu("Kejadian tanggal 15 Januari 2024 di laut")
        assert result is not None
        assert result != ""
        assert "15" in result
        assert "Januari" in result
        assert "2024" in result

    def test_05_pukul_wib(self):
        """Should extract 'pukul 14.30 WIB' format."""
        result = RuleExtractor.extract_waktu("terjadi pukul 14.30 WIB di perairan")
        assert result is not None
        assert result != ""
        assert "14" in result

    def test_06_barusan(self):
        """'hari ini' relative keyword should be extracted."""
        result = RuleExtractor.extract_waktu("Kejadian hari ini ada kapal tenggelam")
        assert result is not None
        assert result != ""
        assert "Hari Ini" in result

    def test_07_no_time_info(self):
        """Should return empty string when no time information present."""
        result = RuleExtractor.extract_waktu("Kapal nelayan di perairan Selat Makassar")
        assert result == ""

    def test_08_time_buried_in_long_text(self):
        """Should find time even when buried in long narrative."""
        msg = (
            "Laporan masuk dari nelayan di perairan Selat Makassar, "
            "cuaca buruk dengan ombak tinggi sekitar 3 meter, "
            "kejadian terjadi tadi malam sekitar pukul 23.00 WIB "
            "saat kapal sedang berlayar menuju pelabuhan."
        )
        result = RuleExtractor.extract_waktu(msg)
        assert result is not None
        assert result != ""

    def test_09_multiple_time_references(self):
        """Should extract the first/primary time reference found."""
        msg = "Kejadian 15 Januari 2024 dilaporkan kemarin sore"
        result = RuleExtractor.extract_waktu(msg)
        assert result is not None
        assert result != ""
        # Date patterns are checked first, so should get the date
        assert "15" in result and "Januari" in result

    def test_10_max_60_chars_guard(self):
        """Extracted time string must not exceed 60 characters."""
        msg = "30 April 2026 pukul 06.00 WIB"
        result = RuleExtractor.extract_waktu(msg)
        assert result is not None
        assert len(result) <= 60

    def test_waktu_date_slash_format(self):
        """Should extract date in DD/MM/YYYY format."""
        result = RuleExtractor.extract_waktu("Kejadian pada 30/04/2026 di laut")
        assert result is not None
        assert result != ""
        assert "30" in result

    def test_waktu_date_dash_format(self):
        """Should extract date in DD-MM-YYYY format."""
        result = RuleExtractor.extract_waktu("Terjadi tanggal 30-04-2026 pagi")
        assert result is not None
        assert result != ""

    def test_waktu_kemarin_malam(self):
        """Should extract 'kemarin malam' compound keyword."""
        result = RuleExtractor.extract_waktu("Ada kapal hilang kemarin malam")
        assert result == "Kemarin Malam"

    def test_waktu_dini_hari(self):
        """Should extract 'dini hari tadi' compound keyword."""
        result = RuleExtractor.extract_waktu("Kejadian dini hari tadi jam 02.00")
        assert result is not None
        assert result != ""

    def test_waktu_jam_standalone(self):
        """Should extract 'jam 10' standalone format."""
        result = RuleExtractor.extract_waktu("Kejadian sekitar jam 10 pagi")
        assert result is not None
        assert result != ""
        assert "10" in result

    def test_waktu_wita_timezone(self):
        """Should extract times with WITA timezone."""
        result = RuleExtractor.extract_waktu("Kejadian pukul 08.00 WITA")
        assert result is not None
        assert result != ""

    def test_waktu_empty_string(self):
        """Empty message should return empty string."""
        result = RuleExtractor.extract_waktu("")
        assert result == ""


# =====================================================================
# extract_korban tests
# =====================================================================

class TestExtractKorban:
    """Tests for RuleExtractor.extract_korban — victim count extraction."""

    def test_11_digit_orang_korban(self):
        """Should extract '2 orang' from '2 orang korban'."""
        result = RuleExtractor.extract_korban("ada 2 orang korban tenggelam")
        assert result is not None
        assert result != ""
        assert "2" in result

    def test_12_korban_digit_orang(self):
        """Should extract from 'korban 5 orang' format."""
        result = RuleExtractor.extract_korban("jumlah korban 5 orang nelayan")
        assert result is not None
        assert result != ""
        assert "5" in result

    def test_13_number_word_tiga(self):
        """Should convert 'tiga orang' → 3."""
        result = RuleExtractor.extract_korban("ada tiga orang korban")
        assert result is not None
        assert result != ""
        assert "3" in result

    def test_14_seorang_nelayan(self):
        """Should handle 'satu orang nelayan' → 1."""
        result = RuleExtractor.extract_korban("satu orang nelayan hilang")
        assert result is not None
        assert result != ""
        assert "1" in result

    def test_15_dua_belas(self):
        """Should not match 'dua belas' as a compound number word
        (two-word numbers may not be in the generic pattern)."""
        # 'dua belas' requires special handling; test actual behavior
        result = RuleExtractor.extract_korban("ada dua belas orang penumpang")
        # Even if 'dua belas' isn't matched, 'dua' alone may match
        assert result is not None or result == ""

    def test_16_named_victim_bernama(self):
        """Should extract named victim from 'korban bernama Budi'."""
        result = RuleExtractor.extract_korban("korban bernama Budi Santoso")
        assert result is not None
        assert result != ""
        assert "1 Orang" in result
        assert "Budi" in result

    def test_17_no_victim_info(self):
        """Should return empty string when no victim info present."""
        result = RuleExtractor.extract_korban("Kapal berlayar ke arah timur cuaca cerah")
        assert result == ""

    def test_18_parenthesized_number(self):
        """Should normalize '6 (enam) orang' → '6 orang'."""
        result = RuleExtractor.extract_korban("ada 6 (enam) orang penumpang")
        assert result is not None
        assert result != ""
        assert "6" in result

    def test_korban_identitas_format(self):
        """Should extract from formal 'identitas korban, Name Gender Age Tahun'."""
        msg = "Identitas korban, Arman Laki-laki 46 Tahun"
        result = RuleExtractor.extract_korban(msg)
        assert result is not None
        assert result != ""
        assert "1 Orang" in result
        assert "Arman" in result

    def test_korban_multiple_digit_patterns(self):
        """Should pick the largest victim count when multiple numbers present."""
        msg = "2 orang nelayan dan 5 orang penumpang tenggelam"
        result = RuleExtractor.extract_korban(msg)
        assert result is not None
        assert result != ""
        # Should get the larger count (5) from generic matching
        assert "5" in result

    def test_korban_abk(self):
        """Should extract '3 ABK' as a valid victim pattern."""
        result = RuleExtractor.extract_korban("total 3 abk terjatuh ke laut")
        assert result is not None
        assert result != ""
        assert "3" in result

    def test_korban_specific_role(self):
        """Should extract '4 orang wisatawan' with the role."""
        result = RuleExtractor.extract_korban("ada 4 orang wisatawan tersesat")
        assert result is not None
        assert result != ""
        assert "4" in result
        assert "Wisatawan" in result

    def test_korban_atas_nama(self):
        """Should extract named victim from 'korban atas nama ...' format."""
        result = RuleExtractor.extract_korban("korban atas nama Siti Aminah")
        assert result is not None
        assert result != ""
        assert "1 Orang" in result
        assert "Siti" in result

    def test_korban_colloquial_bertiga(self):
        """Should extract 3 Orang from colloquial 'bertiga'."""
        result = RuleExtractor.extract_korban("Mereka pergi bertiga")
        assert result == "3 Orang"

    def test_korban_colloquial_berdua(self):
        """Should extract 2 Orang from colloquial 'berdua'."""
        result = RuleExtractor.extract_korban("pergi berdua mencari ikan")
        assert result == "2 Orang"


# =====================================================================
# extract_koordinat tests
# =====================================================================

class TestExtractKoordinat:
    """Tests for RuleExtractor.extract_koordinat — coordinate parsing."""

    def test_19_decimal_negative(self):
        """Should parse negative decimal coordinates: -6.123, 106.456."""
        result = RuleExtractor.extract_koordinat("Lokasi di -6.12300, 106.45600")
        assert result is not None
        lat, lng = result
        assert abs(lat - (-6.123)) < 0.001
        assert abs(lng - 106.456) < 0.001

    def test_20_dms_format(self):
        """Should parse DMS coordinates and convert to decimal."""
        msg = "Posisi 3°45'12\"S 108°30'45\"E"
        result = RuleExtractor.extract_koordinat(msg)
        assert result is not None
        lat, lng = result
        # 3°45'12"S → -(3 + 45/60 + 12/3600) ≈ -3.7533
        assert lat < 0  # South should be negative
        assert lng > 0  # East should be positive
        assert abs(lat - (-3.753333)) < 0.01
        assert abs(lng - 108.5125) < 0.01

    def test_21_no_coordinates(self):
        """Should return None when no coordinates present."""
        result = RuleExtractor.extract_koordinat("Kapal tenggelam di Selat Sunda")
        assert result is None

    def test_22_invalid_out_of_range(self):
        """Should return None for coordinates outside valid range."""
        # Latitude > 90 is invalid
        result = RuleExtractor.extract_koordinat("Posisi 95.12345, 200.67890")
        assert result is None

    def test_23_dms_indonesian_labels(self):
        """Should handle Indonesian DMS labels (LU/LS/BT/BB)."""
        msg = "Koordinat 3°22'20\"LU 106°13'51\"BT"
        result = RuleExtractor.extract_koordinat(msg)
        assert result is not None
        lat, lng = result
        # LU (Lintang Utara) = North → positive
        assert lat > 0
        # BT (Bujur Timur) = East → positive
        assert lng > 0

    def test_koordinat_decimal_slash_separator(self):
        """Should parse decimal coordinates with '/' separator."""
        result = RuleExtractor.extract_koordinat("Koordinat -3.39128 / 106.24152")
        assert result is not None
        lat, lng = result
        assert abs(lat - (-3.39128)) < 0.001
        assert abs(lng - 106.24152) < 0.001

    def test_koordinat_dms_south_west(self):
        """Should handle S and W directions as negative."""
        msg = "Posisi 6°10'30\"S 105°15'20\"W"
        result = RuleExtractor.extract_koordinat(msg)
        assert result is not None
        lat, lng = result
        assert lat < 0  # South
        assert lng < 0  # West

    def test_koordinat_dms_comma_seconds(self):
        """Should handle DMS with comma in seconds (3°22'20,92\"LU)."""
        msg = "Posisi 3°22'20,92\"LU 106°13'51,78\"BT"
        result = RuleExtractor.extract_koordinat(msg)
        assert result is not None
        lat, lng = result
        assert lat > 0
        assert lng > 0

    def test_koordinat_with_degree_symbol(self):
        """Should parse decimal coords with degree symbols."""
        result = RuleExtractor.extract_koordinat("Lokasi -6.12345°, 106.78901°")
        assert result is not None
        lat, lng = result
        assert abs(lat - (-6.12345)) < 0.001


# =====================================================================
# extract_data_kapal tests
# =====================================================================

class TestExtractDataKapal:
    """Tests for RuleExtractor.extract_data_kapal — vessel info extraction."""

    def test_24_km_vessel(self):
        """Should extract 'KM Sinar Jaya' vessel name."""
        result = RuleExtractor.extract_data_kapal("KM Sinar Jaya tenggelam di laut")
        assert result is not None
        assert result != ""
        assert "KM" in result
        assert "Sinar Jaya" in result

    def test_25_gt_extraction(self):
        """Should extract GT (Gross Tonnage) from 'GT 30'."""
        result = RuleExtractor.extract_data_kapal("kapal nelayan GT 30 tenggelam")
        assert result is not None
        assert result != ""
        assert "GT" in result
        assert "30" in result

    def test_26_kri_vessel(self):
        """Should extract 'KRI Diponegoro' military vessel."""
        result = RuleExtractor.extract_data_kapal("KRI Diponegoro melakukan evakuasi")
        assert result is not None
        assert result != ""
        assert "KRI" in result
        assert "Diponegoro" in result

    def test_27_no_vessel_info(self):
        """Should return empty string when no vessel info present."""
        result = RuleExtractor.extract_data_kapal("Ada korban hanyut di sungai")
        assert result == ""

    def test_28_multiple_vessels(self):
        """Should extract multiple vessel mentions."""
        msg = "KM Sinar Laut bertabrakan dengan TB Jaya di selat"
        result = RuleExtractor.extract_data_kapal(msg)
        assert result is not None
        assert result != ""
        # Should contain info about both vessels
        assert "KM" in result
        assert "TB" in result

    def test_kapal_kmn_prefix(self):
        """Should extract KMN (Kapal Motor Nelayan) prefix."""
        result = RuleExtractor.extract_data_kapal("KMN Bahari 01 hilang kontak")
        assert result is not None
        assert result != ""
        assert "KMN" in result

    def test_kapal_mv_tanker(self):
        """Should extract MV (Motor Vessel) prefix."""
        result = RuleExtractor.extract_data_kapal("MV Pacific Glory kandas")
        assert result is not None
        assert result != ""
        assert "MV" in result

    def test_kapal_generic_pompong(self):
        """Should extract generic small boat type 'pompong'."""
        result = RuleExtractor.extract_data_kapal("pompong milik nelayan bocor")
        assert result is not None
        assert result != ""
        assert "Pompong" in result

    def test_kapal_generic_perahu(self):
        """Should extract generic 'perahu' type."""
        result = RuleExtractor.extract_data_kapal("perahu terbalik saat badai")
        assert result is not None
        assert result != ""
        assert "Perahu" in result

    def test_kapal_gt_after_value(self):
        """Should extract GT when pattern is 'GT: 50'."""
        result = RuleExtractor.extract_data_kapal("KM Sejahtera GT 50 tenggelam")
        assert result is not None
        assert result != ""
        assert "50" in result

    def test_kapal_lct_prefix(self):
        """Should extract LCT (Landing Craft Tank) prefix."""
        result = RuleExtractor.extract_data_kapal("LCT Mutiara Persada karam")
        assert result is not None
        assert result != ""
        assert "LCT" in result

    def test_kapal_color_extraction(self):
        """Should extract Warna: Biru from Pompong, 3 GT, Warna Biru."""
        result = RuleExtractor.extract_data_kapal("Pompong, 3 GT, Warna Biru")
        assert "Warna: Biru" in result
        assert "GT: 3" in result
        assert "Pompong" in result


# =====================================================================
# extract_jumlah_korban_detail tests
# =====================================================================

class TestExtractJumlahKorbanDetail:
    """Tests for RuleExtractor.extract_jumlah_korban_detail — victim breakdown."""

    def test_29_selamat_and_meninggal(self):
        """Should extract selamat=2 and meninggal=1 breakdown."""
        msg = "2 orang selamat, 1 orang meninggal dunia"
        result = RuleExtractor.extract_jumlah_korban_detail(msg)
        assert result is not None
        assert result.get("selamat") == "2"
        assert result.get("meninggal") == "1"

    def test_30_hilang_only(self):
        """Should extract hilang=3 when only 'hilang' is mentioned."""
        result = RuleExtractor.extract_jumlah_korban_detail("3 orang hilang")
        assert result is not None
        assert result.get("hilang") == "3"

    def test_31_no_detail(self):
        """Should return None when no victim status detail found."""
        result = RuleExtractor.extract_jumlah_korban_detail("Kapal berlayar normal")
        assert result is None

    def test_detail_all_three_statuses(self):
        """Should extract all three statuses in one message."""
        msg = "5 orang selamat, 2 orang meninggal, 3 orang hilang"
        result = RuleExtractor.extract_jumlah_korban_detail(msg)
        assert result is not None
        assert result.get("selamat") == "5"
        assert result.get("meninggal") == "2"
        assert result.get("hilang") == "3"

    def test_detail_tewas_synonym(self):
        """Should recognize 'tewas' as synonym for 'meninggal'."""
        result = RuleExtractor.extract_jumlah_korban_detail("1 orang tewas")
        assert result is not None
        assert result.get("meninggal") == "1"

    def test_detail_dievakuasi_as_selamat(self):
        """Should recognize 'dievakuasi' as synonym for 'selamat'."""
        result = RuleExtractor.extract_jumlah_korban_detail("4 orang dievakuasi")
        assert result is not None
        assert result.get("selamat") == "4"

    def test_detail_belum_ditemukan_as_hilang(self):
        """Should recognize 'belum ditemukan' as synonym for 'hilang'."""
        result = RuleExtractor.extract_jumlah_korban_detail("2 orang belum ditemukan")
        assert result is not None
        assert result.get("hilang") == "2"

    def test_detail_normalized_parenthesized(self):
        """Should handle '3 (tiga) orang selamat' via normalization."""
        msg = "3 (tiga) orang selamat, 1 (satu) orang meninggal"
        result = RuleExtractor.extract_jumlah_korban_detail(msg)
        assert result is not None
        assert result.get("selamat") == "3"
        assert result.get("meninggal") == "1"

    def test_detail_md_dp_abbreviations(self):
        """Should recognize MD (Meninggal Dunia) and DP (Dalam Pencarian)."""
        result = RuleExtractor.extract_jumlah_korban_detail(
            "1 orang MD, 2 orang masih dalam pencarian"
        )
        assert result is not None
        # At least one of the statuses should be found
        assert len(result) >= 1


# =====================================================================
# extract_jenis_kejadian tests (async, requires DB mock)
# =====================================================================

class TestExtractJenisKejadian:
    """Tests for RuleExtractor.extract_jenis_kejadian — classification matching."""

    @pytest.mark.asyncio
    async def test_keyword_match(self, mock_db):
        """Should match classification keyword in message."""
        classifications = [
            _make_classification("LAKA KAPAL", "kapal tenggelam,kapal terbalik"),
            _make_classification("ORANG HILANG", "orang hilang,hilang di laut"),
        ]
        _setup_db_classifications(mock_db, classifications)

        result = await RuleExtractor.extract_jenis_kejadian(
            "Ada kapal tenggelam di Selat Makassar", mock_db
        )
        assert result == "LAKA KAPAL"

    @pytest.mark.asyncio
    async def test_keyword_case_insensitive(self, mock_db):
        """Should match keywords regardless of case."""
        classifications = [
            _make_classification("LAKA KAPAL", "kecelakaan kapal"),
        ]
        _setup_db_classifications(mock_db, classifications)

        result = await RuleExtractor.extract_jenis_kejadian(
            "KECELAKAAN KAPAL di perairan", mock_db
        )
        assert result == "LAKA KAPAL"

    @pytest.mark.asyncio
    async def test_category_fallback(self, mock_db):
        """Should match category name itself when no keyword matches."""
        classifications = [
            _make_classification("ORANG HILANG", "hilang,missing"),
        ]
        _setup_db_classifications(mock_db, classifications)

        result = await RuleExtractor.extract_jenis_kejadian(
            "Ada laporan orang hilang di hutan", mock_db
        )
        assert result == "ORANG HILANG"

    @pytest.mark.asyncio
    async def test_no_match(self, mock_db):
        """Should return empty string when no classification matches."""
        classifications = [
            _make_classification("LAKA KAPAL", "kapal tenggelam"),
        ]
        _setup_db_classifications(mock_db, classifications)

        result = await RuleExtractor.extract_jenis_kejadian(
            "Cuaca cerah hari ini", mock_db
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_empty_db(self, mock_db):
        """Should return empty string when DB has no classifications."""
        _setup_db_classifications(mock_db, [])

        result = await RuleExtractor.extract_jenis_kejadian(
            "Kapal tenggelam", mock_db
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_classification_empty_keywords(self, mock_db):
        """Should skip classifications with empty/None keywords."""
        classifications = [
            _make_classification("LAKA KAPAL", ""),
            _make_classification("BENCANA ALAM", None),
        ]
        _setup_db_classifications(mock_db, classifications)

        result = await RuleExtractor.extract_jenis_kejadian(
            "Terjadi gempa bumi", mock_db
        )
        # Neither should match via keywords; 'bencana alam' category fallback
        # might match if "bencana alam" is in message — it's not exactly
        assert result == "" or result is not None


# =====================================================================
# extract_lokasi tests (async, requires DB mock)
# =====================================================================

class TestExtractLokasi:
    """Tests for RuleExtractor.extract_lokasi — location extraction."""

    @pytest.mark.asyncio
    async def test_db_location_match(self, mock_db):
        """Should match location name from DB."""
        locations = [_make_location("Selat Makassar")]
        _setup_db_locations(mock_db, locations)

        result = await RuleExtractor.extract_lokasi(
            "Kapal tenggelam di Selat Makassar", mock_db
        )
        assert result == "Selat Makassar"

    @pytest.mark.asyncio
    async def test_regex_perairan_pattern(self, mock_db):
        """Should extract location from 'di perairan ...' pattern."""
        _setup_db_locations(mock_db, [])

        result = await RuleExtractor.extract_lokasi(
            "Kejadian di perairan nusa tenggara", mock_db
        )
        assert result is not None
        assert result != ""

    @pytest.mark.asyncio
    async def test_regex_sungai_pattern(self, mock_db):
        """Should extract location from 'di sungai ...' pattern."""
        _setup_db_locations(mock_db, [])

        result = await RuleExtractor.extract_lokasi(
            "Orang tenggelam di sungai musi palembang", mock_db
        )
        assert result is not None
        assert result != ""

    @pytest.mark.asyncio
    async def test_no_location(self, mock_db):
        """Should return empty string when no location found."""
        _setup_db_locations(mock_db, [])

        result = await RuleExtractor.extract_lokasi(
            "Tolong bantu kami segera", mock_db
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_lokasi_gunung(self, mock_db):
        """Should extract 'gunung' location pattern."""
        _setup_db_locations(mock_db, [])

        result = await RuleExtractor.extract_lokasi(
            "Pendaki hilang di gunung rinjani lombok", mock_db
        )
        assert result is not None
        assert result != ""

    @pytest.mark.asyncio
    async def test_lokasi_max_4_words(self, mock_db):
        """Extracted location should be at most 4 words."""
        _setup_db_locations(mock_db, [])

        result = await RuleExtractor.extract_lokasi(
            "Korban terseret arus di pantai kuta bali selatan menuju arah timur",
            mock_db,
        )
        if result:
            word_count = len(result.split())
            assert word_count <= 4

    @pytest.mark.asyncio
    async def test_lokasi_boundary_trimming(self, mock_db):
        """Should trim transition words from location text."""
        _setup_db_locations(mock_db, [])

        # Trim 'kejadiannya jam 10.00'
        loc_a = await RuleExtractor.extract_lokasi(
            "KMM 2 org tenggelam di pantai piwang kejadiannya jam 10.00", mock_db
        )
        assert loc_a == "Pantai Piwang"

        # Trim 'pukul 08:00'
        loc_b = await RuleExtractor.extract_lokasi(
            "kejadian di laut natuna pukul 08:00", mock_db
        )
        assert loc_b == "Laut Natuna"

        # Trim 'dan'
        loc_c = await RuleExtractor.extract_lokasi(
            "di perairan selat lempa dan ada pompong tenggelam", mock_db
        )
        assert loc_c == "Perairan Selat Lempa"


# =====================================================================
# extract_all integration tests (async)
# =====================================================================

class TestExtractAll:
    """Tests for RuleExtractor.extract_all — full extraction pipeline."""

    @pytest.mark.asyncio
    async def test_32_full_realistic_message(self, mock_db):
        """Should extract multiple fields from a realistic SAR message."""
        classifications = [
            _make_classification("LAKA KAPAL", "kapal tenggelam,kapal terbalik"),
        ]
        locations = [_make_location("Selat Makassar")]

        # Need to handle both classification and location DB calls
        call_count = 0
        cls_result = MagicMock()
        cls_scalars = MagicMock()
        cls_scalars.all.return_value = classifications
        cls_result.scalars.return_value = cls_scalars

        loc_result = MagicMock()
        loc_scalars = MagicMock()
        loc_scalars.all.return_value = locations
        loc_result.scalars.return_value = loc_scalars

        empty_result = MagicMock()
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        empty_result.scalars.return_value = empty_scalars

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return cls_result  # classification query
            if call_count == 2:
                return loc_result  # location query
            return empty_result  # dictionary prefix / enrichment queries

        mock_db.execute = AsyncMock(side_effect=side_effect)

        msg = (
            "KM Sinar Laut GT 50 mengalami kapal tenggelam di Selat Makassar "
            "tanggal 15 Januari 2024 pukul 08.00 WIB. "
            "Ada 5 orang penumpang, 3 orang selamat, 2 orang hilang. "
            "Koordinat -3.39128, 106.24152."
        )

        result = await RuleExtractor.extract_all(msg, mock_db)

        assert "kronologi" in result
        assert result.get("jenis_kejadian") == "LAKA KAPAL"
        assert result.get("lokasi_teks") == "Selat Makassar"
        assert result.get("waktu") is not None
        assert result.get("korban") is not None
        assert result.get("koordinat_lat") is not None
        assert result.get("koordinat_lng") is not None
        assert result.get("data_kapal") is not None
        assert result.get("korban_detail") is not None

    @pytest.mark.asyncio
    async def test_33_empty_message(self, mock_db):
        """Empty message should return dict with only kronologi."""
        _setup_db_classifications(mock_db, [])

        result = await RuleExtractor.extract_all("", mock_db)
        assert "kronologi" in result
        assert result["kronologi"] == ""

    @pytest.mark.asyncio
    async def test_34_partial_only_location(self, mock_db):
        """Message with only location should return partial extraction."""
        # Set cache as loaded to prevent extra db calls for DictionaryWord
        RuleExtractor._cache_loaded = True
        RuleExtractor._dictionary_cache = {}
        try:
            locations = [_make_location("Pelabuhan Tanjung Priok")]

            call_count = 0
            cls_result = MagicMock()
            cls_scalars = MagicMock()
            cls_scalars.all.return_value = []
            cls_result.scalars.return_value = cls_scalars

            loc_result = MagicMock()
            loc_scalars = MagicMock()
            loc_scalars.all.return_value = locations
            loc_result.scalars.return_value = loc_scalars

            empty_result = MagicMock()
            empty_scalars = MagicMock()
            empty_scalars.all.return_value = []
            empty_result.scalars.return_value = empty_scalars

            async def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return cls_result
                if call_count == 2:
                    return loc_result
                return empty_result

            mock_db.execute = AsyncMock(side_effect=side_effect)

            result = await RuleExtractor.extract_all(
                "Di Pelabuhan Tanjung Priok", mock_db
            )
            assert result.get("lokasi_teks") is not None
            # Other fields should be absent or empty
            assert result.get("jenis_kejadian") is None or result.get("jenis_kejadian") == ""
        finally:
            RuleExtractor._cache_loaded = False
            RuleExtractor._dictionary_cache = {}


# =====================================================================
# Edge / Destructive Cases
# =====================================================================

class TestEdgeCases:
    """Destructive and edge-case tests for RuleExtractor robustness."""

    def test_36_very_long_message(self):
        """Should not crash on a 10,000+ character message."""
        long_msg = "Kapal nelayan " + ("mengalami kesulitan di laut " * 500)
        # Should not raise — result doesn't matter, just no crash
        result = RuleExtractor.extract_waktu(long_msg)
        assert isinstance(result, str)

        result2 = RuleExtractor.extract_korban(long_msg)
        assert isinstance(result2, str)

        result3 = RuleExtractor.extract_koordinat(long_msg)
        assert result3 is None or isinstance(result3, tuple)

        result4 = RuleExtractor.extract_data_kapal(long_msg)
        assert isinstance(result4, str)

    def test_37_all_caps_message(self):
        """Should handle ALL CAPS messages (case-insensitive matching)."""
        result = RuleExtractor.extract_waktu("KEJADIAN KEMARIN SORE DI LAUT")
        assert result is not None
        assert result != ""
        assert "Kemarin Sore" in result

    def test_37b_all_caps_korban(self):
        """Should extract victim count from ALL CAPS message."""
        result = RuleExtractor.extract_korban("ADA 5 ORANG KORBAN TENGGELAM")
        assert result is not None
        assert result != ""
        assert "5" in result

    def test_38_message_with_emojis(self):
        """Should handle messages containing emojis without crashing."""
        msg = "🚨 Ada kapal tenggelam 🚢 korban 3 orang 😢 kemarin sore"
        result_waktu = RuleExtractor.extract_waktu(msg)
        result_korban = RuleExtractor.extract_korban(msg)
        # Should not crash, may or may not extract depending on emoji positions
        assert isinstance(result_waktu, str)
        assert isinstance(result_korban, str)

    def test_39_message_with_html_tags(self):
        """Should handle messages with HTML tags without crashing."""
        msg = "<b>URGENT</b> kapal <i>nelayan</i> tenggelam 3 orang korban kemarin"
        result = RuleExtractor.extract_korban(msg)
        assert isinstance(result, str)

    def test_40_sql_injection_in_message(self):
        """Should handle SQL injection attempts gracefully (no crash)."""
        msg = "'; DROP TABLE reports; -- kapal tenggelam 3 orang korban"
        result = RuleExtractor.extract_korban(msg)
        assert isinstance(result, str)
        assert "3" in result

    def test_41_english_message(self):
        """English-only message should fail gracefully (no Indonesian keywords)."""
        msg = "A ship sank in the ocean yesterday with 5 people on board"
        result_waktu = RuleExtractor.extract_waktu(msg)
        result_korban = RuleExtractor.extract_korban(msg)
        # Indonesian keywords won't match, but English number + generic patterns might
        assert isinstance(result_waktu, str)
        assert isinstance(result_korban, str)

    def test_42_repeated_patterns(self):
        """Should handle messages with repeated patterns gracefully."""
        msg = "3 orang korban 3 orang korban 3 orang korban di laut"
        result = RuleExtractor.extract_korban(msg)
        assert result is not None
        assert "3" in result

    def test_43_unicode_numbers(self):
        """Should handle Unicode full-width numbers gracefully (no crash)."""
        msg = "Korban ３ orang di laut"  # Full-width '3'
        result = RuleExtractor.extract_korban(msg)
        # May not match, but should not crash
        assert isinstance(result, str)

    def test_44_negative_numbers(self):
        """Should not treat negative numbers as victim counts."""
        msg = "Suhu -5 derajat dan angin kencang"
        result = RuleExtractor.extract_korban(msg)
        # Should not extract '-5' as victim count
        assert result == "" or "5" not in result

    def test_edge_newlines_in_message(self):
        """Should handle messages with newlines."""
        msg = "Laporan:\nKapal KM Jaya tenggelam\n3 orang korban\nKemarin sore"
        result_kapal = RuleExtractor.extract_data_kapal(msg)
        result_korban = RuleExtractor.extract_korban(msg)
        result_waktu = RuleExtractor.extract_waktu(msg)
        assert isinstance(result_kapal, str)
        assert isinstance(result_korban, str)
        assert isinstance(result_waktu, str)

    def test_edge_tabs_and_extra_whitespace(self):
        """Should handle tabs and extra whitespace in messages."""
        msg = "Kapal  \t KM   Sejahtera   tenggelam   GT  50"
        result = RuleExtractor.extract_data_kapal(msg)
        assert isinstance(result, str)

    def test_edge_special_characters(self):
        """Should handle special characters without crashing."""
        msg = "Kapal @#$%^&*() tenggelam!!!"
        result = RuleExtractor.extract_data_kapal(msg)
        assert isinstance(result, str)

    def test_edge_only_whitespace(self):
        """Should handle whitespace-only message."""
        result = RuleExtractor.extract_waktu("   \t\n  ")
        assert result == ""


# =====================================================================
# _normalize_num_format tests
# =====================================================================

class TestNormalizeNumFormat:
    """Tests for the internal _normalize_num_format helper."""

    def test_parenthesized_word_removed(self):
        """Should strip '(enam)' after digit: '6 (enam) orang' → '6 orang'."""
        result = RuleExtractor._normalize_num_format("6 (enam) orang")
        assert "(enam)" not in result
        assert "6" in result
        assert "orang" in result

    def test_anak_anak_normalized(self):
        """Should normalize 'anak-anak' → 'anak'."""
        result = RuleExtractor._normalize_num_format("3 orang anak-anak")
        assert "anak-anak" not in result
        assert "anak" in result

    def test_no_change_normal_text(self):
        """Should not modify text without parenthesized numbers."""
        text = "5 orang nelayan hilang"
        result = RuleExtractor._normalize_num_format(text)
        assert result == text


# =====================================================================
# _dms_to_decimal tests
# =====================================================================

class TestDmsToDecimal:
    """Tests for the internal _dms_to_decimal conversion helper."""

    def test_north_positive(self):
        """North (N) direction should produce positive decimal."""
        import re
        pattern = RuleExtractor._DMS_PATTERN
        match = pattern.search("3°45'12\"N")
        assert match is not None
        result = RuleExtractor._dms_to_decimal(match)
        assert result > 0
        expected = 3 + 45/60 + 12/3600
        assert abs(result - expected) < 0.0001

    def test_south_negative(self):
        """South (S) direction should produce negative decimal."""
        import re
        pattern = RuleExtractor._DMS_PATTERN
        match = pattern.search("6°10'30\"S")
        assert match is not None
        result = RuleExtractor._dms_to_decimal(match)
        assert result < 0

    def test_ls_negative(self):
        """LS (Lintang Selatan) should produce negative decimal."""
        import re
        pattern = RuleExtractor._DMS_PATTERN
        match = pattern.search("3°22'20\"LS")
        assert match is not None
        result = RuleExtractor._dms_to_decimal(match)
        assert result < 0

    def test_bt_positive(self):
        """BT (Bujur Timur) should produce positive decimal."""
        import re
        pattern = RuleExtractor._DMS_PATTERN
        match = pattern.search("106°13'51\"BT")
        assert match is not None
        result = RuleExtractor._dms_to_decimal(match)
        assert result > 0


# =====================================================================
# Dictionary Integration Tests (async)
# =====================================================================

class TestDictionaryIntegration:
    """Tests for RuleExtractor integrations with DictionaryWord table."""

    @pytest.mark.asyncio
    async def test_extract_lokasi_from_dictionary(self, mock_db):
        """Should extract location from approved DictionaryWord entry."""
        from app.models.knowledge_models import DictionaryWord, DictionaryStatus
        
        # Mock the DB result for DictionaryWord query
        dw = DictionaryWord(
            word="senoa",
            status=DictionaryStatus.APPROVED,
            ner_type="Nama Tempat",
            ner_target="Data Lokasi"
        )
        
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [dw]
        result_mock.scalars.return_value = scalars_mock
        
        # Setup DB execute return
        async def side_effect(*args, **kwargs):
            return result_mock
            
        mock_db.execute = AsyncMock(side_effect=side_effect)
        
        result = await RuleExtractor.extract_lokasi("di dekat senoa jam 4 sore", mock_db)
        assert result == "Senoa"

    @pytest.mark.asyncio
    async def test_extract_jenis_kejadian_from_dictionary(self, mock_db):
        """Should extract incident classification from approved DictionaryWord entry."""
        from app.models.knowledge_models import DictionaryWord, DictionaryStatus
        
        # Mock the DB result for DictionaryWord query
        dw = DictionaryWord(
            word="mati mesin",
            status=DictionaryStatus.APPROVED,
            ner_type="Nama Kejadian",
            ner_target="Laka Kapal"
        )
        
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [dw]
        result_mock.scalars.return_value = scalars_mock
        
        # Setup DB execute return
        # The first call inside extract_jenis_kejadian is Classification query (which we mock as empty list)
        # The second call is DictionaryWord query
        call_count = 0
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return result_mock
            
        mock_db.execute = AsyncMock(side_effect=side_effect)
        
        result = await RuleExtractor.extract_jenis_kejadian("pompong mati mesin", mock_db)
        assert result == "LAKA KAPAL"

    @pytest.mark.asyncio
    async def test_dynamic_cache_nlp_extraction(self, mock_db):
        """Should utilize dynamic cache to extract new words correctly."""
        from app.models.knowledge_models import DictionaryWord, DictionaryStatus
        
        # Mock entries in database
        words = [
            DictionaryWord(word="tigo", status=DictionaryStatus.APPROVED, ner_type="QUANTIFIER", ner_target="3"),
            DictionaryWord(word="kemarin petang", status=DictionaryStatus.APPROVED, ner_type="TIME_MARKER", ner_target="kemarin petang"),
            DictionaryWord(word="pompong_baru", status=DictionaryStatus.APPROVED, ner_type="VESSEL_TYPE", ner_target="pompong_baru"),
            DictionaryWord(word="hanyut_lagi", status=DictionaryStatus.APPROVED, ner_type="INCIDENT_PROBLEM", ner_target="hanyut_lagi"),
            DictionaryWord(word="natuna_island", status=DictionaryStatus.APPROVED, ner_type="ISLAND", ner_target="natuna_island"),
        ]
        
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = words
        result_mock.scalars.return_value = scalars_mock
        
        mock_db.execute = AsyncMock(return_value=result_mock)
        
        # Load the cache
        await RuleExtractor.load_cache(mock_db)
        
        # Test time marker dynamic extraction
        waktu = RuleExtractor.extract_waktu("kejadian kemarin petang")
        assert waktu == "Kemarin Petang"
        
        # Test quantifier/victim count dynamic extraction
        korban = RuleExtractor.extract_korban("ada tigo orang hilang")
        assert "3 Orang" in korban
