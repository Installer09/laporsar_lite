"""
Comprehensive tests for app.engine.state_manager.StateManager.

Covers:
  - Happy-path state transitions (single missing field)
  - Priority ordering when multiple fields are missing
  - State constant string values
  - Edge cases (empty list, duplicates, case sensitivity, etc.)
  - Class-level design invariants
"""

import pytest
from app.engine.state_manager import StateManager


# ---------------------------------------------------------------------------
# Fixture – instantiate once per test for isolation
# ---------------------------------------------------------------------------

@pytest.fixture
def sm():
    """Provide a fresh StateManager instance for each test."""
    return StateManager()


# =========================================================================
# HAPPY PATH – single missing field → expected next state
# =========================================================================

class TestHappyPath:
    """Tests where exactly one field drives the transition."""

    def test_no_missing_fields_returns_confirming(self, sm):
        """When nothing is missing the conversation should move to confirmation."""
        result = sm.get_next_state("AWAITING_REPORT", [])
        assert result == StateManager.STATE_CONFIRMING

    def test_waktu_missing_returns_awaiting_waktu(self, sm):
        """Missing 'waktu' should ask for the time."""
        result = sm.get_next_state("AWAITING_REPORT", ["waktu"])
        assert result == StateManager.STATE_AWAITING_WAKTU

    def test_lokasi_teks_missing_returns_awaiting_lokasi(self, sm):
        """Missing 'lokasi_teks' should ask for the location."""
        result = sm.get_next_state("AWAITING_REPORT", ["lokasi_teks"])
        assert result == StateManager.STATE_AWAITING_LOKASI

    def test_korban_missing_returns_awaiting_korban(self, sm):
        """Missing 'korban' should ask for victim info."""
        result = sm.get_next_state("AWAITING_REPORT", ["korban"])
        assert result == StateManager.STATE_AWAITING_KORBAN

    def test_data_korban_missing_returns_awaiting_korban(self, sm):
        """Missing 'data_korban' should also ask for victim info (alternate key)."""
        result = sm.get_next_state("AWAITING_REPORT", ["data_korban"])
        assert result == StateManager.STATE_AWAITING_KORBAN

    def test_unknown_field_returns_confirming(self, sm):
        """An unrecognised field name falls through to CONFIRMING (no special branch)."""
        result = sm.get_next_state("AWAITING_REPORT", ["some_unknown_field"])
        assert result == StateManager.STATE_CONFIRMING


# =========================================================================
# PRIORITY TESTS – multiple missing fields, order matters
# =========================================================================

class TestPriorityOrder:
    """Verify that waktu > lokasi_teks > korban/data_korban priority is respected."""

    def test_waktu_beats_lokasi(self, sm):
        """waktu has higher priority than lokasi_teks."""
        result = sm.get_next_state("AWAITING_REPORT", ["lokasi_teks", "waktu"])
        assert result == StateManager.STATE_AWAITING_WAKTU

    def test_waktu_beats_korban(self, sm):
        """waktu has higher priority than korban."""
        result = sm.get_next_state("AWAITING_REPORT", ["korban", "waktu"])
        assert result == StateManager.STATE_AWAITING_WAKTU

    def test_lokasi_beats_korban(self, sm):
        """lokasi_teks has higher priority than korban."""
        result = sm.get_next_state("AWAITING_REPORT", ["korban", "lokasi_teks"])
        assert result == StateManager.STATE_AWAITING_LOKASI

    def test_all_three_missing_returns_waktu(self, sm):
        """When all three key fields are missing, waktu takes priority."""
        result = sm.get_next_state("AWAITING_REPORT", ["korban", "lokasi_teks", "waktu"])
        assert result == StateManager.STATE_AWAITING_WAKTU

    def test_jenis_kejadian_only_returns_confirming(self, sm):
        """'jenis_kejadian' alone is not a tracked missing field → CONFIRMING."""
        result = sm.get_next_state("AWAITING_REPORT", ["jenis_kejadian"])
        assert result == StateManager.STATE_CONFIRMING

    def test_lokasi_beats_data_korban(self, sm):
        """lokasi_teks has higher priority than data_korban."""
        result = sm.get_next_state("AWAITING_REPORT", ["data_korban", "lokasi_teks"])
        assert result == StateManager.STATE_AWAITING_LOKASI

    def test_waktu_beats_data_korban(self, sm):
        """waktu has higher priority than data_korban."""
        result = sm.get_next_state("AWAITING_REPORT", ["data_korban", "waktu"])
        assert result == StateManager.STATE_AWAITING_WAKTU


# =========================================================================
# STATE CONSTANTS – verify literal values haven't drifted
# =========================================================================

class TestStateConstants:
    """Ensure every class-level constant has the expected string value."""

    def test_state_awaiting_report(self):
        assert StateManager.STATE_AWAITING_REPORT == "AWAITING_REPORT"

    def test_state_awaiting_waktu(self):
        assert StateManager.STATE_AWAITING_WAKTU == "AWAITING_WAKTU"

    def test_state_awaiting_lokasi(self):
        assert StateManager.STATE_AWAITING_LOKASI == "AWAITING_LOKASI"

    def test_state_awaiting_korban(self):
        assert StateManager.STATE_AWAITING_KORBAN == "AWAITING_KORBAN"

    def test_state_confirming(self):
        assert StateManager.STATE_CONFIRMING == "CONFIRMING"

    def test_state_completed(self):
        assert StateManager.STATE_COMPLETED == "COMPLETED"


# =========================================================================
# EDGE CASES
# =========================================================================

class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    def test_empty_list_returns_confirming(self, sm):
        """An explicitly empty list is functionally identical to 'no missing fields'."""
        assert sm.get_next_state("AWAITING_REPORT", []) == StateManager.STATE_CONFIRMING

    def test_duplicate_waktu_entries(self, sm):
        """Duplicate field names in list should still resolve correctly."""
        result = sm.get_next_state("AWAITING_REPORT", ["waktu", "waktu"])
        assert result == StateManager.STATE_AWAITING_WAKTU

    def test_empty_string_in_list(self, sm):
        """A list containing only an empty string has no recognised field → CONFIRMING."""
        result = sm.get_next_state("AWAITING_REPORT", [""])
        assert result == StateManager.STATE_CONFIRMING

    def test_very_long_missing_fields_list(self, sm):
        """A long list with 'waktu' buried at the end should still resolve to AWAITING_WAKTU."""
        filler = [f"field_{i}" for i in range(100)]
        filler.append("waktu")
        result = sm.get_next_state("AWAITING_REPORT", filler)
        assert result == StateManager.STATE_AWAITING_WAKTU

    def test_mixed_valid_and_invalid_fields(self, sm):
        """Valid fields mixed with garbage – highest-priority valid field wins."""
        result = sm.get_next_state("AWAITING_REPORT", ["xyz", "korban", "abc"])
        assert result == StateManager.STATE_AWAITING_KORBAN

    def test_current_state_does_not_affect_output(self, sm):
        """The returned state depends only on missing_fields, not on current_state."""
        states = [
            StateManager.STATE_AWAITING_REPORT,
            StateManager.STATE_AWAITING_WAKTU,
            StateManager.STATE_AWAITING_LOKASI,
            StateManager.STATE_AWAITING_KORBAN,
            StateManager.STATE_CONFIRMING,
            StateManager.STATE_COMPLETED,
            "TOTALLY_INVALID_STATE",
        ]
        for current in states:
            assert sm.get_next_state(current, ["lokasi_teks"]) == StateManager.STATE_AWAITING_LOKASI

    def test_case_sensitivity_waktu(self, sm):
        """Field names are case-sensitive; 'Waktu' ≠ 'waktu'."""
        result = sm.get_next_state("AWAITING_REPORT", ["Waktu"])
        assert result == StateManager.STATE_CONFIRMING  # Not recognised

    def test_case_sensitivity_lokasi(self, sm):
        """'Lokasi_Teks' should NOT match 'lokasi_teks'."""
        result = sm.get_next_state("AWAITING_REPORT", ["Lokasi_Teks"])
        assert result == StateManager.STATE_CONFIRMING

    def test_classmethod_callable_without_instance(self):
        """get_next_state is a classmethod and can be called on the class directly."""
        result = StateManager.get_next_state("AWAITING_REPORT", ["waktu"])
        assert result == StateManager.STATE_AWAITING_WAKTU

    def test_whitespace_field_name_not_matched(self, sm):
        """' waktu ' (with spaces) should not match 'waktu'."""
        result = sm.get_next_state("AWAITING_REPORT", [" waktu "])
        assert result == StateManager.STATE_CONFIRMING

    def test_none_in_list_does_not_crash(self, sm):
        """A None element inside the list should not cause an unhandled exception."""
        # The `in` operator can handle None elements without raising
        result = sm.get_next_state("AWAITING_REPORT", [None, "lokasi_teks"])
        assert result == StateManager.STATE_AWAITING_LOKASI

    def test_korban_and_data_korban_both_present(self, sm):
        """Both victim keys missing – still returns AWAITING_KORBAN (first branch hit)."""
        result = sm.get_next_state("AWAITING_REPORT", ["korban", "data_korban"])
        assert result == StateManager.STATE_AWAITING_KORBAN
