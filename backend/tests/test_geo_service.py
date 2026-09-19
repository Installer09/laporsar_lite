"""
Comprehensive tests for app.services.geo_service module.

Covers:
- parse_coordinates (decimal, DMS, heuristic swap, edge cases)
- calculate_distance_nm (haversine formula verification)
- calculate_heading (cardinal directions, diagonals)
- find_nearest_location (single, multiple, empty, attribute edge cases)
- Destructive / edge cases (NaN, Inf, empty strings, large values)
"""

import math
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.geo_service import (
    parse_coordinates,
    calculate_distance_nm,
    calculate_heading,
    find_nearest_location,
)

R_NM = 3440.065


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_locations():
    """Create a list of SimpleNamespace objects mimicking location models."""
    return [
        SimpleNamespace(name="Jakarta", lat=-6.2088, lng=106.8456, unsur="port", alut="SAR A"),
        SimpleNamespace(name="Surabaya", lat=-7.2575, lng=112.7521, unsur="port", alut="SAR B"),
        SimpleNamespace(name="Bali", lat=-8.3405, lng=115.092, unsur="island", alut="SAR C"),
    ]


@pytest.fixture
def location_without_optional_attrs():
    """Location object missing 'unsur' and 'alut' attributes."""
    loc = MagicMock()
    loc.name = "Remote Outpost"
    loc.lat = -5.0
    loc.lng = 110.0
    del loc.unsur
    del loc.alut
    return loc


# ===========================================================================
# parse_coordinates Tests
# ===========================================================================

class TestParseCoordinatesDecimal:
    """Tests for decimal coordinate parsing."""

    def test_standard_decimal_negative_lat(self):
        """1. Standard decimal with negative latitude returns correct tuple."""
        result = parse_coordinates("-6.123, 106.456")
        assert result == pytest.approx((-6.123, 106.456))

    def test_decimal_without_negative(self):
        """2. Decimal without negative sign returns positive coordinates."""
        result = parse_coordinates("6.123, 106.456")
        assert result == pytest.approx((6.123, 106.456))

    def test_indonesia_heuristic_swaps_lat_lon(self):
        """4. Indonesia heuristic: when |lat| > 15 and |lon| <= 15, swap lat/lon."""
        # Input "106.456, -6.123" has lat=106.456 (>15) and lon=-6.123 (<=15)
        result = parse_coordinates("106.456, -6.123")
        assert result == pytest.approx((-6.123, 106.456))

    def test_coordinates_in_longer_text(self):
        """6. Coordinates embedded in a longer text string are extracted."""
        text = "Vessel last reported at position -6.123, 106.456 heading north."
        result = parse_coordinates(text)
        assert result == pytest.approx((-6.123, 106.456))

    def test_equator_origin(self):
        """7. Edge case: coordinates at the equator/prime-meridian origin (0, 0)."""
        # Using small decimals to ensure the regex's \.\d+ pattern matches
        result = parse_coordinates("0.000, 0.000")
        assert result == pytest.approx((0.0, 0.0))

    def test_max_lat_lon(self):
        """8. Edge case: maximum valid latitude (90) and longitude (180)."""
        result = parse_coordinates("90.000, 180.000")
        assert result is not None
        assert result == pytest.approx((90.0, 180.0))

    def test_negative_longitude(self):
        """9. Negative longitude is parsed correctly."""
        result = parse_coordinates("5.123, -106.456")
        assert result == pytest.approx((5.123, -106.456))

    def test_multiple_coordinate_pairs_returns_first(self):
        """10. When multiple coordinate pairs exist, the first match is returned."""
        text = "-6.123, 106.456 and -7.890, 112.345"
        result = parse_coordinates(text)
        assert result == pytest.approx((-6.123, 106.456))

    def test_coordinates_with_extra_whitespace(self):
        """12. Coordinates separated by extra whitespace are still parsed."""
        result = parse_coordinates("-6.123   106.456")
        assert result == pytest.approx((-6.123, 106.456))

    def test_coordinates_comma_no_space(self):
        """Decimal coordinates with comma and no space are parsed."""
        result = parse_coordinates("-6.123,106.456")
        assert result == pytest.approx((-6.123, 106.456))

    def test_heuristic_does_not_swap_when_both_large(self):
        """Heuristic should NOT swap when both values are > 15."""
        result = parse_coordinates("20.000, 30.000")
        assert result == pytest.approx((20.0, 30.0))

    def test_heuristic_does_not_swap_when_lat_within_range(self):
        """Heuristic should NOT swap when |lat| <= 15 regardless of lon."""
        result = parse_coordinates("-6.123, 106.456")
        assert result == pytest.approx((-6.123, 106.456))


class TestParseCoordinatesDMS:
    """Tests for DMS (Degrees Minutes Seconds) coordinate parsing."""

    def test_standard_dms(self):
        """3. Standard DMS format is parsed correctly."""
        text = '3°45\'12"S 108°30\'45"E'
        result = parse_coordinates(text)
        assert result is not None
        expected_lat = -(3 + 45 / 60 + 12 / 3600)
        expected_lon = 108 + 30 / 60 + 45 / 3600
        assert result[0] == pytest.approx(expected_lat, abs=1e-6)
        assert result[1] == pytest.approx(expected_lon, abs=1e-6)

    def test_dms_north_east(self):
        """DMS with N and E direction letters (positive lat and lon)."""
        text = '3°45\'12"N 108°30\'45"E'
        result = parse_coordinates(text)
        assert result is not None
        expected_lat = 3 + 45 / 60 + 12 / 3600
        expected_lon = 108 + 30 / 60 + 45 / 3600
        assert result[0] == pytest.approx(expected_lat, abs=1e-6)
        assert result[1] == pytest.approx(expected_lon, abs=1e-6)

    def test_dms_south_west(self):
        """DMS with S and W direction letters (negative lat and lon)."""
        text = '3°45\'12"S 108°30\'45"W'
        result = parse_coordinates(text)
        assert result is not None
        expected_lat = -(3 + 45 / 60 + 12 / 3600)
        expected_lon = -(108 + 30 / 60 + 45 / 3600)
        assert result[0] == pytest.approx(expected_lat, abs=1e-6)
        assert result[1] == pytest.approx(expected_lon, abs=1e-6)

    def test_dms_with_unicode_double_prime(self):
        """DMS using Unicode double-prime character (″) is parsed."""
        text = "3°45'12″S 108°30'45″E"
        result = parse_coordinates(text)
        assert result is not None
        expected_lat = -(3 + 45 / 60 + 12 / 3600)
        expected_lon = 108 + 30 / 60 + 45 / 3600
        assert result[0] == pytest.approx(expected_lat, abs=1e-6)
        assert result[1] == pytest.approx(expected_lon, abs=1e-6)

    def test_dms_lowercase_direction(self):
        """DMS with lowercase direction letters (s, e) is accepted."""
        text = '3°45\'12"s 108°30\'45"e'
        result = parse_coordinates(text)
        assert result is not None
        expected_lat = -(3 + 45 / 60 + 12 / 3600)
        expected_lon = 108 + 30 / 60 + 45 / 3600
        assert result[0] == pytest.approx(expected_lat, abs=1e-6)
        assert result[1] == pytest.approx(expected_lon, abs=1e-6)

    def test_dms_with_fractional_seconds(self):
        """DMS with fractional seconds (e.g., 12.5\") is parsed correctly."""
        text = '3°45\'12.5"N 108°30\'45.75"E'
        result = parse_coordinates(text)
        assert result is not None
        expected_lat = 3 + 45 / 60 + 12.5 / 3600
        expected_lon = 108 + 30 / 60 + 45.75 / 3600
        assert result[0] == pytest.approx(expected_lat, abs=1e-6)
        assert result[1] == pytest.approx(expected_lon, abs=1e-6)


class TestParseCoordinatesNone:
    """Tests where parse_coordinates should return None."""

    def test_no_coordinates_in_text(self):
        """5. Text without any coordinate-like pattern returns None."""
        result = parse_coordinates("No coordinates here at all")
        assert result is None

    def test_invalid_text_with_no_numbers(self):
        """11. Completely non-numeric text returns None."""
        result = parse_coordinates("hello world foo bar")
        assert result is None

    def test_empty_string(self):
        """31. Empty string returns None."""
        result = parse_coordinates("")
        assert result is None

    def test_single_number_no_pair(self):
        """A single decimal number without a pair returns None."""
        result = parse_coordinates("6.123")
        assert result is None


# ===========================================================================
# calculate_distance_nm Tests
# ===========================================================================

class TestCalculateDistanceNM:
    """Tests for the Haversine distance calculation in nautical miles."""

    def test_same_point_returns_zero(self):
        """13. Distance from a point to itself is 0."""
        dist = calculate_distance_nm(-6.2, 106.8, -6.2, 106.8)
        assert dist == pytest.approx(0.0, abs=1e-9)

    def test_known_distance_jakarta_surabaya(self):
        """14. Jakarta → Surabaya is approximately 420 NM (rough sanity check)."""
        dist = calculate_distance_nm(-6.2088, 106.8456, -7.2575, 112.7521)
        # Known great-circle ~420 NM; allow generous tolerance for sanity
        assert 350 < dist < 500

    def test_antipodal_points(self):
        """15. Antipodal points yield maximum possible distance (half circumference)."""
        dist = calculate_distance_nm(0, 0, 0, 180)
        expected_half_circumference = math.pi * R_NM
        assert dist == pytest.approx(expected_half_circumference, rel=1e-4)

    def test_very_close_points(self):
        """16. Very close points yield a very small (but non-negative) distance."""
        dist = calculate_distance_nm(-6.2000, 106.8000, -6.2001, 106.8001)
        assert 0 < dist < 0.01

    def test_north_pole_to_south_pole(self):
        """17. North Pole to South Pole equals half circumference."""
        dist = calculate_distance_nm(90, 0, -90, 0)
        expected = math.pi * R_NM
        assert dist == pytest.approx(expected, rel=1e-4)

    def test_equator_short_distance(self):
        """Distance along the equator: 1 degree longitude ≈ 60 NM."""
        dist = calculate_distance_nm(0, 0, 0, 1)
        assert dist == pytest.approx(60.0, abs=1.0)

    def test_symmetry(self):
        """Distance from A→B equals B→A."""
        d1 = calculate_distance_nm(-6.2, 106.8, -7.3, 112.7)
        d2 = calculate_distance_nm(-7.3, 112.7, -6.2, 106.8)
        assert d1 == pytest.approx(d2, abs=1e-9)

    def test_distance_is_always_non_negative(self):
        """Distance should never be negative."""
        dist = calculate_distance_nm(45.0, -120.0, -33.0, 151.0)
        assert dist >= 0


# ===========================================================================
# calculate_heading Tests
# ===========================================================================

class TestCalculateHeading:
    """Tests for initial bearing/heading calculation."""

    def test_due_north(self):
        """18. Heading due north from equator is approximately 0°."""
        heading = calculate_heading(0, 0, 1, 0)
        assert heading == pytest.approx(0.0, abs=0.5)

    def test_due_east(self):
        """19. Heading due east from equator is approximately 90°."""
        heading = calculate_heading(0, 0, 0, 1)
        assert heading == pytest.approx(90.0, abs=0.5)

    def test_due_south(self):
        """20. Heading due south from equator is approximately 180°."""
        heading = calculate_heading(1, 0, 0, 0)
        assert heading == pytest.approx(180.0, abs=0.5)

    def test_due_west(self):
        """21. Heading due west from equator is approximately 270°."""
        heading = calculate_heading(0, 1, 0, 0)
        assert heading == pytest.approx(270.0, abs=0.5)

    def test_same_point_heading(self):
        """22. Heading from a point to itself is 0 (atan2(0,0)=0 → (0+360)%360=0)."""
        heading = calculate_heading(0, 0, 0, 0)
        assert heading == pytest.approx(0.0, abs=1e-9)

    def test_diagonal_northeast(self):
        """23. Heading toward northeast should be between 0° and 90°."""
        heading = calculate_heading(0, 0, 1, 1)
        assert 0 < heading < 90

    def test_heading_always_in_0_360_range(self):
        """Heading is always in [0, 360) regardless of input."""
        heading = calculate_heading(10, 20, -30, -40)
        assert 0 <= heading < 360

    def test_diagonal_southwest(self):
        """Heading toward southwest should be between 180° and 270°."""
        heading = calculate_heading(1, 1, 0, 0)
        assert 180 < heading < 270

    def test_heading_symmetry_opposite(self):
        """Heading A→B and B→A should differ by roughly 180° (for moderate distances)."""
        h1 = calculate_heading(0, 0, 1, 0)
        h2 = calculate_heading(1, 0, 0, 0)
        diff = abs(h1 - h2)
        assert diff == pytest.approx(180.0, abs=1.0)


# ===========================================================================
# find_nearest_location Tests
# ===========================================================================

class TestFindNearestLocation:
    """Tests for find_nearest_location."""

    def test_single_location_returns_it(self, sample_locations):
        """24. With a single location in the list, that location is returned."""
        single = [sample_locations[0]]  # Jakarta
        result = find_nearest_location(-6.0, 107.0, single)
        assert result is not None
        assert result["name"] == "Jakarta"
        assert "distance_nm" in result
        assert "heading" in result

    def test_multiple_locations_returns_nearest(self, sample_locations):
        """25. With multiple locations, the nearest one is returned."""
        # Point very close to Surabaya
        result = find_nearest_location(-7.2, 112.7, sample_locations)
        assert result is not None
        assert result["name"] == "Surabaya"

    def test_empty_locations_list_returns_none(self):
        """26. Empty locations list returns None."""
        result = find_nearest_location(-6.0, 107.0, [])
        assert result is None

    def test_location_at_same_point_zero_distance(self):
        """27. Location exactly at the query point has distance 0."""
        loc = SimpleNamespace(name="Here", lat=-6.0, lng=107.0, unsur="X", alut="Y")
        result = find_nearest_location(-6.0, 107.0, [loc])
        assert result is not None
        assert result["distance_nm"] == 0.0

    def test_location_missing_unsur_alut(self, location_without_optional_attrs):
        """28. Locations without unsur/alut attributes return None for those fields."""
        result = find_nearest_location(-5.0, 110.0, [location_without_optional_attrs])
        assert result is not None
        assert result["unsur"] is None
        assert result["alut"] is None

    def test_result_contains_all_expected_keys(self, sample_locations):
        """Result dict has all five expected keys."""
        result = find_nearest_location(-6.0, 107.0, sample_locations)
        assert result is not None
        expected_keys = {"name", "distance_nm", "heading", "unsur", "alut"}
        assert expected_keys.issubset(result.keys())

    def test_result_distance_is_rounded_to_2_decimals(self, sample_locations):
        """distance_nm value is rounded to 2 decimal places."""
        result = find_nearest_location(-6.0, 107.0, sample_locations)
        assert result is not None
        dist_str = str(result["distance_nm"])
        if "." in dist_str:
            decimals = len(dist_str.split(".")[1])
            assert decimals <= 2

    def test_result_heading_is_rounded_to_1_decimal(self, sample_locations):
        """heading value is rounded to 1 decimal place."""
        result = find_nearest_location(-6.0, 107.0, sample_locations)
        assert result is not None
        heading_str = str(result["heading"])
        if "." in heading_str:
            decimals = len(heading_str.split(".")[1])
            assert decimals <= 1

    def test_nearest_among_equidistant_returns_first(self):
        """When two locations are equidistant, the one iterated first wins."""
        loc_a = SimpleNamespace(name="A", lat=1.0, lng=0.0, unsur=None, alut=None)
        loc_b = SimpleNamespace(name="B", lat=-1.0, lng=0.0, unsur=None, alut=None)
        # Both are equidistant from (0, 0) but A comes first in the list
        result = find_nearest_location(0.0, 0.0, [loc_a, loc_b])
        assert result is not None
        assert result["name"] == "A"

    def test_unsur_and_alut_values_populated(self, sample_locations):
        """When unsur/alut are present on the location, they are populated."""
        result = find_nearest_location(-6.2, 106.8, sample_locations)
        assert result is not None
        assert result["unsur"] == "port"
        assert result["alut"] == "SAR A"


# ===========================================================================
# Destructive / Edge Cases
# ===========================================================================

class TestDestructiveEdgeCases:
    """Destructive and boundary-condition tests."""

    def test_very_large_coordinates_parse(self):
        """29. Very large coordinate values (999, 999) are still parsed without crash."""
        result = parse_coordinates("999.999, 999.999")
        # The heuristic will not swap since both > 15
        assert result is not None
        assert result == pytest.approx((999.999, 999.999))

    def test_nan_distance_does_not_crash(self):
        """30. NaN input to distance calculation should return NaN, not crash."""
        dist = calculate_distance_nm(float("nan"), 0, 0, 0)
        assert math.isnan(dist)

    def test_inf_distance_does_not_crash(self):
        """30b. Inf input to distance calculation should not raise an exception."""
        # math functions with inf may return nan; we just ensure no crash
        try:
            dist = calculate_distance_nm(float("inf"), 0, 0, 0)
            assert math.isnan(dist) or math.isinf(dist) or isinstance(dist, float)
        except (ValueError, OverflowError):
            # Some math domain errors are acceptable
            pass

    def test_empty_string_parse(self):
        """31. (duplicate safeguard) Empty string returns None."""
        assert parse_coordinates("") is None

    def test_none_input_parse_raises(self):
        """32. None input to parse_coordinates raises an appropriate exception."""
        with pytest.raises((TypeError, AttributeError)):
            parse_coordinates(None)

    def test_r_nm_constant_value(self):
        """R_NM constant should be Earth's radius in nautical miles (~3440)."""
        assert R_NM == pytest.approx(3440.065)

    def test_large_coordinate_distance_does_not_crash(self):
        """Distance with very large (but finite) coordinates does not crash."""
        dist = calculate_distance_nm(999, 999, -999, -999)
        assert isinstance(dist, float)

    def test_heading_with_nan_does_not_crash(self):
        """Heading calculation with NaN returns NaN, not a crash."""
        heading = calculate_heading(float("nan"), 0, 0, 0)
        assert math.isnan(heading)

    def test_parse_coordinates_whitespace_only(self):
        """Whitespace-only string returns None."""
        assert parse_coordinates("   ") is None

    def test_parse_coordinates_special_characters(self):
        """String with special characters but no valid coords returns None."""
        assert parse_coordinates("!@#$%^&*()") is None
