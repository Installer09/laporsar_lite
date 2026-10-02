"""
Geo Service — Coordinate Parsing, Distance & Heading Calculation
=================================================================
Provides utilities for:
- Parsing latitude/longitude from various text formats (DMS, decimal)
- Calculating distance in nautical miles (Haversine)
- Calculating heading/bearing between two points
- Finding nearest SAR location from the database
"""

import re
import math
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


def parse_coordinates(text: str) -> Optional[Tuple[float, float]]:
    """
    Extract latitude and longitude from a text string.
    Supports multiple formats:
      - Decimal (dot/comma): -6.123, 106.456 or -6,123, 106,456
      - DMM (Degrees Decimal Minutes): 03° 23.475' S / 106° 14.492' E
      - DMS (Degrees Minutes Seconds): 03°23'28.6" LU / 106°14'29.5" BT
      - Maritime/Natural text: 03 23.475 S 106 14.492 T
    Returns (lat, lon) or None if not found.
    """
    if not text.strip():
        return None

    # --- 1. Try DMS / DMM with hemisphere letters (NSEW / LULS / BTBB / UT) ---
    # Matches:
    # Group 1: degrees
    # Group 2: minutes (can be float like 23.475 for DMM)
    # Group 3: optional seconds (for DMS)
    # Group 4: hemisphere indicator
    dms_dmm_pattern = (
        r"(\d{1,3})[°º\s]?"                                  # degrees + optional degree symbol/space
        r"\s*(\d{1,2}(?:[\.,]\d+)?)['''′']?"                 # minutes (integer or decimal) + optional minute symbol
        r"(?:\s*(\d{1,2}(?:[\.,]\d+)?)[\"\"″\"\"']?)?"       # optional seconds + optional quote
        r"\s*([NSEWUSTB]|LS|LU|BT|BB|[Uu]tara|[Ss]elatan|[Tt]imur|[Bb]arat)\b" # hemisphere
    )
    matches = re.findall(dms_dmm_pattern, text, re.IGNORECASE)
    if len(matches) >= 2:
        coords = []
        for deg, mins, secs, hem in matches:
            deg_val = float(deg)
            mins_val = float(mins.replace(",", ".")) if mins else 0.0
            secs_val = float(secs.replace(",", ".")) if (secs and secs.strip()) else 0.0

            decimal = deg_val + (mins_val / 60.0) + (secs_val / 3600.0)
            hem_u = hem.upper()
            if hem_u in ('S', 'LS', 'SELATAN'):
                decimal = -decimal
            elif hem_u in ('W', 'BB', 'B', 'BARAT'):
                decimal = -decimal
            coords.append(decimal)

        lat, lon = coords[0], coords[1]
        # Heuristic swap: latitude is smaller for Indonesia (lat < 15, lon > 90)
        if abs(lat) > 20 and abs(lon) <= 20:
            lat, lon = lon, lat
        return (round(lat, 6), round(lon, 6))

    # --- 2. Try decimal format: e.g. "3.391282, 106.241521" or "-6,123, 106,456" ---
    decimal_pattern = r'(-?\d{1,3}(?:[\.,]\d{2,}))\s*(?:[,/]\s*|\s+)(-?\d{1,3}(?:[\.,]\d{2,}))'
    match = re.search(decimal_pattern, text)
    if match:
        val1 = float(match.group(1).replace(",", "."))
        val2 = float(match.group(2).replace(",", "."))
        # Heuristic: latitude is usually smaller for Indonesia (0-11°)
        if abs(val1) <= 15 and abs(val2) > 15:
            return (val1, val2)
        elif abs(val2) <= 15 and abs(val1) > 15:
            return (val2, val1)
        else:
            return (val1, val2)

    return None


def calculate_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points
    using the Haversine formula. Returns distance in nautical miles.
    """
    R_NM = 3440.065  # Earth radius in nautical miles

    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R_NM * c


def calculate_heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the initial bearing (heading) from point 1 to point 2.
    Returns heading in degrees (0-360).
    Point 1 = SAR office, Point 2 = LKP (incident location).
    """
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlon = lon2_r - lon1_r

    x = math.sin(dlon) * math.cos(lat2_r)
    y = (math.cos(lat1_r) * math.sin(lat2_r) -
         math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon))

    bearing = math.atan2(x, y)
    bearing_deg = (math.degrees(bearing) + 360) % 360

    return round(bearing_deg, 0)


def find_nearest_location(
    lat: float, lon: float, locations: list
) -> Optional[dict]:
    """
    Find the nearest SAR location from a list of location objects.
    Each location must have .name, .type, .lat, .lng attributes.
    Returns dict with name, type, distance_nm, heading.
    """
    if not locations:
        return None

    nearest = None
    min_dist = float('inf')

    for loc in locations:
        if loc.lat is None or loc.lng is None:
            continue
        dist = calculate_distance_nm(loc.lat, loc.lng, lat, lon)
        if dist < min_dist:
            min_dist = dist
            heading = calculate_heading(loc.lat, loc.lng, lat, lon)
            nearest = {
                "name": loc.name,
                "type": getattr(loc, "type", "Pos SAR"),
                "distance_nm": round(dist, 2),
                "heading": heading,
                "lat": loc.lat,
                "lng": loc.lng,
                "unsur": getattr(loc, "unsur", None),
                "alut": getattr(loc, "alut", None),
                "location_obj": loc,
            }

    return nearest
