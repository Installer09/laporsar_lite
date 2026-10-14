"""
Weather Service — Fetch Weather Data from Open-Meteo
=========================================================
Fetches current weather data for a given coordinate and formats it
into a string suitable for the Info Awal SAR report template.
Falls back gracefully if the request fails (No API key required).
"""

import logging
from typing import Optional
import httpx
import time
import redis.asyncio as redis_async

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory backup cache
_in_memory_cache = {}  # format: {cache_key: {"data": formatted_string, "expire_at": float}}
_redis_client = None
_redis_failed = False

async def _get_redis_client():
    global _redis_client, _redis_failed
    if _redis_failed:
        return None
    if _redis_client is None:
        try:
            # Resolve connection url
            url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            _redis_client = redis_async.from_url(url, decode_responses=True)
            # Test connection
            await _redis_client.ping()
            logger.info("Redis client connected for Weather Service caching.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis for weather cache, using in-memory fallback: {e}")
            _redis_failed = True
            _redis_client = None
    return _redis_client

async def _save_to_cache(cache_key: str, formatted: str):
    cache_ttl = 900  # 15 minutes (900 seconds)
    now = time.time()
    
    # Try Redis
    r_client = await _get_redis_client()
    if r_client:
        try:
            await r_client.set(cache_key, formatted, ex=cache_ttl)
            logger.info(f"Saved weather to Redis cache for key {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to write to Redis cache: {e}")
            
    # Save in-memory
    _in_memory_cache[cache_key] = {
        "data": formatted,
        "expire_at": now + cache_ttl
    }
    logger.info(f"Saved weather to In-Memory cache for key {cache_key}")

# Wind direction mapping (degrees → Indonesian compass)
WIND_DIRECTIONS = [
    (0, "Utara"), (22.5, "Utara-Timur Laut"), (45, "Timur Laut"),
    (67.5, "Timur-Timur Laut"), (90, "Timur"), (112.5, "Timur-Tenggara"),
    (135, "Tenggara"), (157.5, "Selatan-Tenggara"), (180, "Selatan"),
    (202.5, "Selatan-Barat Daya"), (225, "Barat Daya"),
    (247.5, "Barat-Barat Daya"), (270, "Barat"), (292.5, "Barat-Barat Laut"),
    (315, "Barat Laut"), (337.5, "Utara-Barat Laut"),
]


def _degrees_to_compass(deg: float) -> str:
    """Convert wind direction in degrees to Indonesian compass direction."""
    idx = int((deg + 11.25) / 22.5) % 16
    return WIND_DIRECTIONS[idx][1]


async def fetch_weather(lat: float, lon: float) -> Optional[str]:
    """
    Fetch current weather from Open-Meteo API and format for Info Awal.
    Includes marine data (wave height).
    Returns a formatted multi-line string, or None if unavailable.
    """
    grid_lat = round(lat, 1)
    grid_lon = round(lon, 1)
    cache_key = f"weather:{grid_lat}:{grid_lon}"

    # Try Redis cache first
    r_client = await _get_redis_client()
    if r_client:
        try:
            cached_data = await r_client.get(cache_key)
            if cached_data:
                logger.info(f"Weather cache hit (Redis) for key {cache_key}")
                return cached_data
        except Exception as e:
            logger.warning(f"Failed to read from Redis cache: {e}")

    # Fallback to In-Memory cache
    now = time.time()
    if cache_key in _in_memory_cache:
        cached_entry = _in_memory_cache[cache_key]
        if cached_entry["expire_at"] > now:
            logger.info(f"Weather cache hit (In-Memory) for key {cache_key}")
            return cached_entry["data"]
        else:
            del _in_memory_cache[cache_key]

    url = "https://api.open-meteo.com/v1/forecast"
    marine_url = "https://marine-api.open-meteo.com/v1/marine"
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,wind_speed_10m,wind_direction_10m,cloud_cover,weather_code,visibility",
        "timezone": "auto"
    }
    
    marine_params = {
        "latitude": lat,
        "longitude": lon,
        "current": "wave_height",
        "timezone": "auto"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # WMO Weather interpretation codes (WMO code 4680)
            weather_codes = {
                0: "Cerah", 1: "Cerah Berawan", 2: "Berawan", 3: "Mendung",
                45: "Kabut", 48: "Kabut Embun",
                51: "Gerimis Ringan", 53: "Gerimis Sedang", 55: "Gerimis Lebat",
                61: "Hujan Ringan", 63: "Hujan Sedang", 65: "Hujan Lebat",
                71: "Salju Ringan", 73: "Salju Sedang", 75: "Salju Lebat",
                80: "Hujan Badai Ringan", 81: "Hujan Badai Sedang", 82: "Hujan Badai Lebat",
                95: "Badai Petir Ringan", 96: "Badai Petir dengan Hujan Es", 99: "Badai Petir Hebat"
            }
            
            current = data.get("current", {})
            temp = current.get("temperature_2m", "?")
            wind_speed_kmh = current.get("wind_speed_10m", 0)
            wind_deg = current.get("wind_direction_10m", 0)
            clouds = current.get("cloud_cover", 0)
            weather_code = current.get("weather_code", 0)
            weather_desc = weather_codes.get(weather_code, "Tidak diketahui")
            visibility_m = current.get("visibility", 10000)
            
            # Convert wind speed km/h to knots
            wind_kts = round(wind_speed_kmh / 1.852, 1)
            wind_dir = _degrees_to_compass(wind_deg)
            visibility_km = round(visibility_m / 1000, 1)
            
            # Fetch marine data
            wave_height_text = ""
            try:
                marine_response = await client.get(marine_url, params=marine_params)
                if marine_response.status_code == 200:
                    marine_data = marine_response.json()
                    wave_height = marine_data.get("current", {}).get("wave_height")
                    if wave_height is not None:
                        wave_height_text = f"* Gelombang : {wave_height} M\n"
            except Exception as e:
                logger.warning(f"Failed to fetch marine data: {e}")

        formatted = (
            f"* Cuaca : {weather_desc} (awan {clouds}%)\n"
            f"{wave_height_text}"
            f"* Suhu\t: {temp}°C\n"
            f"* Kecepatan angin : {wind_kts} Kts\n"
            f"* Arah Angin : {wind_dir}\n"
            f"* Jarak Pandang : {visibility_km} Km"
        )

        logger.info(f"Weather fetched for ({lat}, {lon}): {weather_desc}, {temp}°C")
        await _save_to_cache(cache_key, formatted)
        return formatted

    except Exception as e:
        logger.error(f"Failed to fetch weather from Open-Meteo: {e}")
        # FALLBACK to wttr.in
        logger.info("Attempting fallback to wttr.in...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"https://wttr.in/{lat},{lon}?format=j1")
                if response.status_code == 200:
                    data = response.json()
                    current = data.get("current_condition", [{}])[0]
                    temp = current.get("temp_C", "?")
                    wind_speed_kmh = float(current.get("windspeedKmph", 0))
                    # Convert km/h to knots
                    wind_kts = round(wind_speed_kmh / 1.852, 1)
                    
                    wind_dir_raw = current.get("winddir16Point", "Tidak diketahui")
                    wind_compass_map = {
                        "N": "Utara", "NNE": "Utara-Timur Laut", "NE": "Timur Laut", "ENE": "Timur-Timur Laut",
                        "E": "Timur", "ESE": "Timur-Tenggara", "SE": "Tenggara", "SSE": "Selatan-Tenggara",
                        "S": "Selatan", "SSW": "Selatan-Barat Daya", "SW": "Barat Daya", "WSW": "Barat-Barat Daya",
                        "W": "Barat", "WNW": "Barat-Barat Laut", "NW": "Barat Laut", "NNW": "Utara-Barat Laut"
                    }
                    wind_dir = wind_compass_map.get(wind_dir_raw.upper(), wind_dir_raw)
                    
                    weather_desc_raw = current.get("weatherDesc", [{}])[0].get("value", "Tidak diketahui").strip().lower()
                    weather_desc = "Tidak diketahui"
                    for en, id_desc in {
                        "clear": "Cerah", "sunny": "Cerah", "partly cloudy": "Cerah Berawan",
                        "cloudy": "Berawan", "overcast": "Mendung", "mist": "Kabut", "fog": "Kabut",
                        "drizzle": "Gerimis", "rain": "Hujan", "heavy rain": "Hujan Lebat",
                        "thunderstorm": "Badai Petir", "snow": "Salju"
                    }.items():
                        if en in weather_desc_raw:
                            weather_desc = id_desc
                            break
                    if weather_desc == "Tidak diketahui":
                        weather_desc = weather_desc_raw.title()
                        
                    humidity = current.get("humidity", 0)
                    visibility_km = current.get("visibility", 10)
                    
                    formatted = (
                        f"* Cuaca : {weather_desc} (kelembaban {humidity}%)\n"
                        f"* Suhu\t: {temp}°C\n"
                        f"* Kecepatan angin : {wind_kts} Kts\n"
                        f"* Arah Angin : {wind_dir}\n"
                        f"* Jarak Pandang : {visibility_km} Km"
                    )
                    logger.info(f"Weather fetched from wttr.in fallback: {weather_desc}, {temp}°C")
                    await _save_to_cache(cache_key, formatted)
                    return formatted
        except Exception as wttr_err:
            logger.error(f"Fallback to wttr.in failed: {wttr_err}")
            
        return None
