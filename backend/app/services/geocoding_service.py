import httpx
import logging

from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class GeocodingService:
    """Service to handle geocoding via OpenStreetMap Nominatim API."""

    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.user_agent = "SARBot/2.4 (SAR Operations Indonesia)"
        self._geocode_cache = {}          # key: query_string -> value: (lat, lon, display_name) or None
        self._reverse_geocode_cache = {}  # key: (lat, lon) -> value: display_name or None

    async def geocode_location(self, location_name: str, db = None) -> Optional[Tuple[float, float, str]]:
        """
        Geocode a location name into (latitude, longitude, display_name).
        Appends the default working area to improve accuracy.
        """
        if not location_name or len(location_name.strip()) < 3:
            return None

        # Clean the input a bit
        loc_clean = location_name.strip()
        
        # Get wilayah kerja from DB
        wilayah_kerja = "Indonesia"
        if db is not None:
            try:
                from sqlalchemy.future import select
                from app.models.settings_models import SystemSetting, SettingKey
                result = await db.execute(select(SystemSetting).where(SystemSetting.key == SettingKey.WILAYAH_KERJA))
                setting = result.scalar_one_or_none()
                if setting and setting.value:
                    wilayah_kerja = setting.value
            except Exception as e:
                logger.warning(f"Failed to fetch wilayah kerja from DB: {e}")
        
        # Prevent appending if the user already typed 'natuna' or 'kepri'
        query = loc_clean
        if wilayah_kerja and wilayah_kerja.lower() not in loc_clean.lower():
            query = f"{loc_clean}, {wilayah_kerja}"

        # Check Cache
        cache_key = query.lower().strip()
        if cache_key in self._geocode_cache:
            logger.info(f"[Geocoding] Cache hit for '{query}': {self._geocode_cache[cache_key]}")
            return self._geocode_cache[cache_key]

        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 0
        }
        
        headers = {
            "User-Agent": self.user_agent
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params, headers=headers, timeout=5.0)
                response.raise_for_status()
                data = response.json()
                
                if data and len(data) > 0:
                    result = data[0]
                    lat = float(result.get("lat"))
                    lon = float(result.get("lon"))
                    display_name = result.get("name", loc_clean)  # use short name if available
                    res = (lat, lon, display_name)
                    self._geocode_cache[cache_key] = res
                    return res
                self._geocode_cache[cache_key] = None
                return None
        except Exception as e:
            logger.error(f"[Geocoding] Error resolving '{location_name}': {e}")
            return None

    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """
        Reverse geocode coordinates into a display name.
        """
        # Round coordinates to 5 decimal places (~1.1m precision) to increase cache hits for slightly varying queries
        cache_key = (round(lat, 5), round(lon, 5))
        if cache_key in self._reverse_geocode_cache:
            logger.info(f"[Geocoding] Reverse cache hit for {cache_key}: {self._reverse_geocode_cache[cache_key]}")
            return self._reverse_geocode_cache[cache_key]

        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "zoom": 14,  # Village/Suburb level
            "addressdetails": 0
        }
        headers = {"User-Agent": self.user_agent}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers, timeout=5.0)
                response.raise_for_status()
                data = response.json()
                
                resolved_name = None
                if data and "name" in data and data["name"]:
                    resolved_name = data["name"]
                elif data and "display_name" in data:
                    parts = data["display_name"].split(",")
                    if parts:
                        resolved_name = parts[0].strip()
                

                
                self._reverse_geocode_cache[cache_key] = resolved_name
                return resolved_name
        except Exception as e:
            logger.error(f"[Geocoding] Error reverse geocoding {lat},{lon}: {e}")
            return None

    def is_coordinate_in_water(self, lat: float, lng: float) -> bool:
        """Heuristics to check if coordinates are in water (sea) within Natuna/Anambas."""
        features = [
            {"name": "Pulau Senua", "lat": 4.015, "lng": 108.423, "is_island": True},
            {"name": "Pulau Sedanau", "lat": 3.805, "lng": 108.030, "is_island": True},
            {"name": "Pulau Laut", "lat": 4.710, "lng": 107.985, "is_island": True},
            {"name": "Pulau Midai", "lat": 3.030, "lng": 107.780, "is_island": True},
            {"name": "Pulau Subi", "lat": 2.905, "lng": 108.850, "is_island": True},
            {"name": "Pulau Serasan", "lat": 2.500, "lng": 109.020, "is_island": True},
            {"name": "Pulau Tiga", "lat": 3.630, "lng": 108.060, "is_island": True},
            {"name": "Pulau Panjang", "lat": 2.780, "lng": 108.910, "is_island": True},
            {"name": "Pulau Jemaja", "lat": 2.950, "lng": 105.730, "is_island": True},
            {"name": "Pulau Siantan", "lat": 3.220, "lng": 106.230, "is_island": True},
            {"name": "Pulau Matak", "lat": 3.320, "lng": 106.260, "is_island": True},
            {"name": "Ranai (Bunguran Besar)", "lat": 3.945, "lng": 108.350, "is_island": False}
        ]
        
        from app.services.geo_service import calculate_distance_nm
        
        nearest = None
        min_dist = float('inf')
        
        for f in features:
            dist = calculate_distance_nm(f["lat"], f["lng"], lat, lng)
            if dist < min_dist:
                min_dist = dist
                nearest = f
                
        if not nearest:
            return False
            
        if nearest["is_island"]:
            # Outer islands: if you are > 0.05 NM from the island center, it is sea/water
            return min_dist > 0.05
        else:
            # Mainland Bunguran Besar (Ranai): main town is right on the coast.
            # If distance to Ranai center is > 1.5 NM, it is sea/water (or mountains, which we distinguish by land text).
            return min_dist > 1.5

    async def enrich_location_with_island(self, lat: float, lng: float, default_name: str = None) -> str:
        """Enrich a location name to refer to the closest island if it is in the water near it."""
        features = [
            {"name": "Pulau Senua", "lat": 4.015, "lng": 108.423, "is_island": True},
            {"name": "Pulau Sedanau", "lat": 3.805, "lng": 108.030, "is_island": True},
            {"name": "Pulau Laut", "lat": 4.710, "lng": 107.985, "is_island": True},
            {"name": "Pulau Midai", "lat": 3.030, "lng": 107.780, "is_island": True},
            {"name": "Pulau Subi", "lat": 2.905, "lng": 108.850, "is_island": True},
            {"name": "Pulau Serasan", "lat": 2.500, "lng": 109.020, "is_island": True},
            {"name": "Pulau Tiga", "lat": 3.630, "lng": 108.060, "is_island": True},
            {"name": "Pulau Panjang", "lat": 2.780, "lng": 108.910, "is_island": True},
            {"name": "Pulau Jemaja", "lat": 2.950, "lng": 105.730, "is_island": True},
            {"name": "Pulau Siantan", "lat": 3.220, "lng": 106.230, "is_island": True},
            {"name": "Pulau Matak", "lat": 3.320, "lng": 106.260, "is_island": True},
            {"name": "Ranai (Bunguran Besar)", "lat": 3.945, "lng": 108.350, "is_island": False}
        ]
        
        from app.services.geo_service import calculate_distance_nm
        
        nearest = None
        min_dist = float('inf')
        
        for f in features:
            dist = calculate_distance_nm(f["lat"], f["lng"], lat, lng)
            if dist < min_dist:
                min_dist = dist
                nearest = f
                
        if nearest:
            name_clean = default_name or ""
            name_lower = name_clean.lower()
            land_keywords = ["kecamatan", "kelurahan", "desa", "jalan", "gunung", "bukit", "hutan", "rt/", "rw/"]
            
            # If the resolved name explicitly indicates a land address, keep it
            if any(lk in name_lower for lk in land_keywords):
                return default_name
                
            if nearest["is_island"] and min_dist <= 15.0:
                if self.is_coordinate_in_water(lat, lng):
                    return f"Perairan {nearest['name']}"
                else:
                    return nearest["name"]
            elif nearest["name"] == "Ranai (Bunguran Besar)" and min_dist <= 15.0:
                if min_dist > 1.5:
                    return "Perairan Ranai, Natuna"
                else:
                    return default_name or "Ranai, Natuna"
                    
        return default_name or f"Koordinat {lat:.4f}, {lng:.4f}"

geocoding_service = GeocodingService()
