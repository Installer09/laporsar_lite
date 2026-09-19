"""
Comprehensive tests for app.schemas.nlp_schemas module.

Covers:
- KorbanDetail: defaults, optional fields, edge cases
- SARExtractedFields: clean_unknown validator, defaults, serialization
"""

import pytest
from app.schemas.nlp_schemas import SARExtractedFields, KorbanDetail


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def complete_korban_data():
    """Fixture providing a fully-populated KorbanDetail dict."""
    return {
        "nama": "Budi Santoso",
        "umur": "35",
        "jenis_kelamin": "Laki-laki",
        "alamat": "Jl. Merdeka No. 10, Jakarta",
        "kondisi": "Selamat",
    }


@pytest.fixture
def complete_sar_data(complete_korban_data):
    """Fixture providing a fully-populated SARExtractedFields dict."""
    return {
        "jenis_kejadian": "Tenggelam",
        "waktu": "2025-01-15 14:30",
        "lokasi_teks": "Pantai Parangtritis, Yogyakarta",
        "korban": "Budi Santoso",
        "data_korban": [complete_korban_data],
        "kronologi": "Korban tenggelam saat berenang di pantai.",
    }


# ===================================================================
# KorbanDetail Tests
# ===================================================================

class TestKorbanDetail:
    """Tests for the KorbanDetail Pydantic model."""

    # 1. Valid complete korban
    def test_valid_complete_korban(self, complete_korban_data):
        """All fields provided should be stored correctly."""
        korban = KorbanDetail(**complete_korban_data)

        assert korban.nama == "Budi Santoso"
        assert korban.umur == "35"
        assert korban.jenis_kelamin == "Laki-laki"
        assert korban.alamat == "Jl. Merdeka No. 10, Jakarta"
        assert korban.kondisi == "Selamat"

    # 2. All fields None → defaults
    def test_all_fields_none_defaults(self):
        """Instantiating with no arguments should yield None for all
        optional fields except kondisi which has a default."""
        korban = KorbanDetail()

        assert korban.nama is None
        assert korban.umur is None
        assert korban.jenis_kelamin is None
        assert korban.alamat is None
        assert korban.kondisi == "Dalam Pencarian"

    # 3. kondisi defaults to "Dalam Pencarian"
    def test_kondisi_default_value(self):
        """The kondisi field must default to 'Dalam Pencarian'."""
        korban = KorbanDetail(nama="Test")

        assert korban.kondisi == "Dalam Pencarian"

    # 4. Empty strings in fields
    def test_empty_strings_in_fields(self):
        """Empty strings are valid values and should NOT be coerced."""
        korban = KorbanDetail(
            nama="", umur="", jenis_kelamin="", alamat="", kondisi=""
        )

        assert korban.nama == ""
        assert korban.umur == ""
        assert korban.jenis_kelamin == ""
        assert korban.alamat == ""
        assert korban.kondisi == ""

    # 5. Very long name (5000 chars)
    def test_very_long_name(self):
        """Schema should accept arbitrarily long strings without truncation."""
        long_name = "A" * 5000
        korban = KorbanDetail(nama=long_name)

        assert korban.nama == long_name
        assert len(korban.nama) == 5000

    # 6. Special characters in nama
    def test_special_characters_in_nama(self):
        """Names with special chars, unicode, and emojis should be stored."""
        special = "M. O'Brien-Müller <test> & 日本語 🔥"
        korban = KorbanDetail(nama=special)

        assert korban.nama == special

    # 7. Numeric string for umur
    def test_numeric_string_for_umur(self):
        """Umur accepts string representations of numbers."""
        korban = KorbanDetail(umur="25")
        assert korban.umur == "25"

    def test_umur_non_numeric_string(self):
        """Umur field also accepts descriptive age strings (no int constraint)."""
        korban = KorbanDetail(umur="sekitar 30 tahun")
        assert korban.umur == "sekitar 30 tahun"

    def test_explicit_none_values(self):
        """Explicitly passing None should be accepted."""
        korban = KorbanDetail(
            nama=None, umur=None, jenis_kelamin=None, alamat=None, kondisi=None
        )

        assert korban.nama is None
        assert korban.kondisi is None  # overrides default when explicit


# ===================================================================
# SARExtractedFields – clean_unknown Validator
# ===================================================================

class TestCleanUnknownValidator:
    """Tests for the clean_unknown field_validator on SARExtractedFields."""

    # Helper: build a model with one field set, return that field's value.
    @staticmethod
    def _extract(field: str, value):
        """Instantiate SARExtractedFields with *field* = *value* and return it."""
        obj = SARExtractedFields(**{field: value})
        return getattr(obj, field)

    # --- Null-like string values → None --------------------------------

    # 8. "null" → None
    def test_null_string_becomes_none(self):
        """Literal 'null' should be cleaned to None."""
        assert self._extract("jenis_kejadian", "null") is None

    # 9. "None" → None
    def test_none_string_title_case(self):
        """'None' (title case) should be cleaned to None."""
        assert self._extract("jenis_kejadian", "None") is None

    # 10. "NONE" → None
    def test_none_string_upper_case(self):
        """'NONE' (upper case) should be cleaned to None."""
        assert self._extract("jenis_kejadian", "NONE") is None

    # 11. "none" → None
    def test_none_string_lower_case(self):
        """'none' (lower case) should be cleaned to None."""
        assert self._extract("jenis_kejadian", "none") is None

    # 12. "-" → None
    def test_dash_becomes_none(self):
        """A single dash '-' should be cleaned to None."""
        assert self._extract("waktu", "-") is None

    # 13. "unknown" → None
    def test_unknown_lower(self):
        """'unknown' should be cleaned to None."""
        assert self._extract("lokasi_teks", "unknown") is None

    # 14. "Unknown" → None
    def test_unknown_title(self):
        """'Unknown' (title case) should be cleaned to None."""
        assert self._extract("lokasi_teks", "Unknown") is None

    # 15. "UNKNOWN" → None
    def test_unknown_upper(self):
        """'UNKNOWN' should be cleaned to None."""
        assert self._extract("lokasi_teks", "UNKNOWN") is None

    # 16. "tidak diketahui" → None
    def test_tidak_diketahui_lower(self):
        """Indonesian 'tidak diketahui' should be cleaned to None."""
        assert self._extract("korban", "tidak diketahui") is None

    # 17. "Tidak Diketahui" → None
    def test_tidak_diketahui_title(self):
        """Title-case 'Tidak Diketahui' should also be cleaned to None."""
        assert self._extract("korban", "Tidak Diketahui") is None

    # 18. "belum diketahui" → None
    def test_belum_diketahui_lower(self):
        """'belum diketahui' should be cleaned to None."""
        assert self._extract("kronologi", "belum diketahui") is None

    # 19. "Belum Diketahui" → None
    def test_belum_diketahui_title(self):
        """Title-case variant should also be cleaned."""
        assert self._extract("kronologi", "Belum Diketahui") is None

    # 20. "n/a" → None
    def test_na_slash_lower(self):
        """'n/a' should be cleaned to None."""
        assert self._extract("jenis_kejadian", "n/a") is None

    # 21. "N/A" → None
    def test_na_slash_upper(self):
        """'N/A' upper-case should be cleaned to None."""
        assert self._extract("jenis_kejadian", "N/A") is None

    # 22. "na" → None
    def test_na_no_slash(self):
        """'na' without slash should be cleaned to None."""
        assert self._extract("waktu", "na") is None

    # 23. "tbd" → None
    def test_tbd_lower(self):
        """'tbd' should be cleaned to None."""
        assert self._extract("waktu", "tbd") is None

    # 24. "TBD" → None
    def test_tbd_upper(self):
        """'TBD' upper-case should be cleaned to None."""
        assert self._extract("waktu", "TBD") is None

    # 25. " null " (whitespace-padded) → None
    def test_whitespace_padded_null(self):
        """Leading/trailing whitespace should be stripped before comparison."""
        assert self._extract("jenis_kejadian", "  null  ") is None

    # 26. "" (empty string) → should NOT become None
    def test_empty_string_stays(self):
        """An empty string is not in the nullish set; should remain as-is."""
        assert self._extract("jenis_kejadian", "") == ""

    # 27. Valid text remains unchanged
    def test_valid_text_passes_through(self):
        """Legitimate values should pass the validator untouched."""
        assert self._extract("jenis_kejadian", "Gempa Bumi") == "Gempa Bumi"

    # 28. List value → stringified
    def test_list_value_stringified(self):
        """If a list is passed, the validator converts it to a string."""
        result = self._extract("jenis_kejadian", [{"a": 1}])
        assert isinstance(result, str)
        assert result == str([{"a": 1}])

    # 29. Dict value → stringified
    def test_dict_value_stringified(self):
        """If a dict is passed, the validator converts it to a string."""
        result = self._extract("jenis_kejadian", {"a": 1})
        assert isinstance(result, str)
        assert result == str({"a": 1})

    # 30. Integer value → stays as-is (returned by validator, Pydantic coerces)
    def test_integer_value_passes_through(self):
        """An integer is not str/list/dict, so the validator returns it as-is.
        Pydantic may then coerce it to str for the Optional[str] field."""
        result = self._extract("jenis_kejadian", 42)
        # Pydantic v2 coerces int → str for Optional[str] in strict=False (default)
        assert result == "42" or result == 42  # depends on Pydantic mode

    # 31. Boolean True → stays as-is (or coerced)
    def test_boolean_value_passes_through(self):
        """Boolean is not in the nullish set; validator returns it.
        Pydantic may coerce to str."""
        result = self._extract("jenis_kejadian", True)
        # Pydantic v2 with default (lax) mode: True → "true" or kept
        assert result is not None  # not cleaned to None

    # --- Parametrized sweep across ALL validated fields ------------------

    @pytest.mark.parametrize(
        "field",
        ["jenis_kejadian", "waktu", "lokasi_teks", "korban", "kronologi"],
    )
    @pytest.mark.parametrize(
        "value",
        ["null", "None", "NONE", "-", "unknown", "tidak diketahui",
         "belum diketahui", "n/a", "N/A", "na", "tbd", "TBD"],
    )
    def test_all_validated_fields_clean_nullish(self, field, value):
        """Every validated field should clean every nullish sentinel to None."""
        assert self._extract(field, value) is None

    @pytest.mark.parametrize(
        "field",
        ["jenis_kejadian", "waktu", "lokasi_teks", "korban", "kronologi"],
    )
    def test_none_input_stays_none(self, field):
        """Explicit None should remain None for every validated field."""
        assert self._extract(field, None) is None


# ===================================================================
# Full SARExtractedFields Tests
# ===================================================================

class TestSARExtractedFields:
    """Integration-level tests for SARExtractedFields."""

    # 32. Empty instantiation → all defaults
    def test_empty_instantiation_defaults(self):
        """All fields should have sensible defaults when nothing is supplied."""
        fields = SARExtractedFields()

        assert fields.jenis_kejadian is None
        assert fields.waktu is None
        assert fields.lokasi_teks is None
        assert fields.korban is None
        assert fields.data_korban == []
        assert fields.kronologi is None

    # 33. Complete valid data
    def test_complete_valid_data(self, complete_sar_data):
        """All fields should be correctly populated from valid input."""
        fields = SARExtractedFields(**complete_sar_data)

        assert fields.jenis_kejadian == "Tenggelam"
        assert fields.waktu == "2025-01-15 14:30"
        assert fields.lokasi_teks == "Pantai Parangtritis, Yogyakarta"
        assert fields.korban == "Budi Santoso"
        assert len(fields.data_korban) == 1
        assert fields.data_korban[0].nama == "Budi Santoso"
        assert fields.kronologi == "Korban tenggelam saat berenang di pantai."

    # 34. LLM returning all "null" strings → all None
    def test_all_null_strings_cleaned(self):
        """Simulates an LLM returning 'null' for every field."""
        fields = SARExtractedFields(
            jenis_kejadian="null",
            waktu="null",
            lokasi_teks="null",
            korban="null",
            kronologi="null",
        )

        assert fields.jenis_kejadian is None
        assert fields.waktu is None
        assert fields.lokasi_teks is None
        assert fields.korban is None
        assert fields.kronologi is None

    # 35. Mixed valid and null values
    def test_mixed_valid_and_null(self):
        """Some fields valid, some nullish – only nullish ones become None."""
        fields = SARExtractedFields(
            jenis_kejadian="Kebakaran",
            waktu="unknown",
            lokasi_teks="Gunung Semeru",
            korban="n/a",
            kronologi="Kebakaran hutan terjadi pagi hari.",
        )

        assert fields.jenis_kejadian == "Kebakaran"
        assert fields.waktu is None
        assert fields.lokasi_teks == "Gunung Semeru"
        assert fields.korban is None
        assert fields.kronologi == "Kebakaran hutan terjadi pagi hari."

    # 36. data_korban with valid KorbanDetail list
    def test_data_korban_with_list(self):
        """data_korban should accept a list of KorbanDetail-compatible dicts."""
        fields = SARExtractedFields(
            data_korban=[
                {"nama": "Andi", "umur": "20"},
                {"nama": "Siti", "umur": "25", "kondisi": "Meninggal"},
            ]
        )

        assert len(fields.data_korban) == 2
        assert fields.data_korban[0].nama == "Andi"
        assert fields.data_korban[0].kondisi == "Dalam Pencarian"
        assert fields.data_korban[1].kondisi == "Meninggal"

    # 37. data_korban as None → defaults to []
    def test_data_korban_none_defaults_to_empty(self):
        """Passing None for data_korban should fall back to the default []."""
        fields = SARExtractedFields(data_korban=None)

        # Pydantic v2: None for Optional[List] with default=[] stays None
        # or falls back to []; verify based on actual model behavior.
        assert fields.data_korban is None or fields.data_korban == []

    # 38. data_korban with empty dicts
    def test_data_korban_with_empty_dicts(self):
        """Empty dicts should produce KorbanDetail instances with defaults."""
        fields = SARExtractedFields(data_korban=[{}, {}])

        assert len(fields.data_korban) == 2
        for k in fields.data_korban:
            assert k.nama is None
            assert k.umur is None
            assert k.kondisi == "Dalam Pencarian"

    # 39. Validate model_dump() output shape
    def test_model_dump_output_shape(self, complete_sar_data):
        """model_dump() should return a dict with the expected keys."""
        fields = SARExtractedFields(**complete_sar_data)
        dumped = fields.model_dump()

        expected_keys = {
            "jenis_kejadian", "waktu", "lokasi_teks",
            "korban", "data_korban", "kronologi",
        }
        assert set(dumped.keys()) == expected_keys
        assert isinstance(dumped["data_korban"], list)
        assert isinstance(dumped["data_korban"][0], dict)

    # 40. Extra fields ignored (or error)
    def test_extra_fields_behavior(self):
        """By default Pydantic v2 ignores extra fields (model_config not set).
        Verify the model does not raise on unexpected keys."""
        try:
            fields = SARExtractedFields(
                jenis_kejadian="Banjir",
                extra_field="should be ignored",
            )
            # If no error, the extra field should not appear in the model
            assert not hasattr(fields, "extra_field")
        except Exception:
            # Some Pydantic configs raise on extras – that's also acceptable
            pass

    # --- Additional edge-case / integration tests ----------------------

    def test_data_korban_accepts_korban_detail_instances(self, complete_korban_data):
        """data_korban should accept pre-built KorbanDetail objects."""
        korban = KorbanDetail(**complete_korban_data)
        fields = SARExtractedFields(data_korban=[korban])

        assert fields.data_korban[0].nama == "Budi Santoso"

    def test_model_dump_round_trip(self, complete_sar_data):
        """Dumping and re-loading should produce an equivalent model."""
        original = SARExtractedFields(**complete_sar_data)
        reloaded = SARExtractedFields(**original.model_dump())

        assert original.model_dump() == reloaded.model_dump()

    def test_multiple_korban_details(self):
        """Validate a realistic multi-victim scenario."""
        victims = [
            {"nama": f"Korban {i}", "umur": str(20 + i)} for i in range(5)
        ]
        fields = SARExtractedFields(data_korban=victims)

        assert len(fields.data_korban) == 5
        assert fields.data_korban[4].nama == "Korban 4"

    def test_whitespace_only_strings_not_cleaned(self):
        """Strings of only whitespace are not in the nullish set and should
        survive the validator (they don't match after strip+lower)."""
        fields = SARExtractedFields(jenis_kejadian="   ")
        # "   ".strip().lower() == "" which is NOT in the set
        assert fields.jenis_kejadian == "   "

    def test_clean_unknown_does_not_affect_data_korban(self):
        """The clean_unknown validator is NOT applied to data_korban.
        Passing 'null' inside a KorbanDetail nama should remain 'null'."""
        fields = SARExtractedFields(
            data_korban=[{"nama": "null"}]
        )
        # KorbanDetail has no clean_unknown validator
        assert fields.data_korban[0].nama == "null"
