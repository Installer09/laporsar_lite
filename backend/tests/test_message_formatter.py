"""
Comprehensive tests for MessageFormatterService aligned with production templates and constraints.
"""

import time
import pytest
from datetime import datetime

from app.services.message_formatter import (
    message_formatter,
    MessageFormatterService,
    DEFAULT_TEMPLATE,
)

@pytest.fixture
def formatter():
    """Return a fresh MessageFormatterService instance for each test."""
    return MessageFormatterService()

@pytest.fixture
def complete_data():
    """Return a fully-populated incident data dict."""
    return {
        "jenis_kejadian": "Banjir",
        "waktu": "2026-05-24 10:00 WIB",
        "lokasi_teks": "Sungai Ciliwung, Jakarta",
        "kronologi": "Hujan deras menyebabkan banjir.",
        "data_korban": [
            {
                "nama": "Budi",
                "umur": "30",
                "jenis_kelamin": "L",
                "alamat": "Jl. Merdeka No. 1",
                "ciri_ciri": "Tato di lengan",
            },
            {
                "nama": "Siti",
                "umur": "25",
                "jenis_kelamin": "P",
                "alamat": "Jl. Sudirman No. 5",
                "ciri_ciri": "Kerudung hitam",
            },
        ],
    }

class TestRenderNullSafety:
    """Tests ensuring render() gracefully handles missing / blank data."""

    def test_render_empty_dict_all_belum_diketahui(self, formatter):
        """1. render() with empty dict → every field replaced safely."""
        result = formatter.render(DEFAULT_TEMPLATE, {})
        assert "Belum Diketahui" in result
        # None of the raw placeholders should survive
        for placeholder in [
            "{{DETAIL_JUDUL}}",
            "{{WAKTU_KEJADIAN}}",
            "{{LOKASI_KEJADIAN}}",
            "{{JUMLAH_KORBAN_TOTAL}}",
            "{{KRONOLOGI}}",
        ]:
            assert placeholder not in result

    def test_render_none_values_all_belum_diketahui(self, formatter):
        """2. render() with explicit None values."""
        data = {
            "jenis_kejadian": None,
            "waktu": None,
            "lokasi_teks": None,
            "kronologi": None,
            "data_korban": None,
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "Belum Diketahui" in result
        assert "{{DETAIL_JUDUL}}" not in result

    def test_render_empty_strings_all_belum_diketahui(self, formatter):
        """3. render() with empty strings → treated as missing."""
        data = {
            "jenis_kejadian": "",
            "waktu": "",
            "lokasi_teks": "",
            "kronologi": "",
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "Belum Diketahui" in result
        for placeholder in ["{{DETAIL_JUDUL}}", "{{WAKTU_KEJADIAN}}"]:
            assert placeholder not in result

    def test_render_whitespace_strings_all_belum_diketahui(self, formatter):
        """4. render() with whitespace-only strings."""
        data = {
            "jenis_kejadian": "   ",
            "waktu": "\t\n",
            "lokasi_teks": "  \n  ",
            "kronologi": "   ",
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "Belum Diketahui" in result

    def test_render_template_none_uses_default(self, formatter):
        """5. render() with template=None → falls back to dynamic templates."""
        data = {"jenis_kejadian": "Gempa"}
        result = formatter.render(None, data)
        assert "INFO AWAL" in result
        assert "GEMPA" in result

class TestFormatKorban:
    """Tests for the format_korban() helper method."""

    def test_empty_list_returns_placeholder(self, formatter):
        """6. Empty list → blank skeleton"""
        expected = (
            "*Korban ke-1:*\n"
            "- Nama : \n"
            "- Alamat : \n"
            "- Ciri-ciri:"
        )
        assert formatter.format_korban([]) == expected

    def test_none_input_returns_placeholder(self, formatter):
        """7. None input → blank skeleton"""
        expected = (
            "*Korban ke-1:*\n"
            "- Nama : \n"
            "- Alamat : \n"
            "- Ciri-ciri:"
        )
        assert formatter.format_korban(None) == expected

    def test_single_korban_dict_all_fields(self, formatter):
        """8. Single korban dict with every field populated."""
        korban = [
            {
                "nama": "Andi",
                "umur": "28",
                "jenis_kelamin": "L",
                "alamat": "Jl. Pahlawan",
                "ciri_ciri": "Tahi lalat",
            }
        ]
        result = formatter.format_korban(korban)
        assert "- Nama : Andi (L/28 Thn)" in result
        assert "- Alamat : Jl. Pahlawan" in result
        assert "- Ciri-ciri: Tahi lalat" in result

    def test_multiple_korban_dicts(self, formatter):
        """9. Multiple korban dicts → correctly formatted list."""
        korban = [
            {"nama": "A", "umur": "20", "jenis_kelamin": "L", "alamat": "X", "ciri_ciri": "-"},
            {"nama": "B", "umur": "25", "jenis_kelamin": "P", "alamat": "Y", "ciri_ciri": "-"},
            {"nama": "C", "umur": "30", "jenis_kelamin": "L", "alamat": "Z", "ciri_ciri": "-"},
        ]
        result = formatter.format_korban(korban)
        assert "- Nama : A (L/20 Thn)" in result
        assert "- Nama : B (P/25 Thn)" in result
        assert "- Nama : C (L/30 Thn)" in result

    def test_korban_dict_missing_fields_defaults_dash(self, formatter):
        """10. Korban dict with missing keys → fields are empty."""
        korban = [{"nama": "Dewi"}]  # only nama supplied
        result = formatter.format_korban(korban)
        assert "- Nama : Dewi" in result
        assert "- Alamat : " in result
        assert "- Ciri-ciri: " in result

    def test_mixed_list_dicts_and_strings(self, formatter):
        """11. Mixed list containing both dicts and plain strings."""
        korban = [
            {"nama": "Fani", "umur": "22", "jenis_kelamin": "P", "alamat": "Bandung", "ciri_ciri": "-"},
            "Korban tidak teridentifikasi",
        ]
        result = formatter.format_korban(korban)
        assert "- Nama : Fani (P/22 Thn)" in result
        assert "- Korban tidak teridentifikasi" in result

    def test_list_with_empty_dicts(self, formatter):
        """12. List containing empty dicts → all fields are empty."""
        korban = [{}]
        result = formatter.format_korban(korban)
        assert "- Nama : " in result
        assert "- Alamat : " in result
        assert "- Ciri-ciri: " in result

    def test_stringified_json_list_treated_as_string(self, formatter):
        """13. If a list item is a JSON string (not dict), it is rendered as-is."""
        import json
        raw = json.dumps({"nama": "Ghost"})
        korban = [raw]
        result = formatter.format_korban(korban)
        assert raw in result

class TestRenderValidData:
    """Tests for render() when given complete / partial valid data."""

    def test_complete_data_all_placeholders_replaced(self, formatter, complete_data):
        """14. Complete data → every placeholder replaced with real values."""
        result = formatter.render(DEFAULT_TEMPLATE, complete_data)
        assert "0524 1000 G" in result
        assert "Sungai Ciliwung" in result
        assert "Hujan deras" in result
        assert "Budi" in result
        assert "Siti" in result

    def test_partial_data_mix_values_and_defaults(self, formatter):
        """15. Partial data → supplied values present, rest default."""
        data = {
            "jenis_kejadian": "Longsor",
            "waktu": None,
            "lokasi_teks": "",
            "kronologi": "Tanah longsor di lereng.",
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "LONGSOR" in result.upper()
        assert "Tanah longsor di lereng." in result
        assert "Belum Diketahui" in result

    def test_custom_template_with_custom_placeholders(self, formatter):
        """16. Custom template using standard placeholders → correctly rendered."""
        custom = "Kejadian: {{DETAIL_JUDUL}}\nKorban: {{DATA_KORBAN}}"
        data = {
            "jenis_kejadian": "Kebakaran",
            "lokasi_teks": "Gudang ABC",
            "data_korban": [{"nama": "Rudi", "umur": "40", "jenis_kelamin": "L", "alamat": "Surabaya", "ciri_ciri": "-"}],
        }
        result = formatter.render(custom, data)
        assert "KEBAKARAN DI GUDANG ABC" in result.upper()
        assert "Rudi" in result

    def test_data_korban_multiple_entries_correct_count(self, formatter):
        """17. data_korban with multiple entries reflects len()."""
        data = {
            "data_korban": [
                {"nama": "A"},
                {"nama": "B"},
                {"nama": "C"},
                {"nama": "D"},
            ],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "4" in result

class TestDestructiveEdgeCases:
    """Stress-tests and edge cases to verify robustness."""

    def test_very_long_strings_in_fields(self, formatter):
        """18. Very long strings in fields → no crash, value present."""
        long_str = "A" * 10_000
        data = {
            "jenis_kejadian": long_str,
            "waktu": long_str,
            "lokasi_teks": long_str,
            "kronologi": long_str,
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert long_str in result

    def test_special_characters_telegram_markdown(self, formatter):
        """19. Special Telegram markdown characters (*, _, `) in field values."""
        data = {
            "jenis_kejadian": "*Bold* _italic_ `code`",
            "waktu": "2026-05-24",
            "lokasi_teks": "Jl. *Test* No. 1",
            "kronologi": "Kejadian `penting` terjadi.",
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "*BOLD* _ITALIC_ `CODE`" in result.upper()

    def test_html_injection_in_field_values(self, formatter):
        """20. HTML / script injection strings are rendered verbatim."""
        data = {
            "jenis_kejadian": '<script>alert("xss")</script>',
            "waktu": "<b>Bold</b>",
            "lokasi_teks": '<img src="x" onerror="alert(1)">',
            "kronologi": "Normal text",
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert '<SCRIPT>ALERT("XSS")</SCRIPT>' in result.upper()

    def test_unicode_and_emoji_in_values(self, formatter):
        """21. Unicode / emoji characters in field values."""
        data = {
            "jenis_kejadian": "Gempa 🌍",
            "waktu": "пятница",
            "lokasi_teks": "東京タワー",
            "kronologi": "مرحبا بالعالم",
            "data_korban": [
                {"nama": "José 🎉", "umur": "28", "jenis_kelamin": "L", "alamat": "Ñoño", "ciri_ciri": "Kumis"}
            ],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "Gempa 🌍" in result
        assert "東京タワー" in result
        assert "José 🎉" in result

    def test_newlines_in_field_values(self, formatter):
        """22. Newline characters embedded in field values."""
        data = {
            "jenis_kejadian": "Line1\nLine2",
            "waktu": "2026\n05\n24",
            "lokasi_teks": "Jakarta",
            "kronologi": "Step1\nStep2\nStep3",
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "Line1\nLine2" in result

    def test_data_korban_none_not_list(self, formatter):
        """23. data_korban as None handled gracefully."""
        data = {"data_korban": None}
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "0" in result
        assert "Korban ke-1" in result

    def test_data_korban_string_instead_of_list(self, formatter):
        """24. data_korban as a string instead of list handled gracefully."""
        data = {"data_korban": "some string"}
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "some string" in result

    def test_numeric_values_in_string_fields(self, formatter):
        """25. Numeric values passed as field values."""
        data = {
            "jenis_kejadian": 0,
            "waktu": -1,
            "lokasi_teks": 42,
            "kronologi": 3.14,
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "Belum Diketahui" in result

    def test_boolean_values_in_fields(self, formatter):
        """26. Boolean values in data fields."""
        data = {
            "jenis_kejadian": True,
            "waktu": False,
            "lokasi_teks": True,
            "kronologi": False,
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "Belum Diketahui" in result

    def test_nested_dict_in_korban_fields(self, formatter):
        """27. Nested dict as a korban field value."""
        korban = [
            {
                "nama": {"first": "Budi", "last": "Santoso"},
                "umur": "30",
                "jenis_kelamin": "L",
                "alamat": "Jakarta",
                "ciri_ciri": "-",
            }
        ]
        result = formatter.format_korban(korban)
        assert "first" in result
        assert "Budi" in result

    def test_sql_injection_strings_in_fields(self, formatter):
        """28. SQL injection strings treated as plain text."""
        data = {
            "jenis_kejadian": "'; DROP TABLE users; --",
            "waktu": "1 OR 1=1",
            "lokasi_teks": "Robert'); DROP TABLE students;--",
            "kronologi": "SELECT * FROM incidents",
            "data_korban": [],
        }
        result = formatter.render(DEFAULT_TEMPLATE, data)
        assert "DROP TABLE USERS" in result.upper()

    def test_template_with_no_placeholders_unchanged(self, formatter):
        """29. Template containing no placeholders returned unchanged."""
        template = "This is a static message with no placeholders."
        result = formatter.render(template, {"jenis_kejadian": "Gempa"})
        assert result == "This is a static message with no placeholders."

    def test_template_with_duplicate_placeholders(self, formatter):
        """30. Template with repeated placeholders replaced."""
        template = "{{DETAIL_JUDUL}} dan {{DETAIL_JUDUL}} terjadi."
        data = {
            "jenis_kejadian": "Banjir",
            "lokasi_teks": "Bandung",
            "data_korban": [],
        }
        result = formatter.render(template, data)
        assert result.count("BANJIR DI BANDUNG KABUPATEN NATUNA") == 2

    def test_very_large_data_korban_list_performance(self, formatter):
        """31. 1 000 korban entries completes quickly."""
        korban = [
            {"nama": f"Korban-{i}", "umur": str(20 + i % 50), "jenis_kelamin": "L", "alamat": f"Alamat-{i}", "ciri_ciri": "-"}
            for i in range(1_000)
        ]
        data = {"data_korban": korban}

        start = time.monotonic()
        result = formatter.render(DEFAULT_TEMPLATE, data)
        elapsed = time.monotonic() - start

        assert "1000" in result
        assert "Korban-0" in result
        assert "Korban-999" in result
        assert elapsed < 2.0

class TestAdditionalEdgeCases:
    """Extra tests to reinforce coverage."""

    def test_module_level_singleton_exists(self):
        """32. The module-level `message_formatter` singleton is a valid instance."""
        assert isinstance(message_formatter, MessageFormatterService)

    def test_default_template_contains_all_placeholders(self):
        """33. DEFAULT_TEMPLATE includes every expected placeholder."""
        expected = [
            "{{DETAIL_JUDUL}}",
            "{{WAKTU_KEJADIAN}}",
            "{{LOKASI_KEJADIAN}}",
            "{{JUMLAH_KORBAN_TOTAL}}",
            "{{KRONOLOGI}}",
            "{{DATA_KORBAN}}",
        ]
        for ph in expected:
            assert ph in DEFAULT_TEMPLATE, f"Missing placeholder {ph} in DEFAULT_TEMPLATE"

    def test_render_preserves_template_decorators(self, formatter, complete_data):
        """34. render() preserves decorators from template."""
        result = formatter.render(DEFAULT_TEMPLATE, complete_data)
        assert "*" in result
        assert ">" in result
