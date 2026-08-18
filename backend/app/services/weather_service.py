"""
WeatherService — fetches live weather and 3-day forecast from Open-Meteo.

Uses an in-memory TTL cache (default 10 min) keyed by (lat, lon).
Falls back to Open-Meteo geocoding to resolve district names to coordinates.
"""

import os
import asyncio
from datetime import datetime
from typing import Optional

import httpx

from app.utils.cache import TTLCache

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WEATHER_CACHE_TTL: int = int(os.getenv("WEATHER_CACHE_TTL", "600"))  # seconds

OPEN_METEO_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
)
OPEN_METEO_GEOCODING_URL = (
    "https://geocoding-api.open-meteo.com/v1/search"
)

# WMO Weather interpretation codes → human-readable description
WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Clear Sky",
    1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing Rime Fog",
    51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
    61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
    77: "Snow Grains",
    80: "Slight Showers", 81: "Moderate Showers", 82: "Violent Showers",
    85: "Slight Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm with Slight Hail",
    99: "Thunderstorm with Heavy Hail",
}


# ---------------------------------------------------------------------------
# District name → geocodable alias map
# Government-renamed or unusual district names that Open-Meteo geocoding
# cannot resolve are mapped to their well-known city/town equivalents.
# ---------------------------------------------------------------------------
DISTRICT_GEOCODE_MAP: dict[str, str] = {
    # Andhra Pradesh
    "ysr kadapa": "Kadapa",
    "kadapa": "Kadapa",
    "dr. b.r. ambedkar konaseema": "Amalapuram",
    "konaseema": "Amalapuram",
    "dr b r ambedkar konaseema": "Amalapuram",
    "eluru": "Eluru",
    "sri sathya sai": "Puttaparthi",
    "ntr": "Vijayawada",
    "bapatla": "Bapatla",
    "palnadu": "Narasaraopet",
    "alluri sitharama raju": "Paderu",
    "anakapalli": "Anakapalle",
    "kakinada": "Kakinada",
    "ananthapuramu": "Anantapur",
    # Telangana
    "jayashankar bhupalpally": "Bhupalpally",
    "kumuram bheem asifabad": "Asifabad",
    "mulugu": "Mulugu",
    "narayanpet": "Narayanpet",
    "vikarabad": "Vikarabad",
    # Tamil Nadu
    "chengalpattu": "Chengalpattu",
    "ranipet": "Ranipet",
    "tirupathur": "Tirupathur",
    "tenkasi": "Tenkasi",
    # General pattern: strip "Dr." / "YSR" / "Sri" prefix
}

def _normalize_district_for_geocoding(name: str) -> str:
    """Return a geocodable name for *name*, using the alias map.

    Strategy:
    1. Check exact lowercase match in DISTRICT_GEOCODE_MAP.
    2. Strip common administrative prefixes (YSR, Dr., Sri, etc.) and retry.
    3. Fall back to the original name.
    """
    key = name.lower().strip()
    if key in DISTRICT_GEOCODE_MAP:
        return DISTRICT_GEOCODE_MAP[key]

    # Strip leading honorific/administrative tokens
    import re as _re
    stripped = _re.sub(
        r'^(ysr|dr\.?|sri|shri|babu|baba)\s+',
        '',
        key,
        flags=_re.IGNORECASE,
    ).strip()
    if stripped in DISTRICT_GEOCODE_MAP:
        return DISTRICT_GEOCODE_MAP[stripped]
    if stripped and stripped != key:
        return stripped.title()  # e.g. "kadapa"

    return name  # original


# ---------------------------------------------------------------------------
# WeatherService
# ---------------------------------------------------------------------------
class WeatherService:
    """Async service for fetching weather data from Open-Meteo."""

    def __init__(self) -> None:
        self._cache: TTLCache = TTLCache(default_ttl_seconds=WEATHER_CACHE_TTL)


    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def get_weather_by_coordinates(
        self, lat: float, lon: float
    ) -> Optional[dict]:
        """Return current weather + 3-day forecast for given coordinates."""
        cache_key = f"{lat:.4f},{lon:.4f}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._fetch_weather(lat, lon)
        if data:
            self._cache.set(cache_key, data)
        return data

    async def get_weather_by_district_name(
        self, district_name: str
    ) -> Optional[dict]:
        """Geocode *district_name* and return weather for its coordinates."""
        coords = await self._geocode(district_name)
        if coords is None:
            return None
        lat, lon, resolved_name = coords
        result = await self.get_weather_by_coordinates(lat, lon)
        if result:
            result["location"] = resolved_name or district_name
        return result

    async def get_extended_forecast_by_coordinates(
        self, lat: float, lon: float
    ) -> Optional[dict]:
        """Return 7-day daily forecast + 48h hourly precipitation + soil moisture."""
        cache_key = f"ext_{lat:.4f},{lon:.4f}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._fetch_extended_forecast(lat, lon)
        if data:
            self._cache.set(cache_key, data)
        return data

    async def get_extended_forecast_by_district_name(
        self, district_name: str
    ) -> Optional[dict]:
        """Geocode *district_name* and return extended forecast for its coordinates."""
        geocode_name = _normalize_district_for_geocoding(district_name)
        coords = await self._geocode(geocode_name)
        if coords is None:
            return None
        lat, lon, resolved_name = coords
        result = await self.get_extended_forecast_by_coordinates(lat, lon)
        if result:
            result["location"] = resolved_name or district_name
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _geocode(
        self, name: str
    ) -> Optional[tuple[float, float, str]]:
        """Return (lat, lon, display_name) for *name* using Open-Meteo geocoding."""
        params = {
            "name": name,
            "count": 1,
            "language": "en",
            "format": "json",
            "countryCode": "IN",   # restrict to India
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(OPEN_METEO_GEOCODING_URL, params=params)
                resp.raise_for_status()
                body = resp.json()
                results = body.get("results")
                if not results:
                    # Retry without country filter
                    params.pop("countryCode", None)
                    resp = await client.get(OPEN_METEO_GEOCODING_URL, params=params)
                    resp.raise_for_status()
                    body = resp.json()
                    results = body.get("results")
                if not results:
                    return None
                hit = results[0]
                return hit["latitude"], hit["longitude"], hit.get("name", name)
        except Exception:
            return None

    async def _fetch_weather(self, lat: float, lon: float) -> Optional[dict]:
        """Call Open-Meteo forecast API and return structured payload."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "apparent_temperature",
            ]),
            "daily": ",".join([
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
            ]),
            "forecast_days": 3,
            "timezone": "Asia/Kolkata",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(OPEN_METEO_FORECAST_URL, params=params)
                resp.raise_for_status()
                raw = resp.json()
        except Exception:
            return None

        return self._parse(raw, lat, lon)

    def _parse(self, raw: dict, lat: float, lon: float) -> dict:
        cur = raw.get("current", {})
        daily = raw.get("daily", {})

        # Current conditions
        code = cur.get("weather_code", 0)
        current = {
            "temperature": cur.get("temperature_2m"),
            "feels_like": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "precipitation": cur.get("precipitation"),
            "wind_speed": cur.get("wind_speed_10m"),
            "weather_code": code,
            "description": WMO_DESCRIPTIONS.get(code, "Unknown"),
            "time": cur.get("time"),
        }

        # 3-day forecast
        days = daily.get("time", [])
        forecast = []
        for i, date in enumerate(days):
            day_code = (daily.get("weather_code") or [])[i] if i < len(daily.get("weather_code") or []) else 0
            forecast.append({
                "date": date,
                "weather_code": day_code,
                "description": WMO_DESCRIPTIONS.get(day_code, "Unknown"),
                "temp_max": (daily.get("temperature_2m_max") or [])[i] if i < len(daily.get("temperature_2m_max") or []) else None,
                "temp_min": (daily.get("temperature_2m_min") or [])[i] if i < len(daily.get("temperature_2m_min") or []) else None,
                "precipitation_sum": (daily.get("precipitation_sum") or [])[i] if i < len(daily.get("precipitation_sum") or []) else None,
                "precipitation_probability": (daily.get("precipitation_probability_max") or [])[i] if i < len(daily.get("precipitation_probability_max") or []) else None,
            })

        return {
            "latitude": lat,
            "longitude": lon,
            "current": current,
            "forecast": forecast,
            "source": "Open-Meteo",
        }

    # ------------------------------------------------------------------
    # Extended forecast (7-day + 48h hourly)
    # ------------------------------------------------------------------

    async def _fetch_extended_forecast(
        self, lat: float, lon: float
    ) -> Optional[dict]:
        """Call Open-Meteo for 7-day daily + 48h hourly forecast with soil moisture."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "apparent_temperature",
            ]),
            "daily": ",".join([
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "relative_humidity_2m_mean",
                "et0_fao_evapotranspiration",
                "soil_moisture_0_to_7cm_mean",
            ]),
            "hourly": ",".join([
                "precipitation",
                "soil_moisture_0_to_7cm",
            ]),
            "forecast_days": 7,
            "forecast_hours": 48,
            "timezone": "Asia/Kolkata",
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(OPEN_METEO_FORECAST_URL, params=params)
                resp.raise_for_status()
                raw = resp.json()
        except Exception:
            return None

        return self._parse_extended(raw, lat, lon)

    def _parse_extended(self, raw: dict, lat: float, lon: float) -> dict:
        """Parse Open-Meteo extended forecast into a structured payload."""
        cur = raw.get("current", {})
        daily = raw.get("daily", {})
        hourly = raw.get("hourly", {})

        # Current conditions
        code = cur.get("weather_code", 0)
        current = {
            "temperature": cur.get("temperature_2m"),
            "feels_like": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "precipitation": cur.get("precipitation"),
            "wind_speed": cur.get("wind_speed_10m"),
            "weather_code": code,
            "description": WMO_DESCRIPTIONS.get(code, "Unknown"),
            "time": cur.get("time"),
        }

        # Helper to safely index a list
        def _safe(arr, i, default=None):
            lst = arr or []
            return lst[i] if i < len(lst) else default

        # 7-day daily forecast
        days = daily.get("time", [])
        daily_forecast = []
        for i, date in enumerate(days):
            day_code = _safe(daily.get("weather_code"), i, 0)
            daily_forecast.append({
                "date": date,
                "weather_code": day_code,
                "description": WMO_DESCRIPTIONS.get(day_code, "Unknown"),
                "temp_max": _safe(daily.get("temperature_2m_max"), i),
                "temp_min": _safe(daily.get("temperature_2m_min"), i),
                "precipitation_sum": _safe(daily.get("precipitation_sum"), i),
                "precipitation_probability": _safe(daily.get("precipitation_probability_max"), i),
                "humidity": _safe(daily.get("relative_humidity_2m_mean"), i),
                "et0": _safe(daily.get("et0_fao_evapotranspiration"), i),
                "soil_moisture": _safe(daily.get("soil_moisture_0_to_7cm_mean"), i),
            })

        # 48-hour hourly precipitation
        hourly_times = hourly.get("time", [])
        hourly_precip = hourly.get("precipitation", [])
        hourly_soil = hourly.get("soil_moisture_0_to_7cm", [])
        hourly_rainfall = []
        for i, t in enumerate(hourly_times):
            hourly_rainfall.append({
                "time": t,
                "rain_mm": _safe(hourly_precip, i, 0),
                "soil_moisture": _safe(hourly_soil, i),
            })

        # Totals for the 7-day period
        total_forecast_rain = sum(
            d.get("precipitation_sum") or 0 for d in daily_forecast
        )

        return {
            "latitude": lat,
            "longitude": lon,
            "current": current,
            "current_rainfall_mm": cur.get("precipitation", 0),
            "daily_forecast": daily_forecast,
            "hourly_rainfall": hourly_rainfall,
            "forecast_total_rain_mm": round(total_forecast_rain, 1),
            "source": "Open-Meteo",
        }

