"""
Comprehensive tests for ValidatorRouter.validate_extracted_data().

Covers:
- Happy-path scenarios (all required fields present)
- Missing-field priority (single and multiple missing fields)
- Destructive / edge-case inputs (empty, None, whitespace, falsy, unicode, etc.)
"""

import pytest
from app.engine.validator_router import ValidatorRouter

validator_router = ValidatorRouter()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def router():
    """Return a fresh ValidatorRouter instance for each test."""
    return ValidatorRouter()


@pytest.fixture
def complete_data():
    """Minimal valid data dict with every required field populated."""
    return {
        "jenis_kejadian": "Banjir",
        "waktu": "2025-01-15 08:00",
        "lokasi_teks": "Jakarta Selatan",
        "data_korban": [{"nama": "Budi", "usia": 30}],
    }


# ===================================================================
# HAPPY PATH
# ===================================================================

class TestHappyPath:
    """All required fields are present → missing list must be empty."""

    def test_all_fields_present(self, router, complete_data):
        """1. All fields present → empty missing list."""
        result = router.validate_extracted_data(complete_data)
        assert result == []

    def test_all_fields_present_with_extra_fields(self, router, complete_data):
        """2. Extra fields should be silently ignored."""
        complete_data["catatan_tambahan"] = "Some note"
        complete_data["prioritas"] = "Tinggi"
        result = router.validate_extracted_data(complete_data)
        assert result == []

    def test_data_korban_as_list_of_dicts(self, router):
        """3. data_korban as list with dicts → no korban missing."""
        data = {
            "jenis_kejadian": "Gempa",
            "waktu": "2025-03-01",
            "lokasi_teks": "Bandung",
            "data_korban": [{"nama": "Andi"}],
        }
        assert router.validate_extracted_data(data) == []

    def test_korban_as_string(self, router):
        """4. korban supplied as a plain string → no korban missing."""
        data = {
            "jenis_kejadian": "Kebakaran",
            "waktu": "2025-04-10",
            "lokasi_teks": "Surabaya",
            "korban": "2 orang terluka",
        }
        assert router.validate_extracted_data(data) == []

    def test_both_data_korban_and_korban_present(self, router):
        """5. Both korban keys present → still valid, no missing."""
        data = {
            "jenis_kejadian": "Longsor",
            "waktu": "2025-05-20",
            "lokasi_teks": "Bogor",
            "data_korban": [{"nama": "Siti"}],
            "korban": "1 orang",
        }
        assert router.validate_extracted_data(data) == []


# ===================================================================
# MISSING FIELD PRIORITY
# ===================================================================

class TestMissingFieldPriority:
    """Each required field missing individually, then combinations."""

    def test_only_jenis_kejadian_missing(self, router):
        """6. Only jenis_kejadian missing."""
        data = {
            "waktu": "2025-01-01",
            "lokasi_teks": "Medan",
            "data_korban": [{"nama": "X"}],
        }
        missing = router.validate_extracted_data(data)
        assert missing == ["jenis_kejadian"]

    def test_only_waktu_missing(self, router):
        """7. Only waktu missing."""
        data = {
            "jenis_kejadian": "Banjir",
            "lokasi_teks": "Semarang",
            "data_korban": [{"nama": "Y"}],
        }
        missing = router.validate_extracted_data(data)
        assert missing == ["waktu"]

    def test_only_lokasi_teks_missing(self, router):
        """8. Only lokasi_teks missing."""
        data = {
            "jenis_kejadian": "Banjir",
            "waktu": "2025-06-01",
            "data_korban": [{"nama": "Z"}],
        }
        missing = router.validate_extracted_data(data)
        assert missing == ["lokasi_teks"]

    def test_only_korban_missing(self, router):
        """9. Both data_korban and korban absent → korban missing."""
        data = {
            "jenis_kejadian": "Banjir",
            "waktu": "2025-07-01",
            "lokasi_teks": "Palembang",
        }
        missing = router.validate_extracted_data(data)
        assert missing == ["korban"]

    def test_multiple_fields_missing(self, router):
        """10. Multiple fields missing – verify all are returned."""
        data = {
            "jenis_kejadian": "Gempa",
            # waktu missing
            # lokasi_teks missing
            "data_korban": [{"nama": "A"}],
        }
        missing = router.validate_extracted_data(data)
        assert "waktu" in missing
        assert "lokasi_teks" in missing
        assert len(missing) == 2

    def test_all_fields_missing(self, router):
        """11. Completely empty payload → all four sentinel fields missing."""
        data = {"some_other_key": "value"}
        missing = router.validate_extracted_data(data)
        assert set(missing) == {"jenis_kejadian", "waktu", "lokasi_teks", "korban"}


# ===================================================================
# NEGATIVE / EDGE CASES (DESTRUCTIVE)
# ===================================================================

class TestEdgeCases:
    """Boundary, falsy, and adversarial inputs."""

    def test_empty_dict(self, router):
        """12. Empty dict → all fields reported missing."""
        missing = router.validate_extracted_data({})
        assert set(missing) == {"jenis_kejadian", "waktu", "lokasi_teks", "korban"}

    def test_none_values_for_all_fields(self, router):
        """13. All fields explicitly set to None → all missing."""
        data = {
            "jenis_kejadian": None,
            "waktu": None,
            "lokasi_teks": None,
            "data_korban": None,
            "korban": None,
        }
        missing = router.validate_extracted_data(data)
        assert set(missing) == {"jenis_kejadian", "waktu", "lokasi_teks", "korban"}

    def test_empty_string_values(self, router):
        """14. Empty strings ('') treated as missing."""
        data = {
            "jenis_kejadian": "",
            "waktu": "",
            "lokasi_teks": "",
            "data_korban": [],
            "korban": "",
        }
        missing = router.validate_extracted_data(data)
        assert set(missing) == {"jenis_kejadian", "waktu", "lokasi_teks", "korban"}

    def test_whitespace_only_strings(self, router):
        """15. Whitespace-only strings treated as missing."""
        data = {
            "jenis_kejadian": "   ",
            "waktu": "\t\t",
            "lokasi_teks": "  \n  ",
            "data_korban": [{"nama": "Valid"}],
        }
        missing = router.validate_extracted_data(data)
        assert "jenis_kejadian" in missing
        assert "waktu" in missing
        assert "lokasi_teks" in missing
        assert "korban" not in missing

    def test_empty_list_for_data_korban(self, router):
        """16. data_korban as empty list [] is falsy → korban missing."""
        data = {
            "jenis_kejadian": "Banjir",
            "waktu": "2025-01-01",
            "lokasi_teks": "Jakarta",
            "data_korban": [],
        }
        missing = router.validate_extracted_data(data)
        assert "korban" in missing

    def test_data_korban_with_empty_dicts(self, router):
        """17. data_korban = [{}] is truthy → korban NOT missing."""
        data = {
            "jenis_kejadian": "Banjir",
            "waktu": "2025-01-01",
            "lokasi_teks": "Jakarta",
            "data_korban": [{}],
        }
        missing = router.validate_extracted_data(data)
        assert "korban" not in missing

    def test_zero_values(self, router):
        """18. Zero (0) is a valid value, not treated as missing."""
        data = {
            "jenis_kejadian": 0,
            "waktu": 0,
            "lokasi_teks": 0,
            "data_korban": [{"nama": "Ok"}],
        }
        missing = router.validate_extracted_data(data)
        assert "jenis_kejadian" not in missing
        assert len(missing) == 0

    def test_false_values(self, router):
        """19. False is a valid boolean value, not treated as missing."""
        data = {
            "jenis_kejadian": False,
            "waktu": False,
            "lokasi_teks": False,
            "data_korban": [{"nama": "Ok"}],
        }
        missing = router.validate_extracted_data(data)
        assert "jenis_kejadian" not in missing
        assert len(missing) == 0

    def test_very_long_strings(self, router):
        """20. Very long strings (10 000 chars) are still valid."""
        long_str = "A" * 10_000
        data = {
            "jenis_kejadian": long_str,
            "waktu": long_str,
            "lokasi_teks": long_str,
            "data_korban": [{"nama": long_str}],
        }
        assert router.validate_extracted_data(data) == []

    def test_special_characters_sql_injection(self, router):
        """21. SQL-injection-style strings are still valid string values."""
        data = {
            "jenis_kejadian": "'; DROP TABLE events; --",
            "waktu": "1 OR 1=1",
            "lokasi_teks": "<script>alert('xss')</script>",
            "data_korban": [{"nama": "Robert'); DROP TABLE students;--"}],
        }
        assert router.validate_extracted_data(data) == []

    def test_unicode_and_emoji(self, router):
        """22. Unicode / emoji should be accepted as valid content."""
        data = {
            "jenis_kejadian": "Gempa 🌍",
            "waktu": "2025年01月01日",
            "lokasi_teks": "Ñoño — Ünïcödé",
            "data_korban": [{"nama": "🎭 Tëst"}],
        }
        assert router.validate_extracted_data(data) == []

    def test_newlines_and_tabs_non_empty(self, router):
        """23. Strings with mixed whitespace + real content are valid."""
        data = {
            "jenis_kejadian": "\tBanjir\n",
            "waktu": "2025-01-01\n",
            "lokasi_teks": "\n\tJakarta\t",
            "data_korban": [{"nama": "Ok"}],
        }
        assert router.validate_extracted_data(data) == []

    def test_unexpected_field_names_only(self, router):
        """24. Only unexpected field names → all required fields missing."""
        data = {
            "tanggal": "2025-01-01",
            "tipe": "Banjir",
            "alamat": "Jakarta",
            "jumlah_korban": 5,
        }
        missing = router.validate_extracted_data(data)
        assert set(missing) == {"jenis_kejadian", "waktu", "lokasi_teks", "korban"}

    def test_data_korban_as_string(self, router):
        """25. data_korban as a plain non-empty string is truthy → korban valid."""
        data = {
            "jenis_kejadian": "Banjir",
            "waktu": "2025-01-01",
            "lokasi_teks": "Jakarta",
            "data_korban": "2 orang luka ringan",
        }
        assert router.validate_extracted_data(data) == []

    def test_numeric_values_for_core_fields(self, router):
        """26. Non-zero numeric values are truthy → fields NOT missing."""
        data = {
            "jenis_kejadian": 42,
            "waktu": 1700000000,
            "lokasi_teks": 99.9,
            "data_korban": [{"nama": "Ok"}],
        }
        # Non-zero numbers are truthy; the isinstance(val, str) guard
        # prevents the .strip() check from running, so they pass.
        assert router.validate_extracted_data(data) == []

    def test_nested_dict_values(self, router):
        """27. Nested dicts are truthy → fields NOT missing."""
        data = {
            "jenis_kejadian": {"type": "Banjir"},
            "waktu": {"date": "2025-01-01"},
            "lokasi_teks": {"kota": "Jakarta"},
            "data_korban": [{"nama": "Ok"}],
        }
        assert router.validate_extracted_data(data) == []

    def test_none_input_raises(self, router):
        """28. Passing None instead of a dict should raise AttributeError."""
        with pytest.raises(AttributeError):
            router.validate_extracted_data(None)



# ===================================================================
# REQUIRED_CORE_FIELDS CONFIGURATION
# ===================================================================

class TestRequiredCoreFields:
    """Validate the class-level field list hasn't drifted."""

    def test_required_core_fields_content(self):
        """REQUIRED_CORE_FIELDS must contain exactly the three expected keys."""
        assert ValidatorRouter.REQUIRED_CORE_FIELDS == [
            "jenis_kejadian",
            "waktu",
            "lokasi_teks",
        ]

    def test_required_core_fields_is_list(self):
        """REQUIRED_CORE_FIELDS should be a list (ordered, mutable)."""
        assert isinstance(ValidatorRouter.REQUIRED_CORE_FIELDS, list)


# ===================================================================
# RETURN TYPE & ORDERING
# ===================================================================

class TestReturnContract:
    """Ensure the return value satisfies the documented contract."""

    def test_returns_list(self, router, complete_data):
        """Return type is always a list."""
        result = router.validate_extracted_data(complete_data)
        assert isinstance(result, list)

    def test_missing_order_matches_field_order(self, router):
        """Missing core fields appear in REQUIRED_CORE_FIELDS order, korban last."""
        data = {}
        missing = router.validate_extracted_data(data)
        # Core fields should come before "korban"
        assert missing[-1] == "korban"
        core_missing = missing[:-1]
        assert core_missing == ValidatorRouter.REQUIRED_CORE_FIELDS

    def test_no_duplicates_in_result(self, router):
        """The missing list must not contain duplicates."""
        data = {}
        missing = router.validate_extracted_data(data)
        assert len(missing) == len(set(missing))
