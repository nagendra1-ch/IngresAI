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
# Hardcoded district coordinates — bypasses geocoding API entirely.
# (lat, lon, display_name)
# This ensures weather always works even when the geocoding API is unreachable.
# ---------------------------------------------------------------------------
DISTRICT_COORDS: dict[str, tuple[float, float, str]] = {
    # ── Andhra Pradesh ──────────────────────────────────────────────────────
    "srikakulam": (18.2949, 83.8938, "Srikakulam"),
    "vizianagaram": (18.1066, 83.3956, "Vizianagaram"),
    "visakhapatnam": (17.6868, 83.2185, "Visakhapatnam"),
    "anakapalli": (17.6910, 82.9985, "Anakapalle"),
    "anakapalle": (17.6910, 82.9985, "Anakapalle"),
    "alluri sitharama raju": (18.0800, 82.8500, "Paderu"),
    "kakinada": (16.9891, 82.2475, "Kakinada"),
    "dr. b.r. ambedkar konaseema": (16.9800, 82.0000, "Amalapuram"),
    "dr b r ambedkar konaseema": (16.9800, 82.0000, "Amalapuram"),
    "konaseema": (16.9800, 82.0000, "Amalapuram"),
    "amalapuram": (16.5789, 82.0003, "Amalapuram"),
    "east godavari": (17.3273, 81.8314, "Rajamahendravaram"),
    "eluru": (16.7107, 81.0952, "Eluru"),
    "west godavari": (16.9174, 81.3340, "Bhimavaram"),
    "ntr": (16.5062, 80.6480, "Vijayawada"),
    "krishna": (16.5062, 80.6480, "Vijayawada"),
    "vijayawada": (16.5062, 80.6480, "Vijayawada"),
    "guntur": (16.3067, 80.4365, "Guntur"),
    "bapatla": (15.9053, 80.4674, "Bapatla"),
    "palnadu": (16.4307, 79.6480, "Narasaraopet"),
    "prakasam": (15.3400, 79.5700, "Ongole"),
    "sri potti sriramulu nellore": (14.4426, 79.9865, "Nellore"),
    "nellore": (14.4426, 79.9865, "Nellore"),
    "kurnool": (15.8281, 78.0373, "Kurnool"),
    "nandyal": (15.4780, 78.4830, "Nandyal"),
    "ananthapuramu": (14.6819, 77.6006, "Anantapur"),
    "anantapur": (14.6819, 77.6006, "Anantapur"),
    "sri sathya sai": (14.1676, 77.8169, "Puttaparthi"),
    "puttaparthi": (14.1676, 77.8169, "Puttaparthi"),
    "kadapa": (14.4673, 78.8242, "Kadapa"),
    "ysr kadapa": (14.4673, 78.8242, "Kadapa"),
    "chittoor": (13.2172, 79.1003, "Chittoor"),
    "tirupati": (13.6288, 79.4192, "Tirupati"),
    # ── Telangana ───────────────────────────────────────────────────────────
    "hyderabad": (17.3850, 78.4867, "Hyderabad"),
    "rangareddy": (17.2403, 78.3560, "Rangareddy"),
    "medchal malkajgiri": (17.5545, 78.5380, "Medchal"),
    "sangareddy": (17.6193, 78.0860, "Sangareddy"),
    "medak": (18.0500, 78.2600, "Medak"),
    "siddipet": (18.1020, 78.8521, "Siddipet"),
    "nizamabad": (18.6726, 78.0940, "Nizamabad"),
    "nirmal": (19.0973, 78.3430, "Nirmal"),
    "adilabad": (19.6641, 78.5320, "Adilabad"),
    "kumuram bheem asifabad": (19.3670, 79.2880, "Asifabad"),
    "mancherial": (18.8719, 79.4600, "Mancherial"),
    "peddapalli": (18.6140, 79.3730, "Peddapalli"),
    "jayashankar bhupalpally": (18.4385, 79.9060, "Bhupalpally"),
    "mulugu": (18.1920, 80.0630, "Mulugu"),
    "bhadradri kothagudem": (17.5550, 80.6190, "Kothagudem"),
    "khammam": (17.2473, 80.1514, "Khammam"),
    "mahabubabad": (17.5988, 80.0030, "Mahabubabad"),
    "warangal": (17.9784, 79.5941, "Warangal"),
    "hanamkonda": (17.9784, 79.5941, "Hanamkonda"),
    "jangaon": (17.7275, 79.1520, "Jangaon"),
    "yadadri bhuvanagiri": (17.5833, 78.8833, "Bhongir"),
    "suryapet": (17.1416, 79.6206, "Suryapet"),
    "nalgonda": (17.0576, 79.2671, "Nalgonda"),
    "narayanpet": (16.7430, 77.4960, "Narayanpet"),
    "mahbubnagar": (16.7376, 77.9826, "Mahbubnagar"),
    "wanaparthy": (16.3630, 78.0600, "Wanaparthy"),
    "gadwal": (16.2290, 77.8040, "Gadwal"),
    "jogulamba gadwal": (16.2290, 77.8040, "Gadwal"),
    "vikarabad": (17.3330, 77.9040, "Vikarabad"),
    "karimnagar": (18.4386, 79.1288, "Karimnagar"),
    "rajanna sircilla": (18.3870, 78.8120, "Sircilla"),
    "kamareddy": (18.3197, 78.3427, "Kamareddy"),
    "nagarkurnool": (16.4800, 78.3200, "Nagarkurnool"),
    "nagar kurnool": (16.4800, 78.3200, "Nagarkurnool"),
    # ── Tamil Nadu (common) ─────────────────────────────────────────────────
    "chennai": (13.0827, 80.2707, "Chennai"),
    "coimbatore": (11.0168, 76.9558, "Coimbatore"),
    "madurai": (9.9252, 78.1198, "Madurai"),
    "salem": (11.6643, 78.1460, "Salem"),
    "tiruchirappalli": (10.7905, 78.7047, "Tiruchirappalli"),
    "tirunelveli": (8.7139, 77.7567, "Tirunelveli"),
    "vellore": (12.9165, 79.1325, "Vellore"),
    "erode": (11.3410, 77.7172, "Erode"),
    "tiruppur": (11.1085, 77.3411, "Tiruppur"),
    "dindigul": (10.3673, 77.9803, "Dindigul"),
    "thanjavur": (10.7867, 79.1378, "Thanjavur"),
    "chengalpattu": (12.6922, 79.9760, "Chengalpattu"),
    "ranipet": (12.9221, 79.3323, "Ranipet"),
    "tirupathur": (12.4964, 78.5598, "Tirupathur"),
    "tenkasi": (8.9594, 77.3152, "Tenkasi"),
    "kanyakumari": (8.0883, 77.5385, "Kanyakumari"),
    "villupuram": (11.9401, 79.4861, "Villupuram"),
    "cuddalore": (11.7447, 79.7689, "Cuddalore"),
    "nagapattinam": (10.7631, 79.8428, "Nagapattinam"),
    "pudukkottai": (10.3833, 78.8001, "Pudukkottai"),
    "ramanathapuram": (9.3762, 78.8308, "Ramanathapuram"),
    "sivagangai": (9.8476, 78.4800, "Sivagangai"),
    "theni": (10.0104, 77.4770, "Theni"),
    "virudhunagar": (9.5851, 77.9624, "Virudhunagar"),
    "krishnagiri": (12.5266, 78.2138, "Krishnagiri"),
    "dharmapuri": (12.1275, 78.1580, "Dharmapuri"),
    "the nilgiris": (11.4916, 76.7337, "Ooty"),
    "namakkal": (11.2198, 78.1672, "Namakkal"),
    "karur": (10.9601, 78.0766, "Karur"),
    "ariyalur": (11.1408, 79.0787, "Ariyalur"),
    "perambalur": (11.2335, 78.8736, "Perambalur"),
    "tiruvarur": (10.7726, 79.6368, "Tiruvarur"),
    "thoothukkudi": (8.7642, 78.1348, "Thoothukudi"),
    "thoothukudi": (8.7642, 78.1348, "Thoothukudi"),
    "kallakurichi": (11.7375, 78.9618, "Kallakurichi"),
    "tenkasi": (8.9594, 77.3152, "Tenkasi"),
    "tirupattur": (12.4964, 78.5598, "Tirupattur"),
    "mayiladuthurai": (11.1014, 79.6527, "Mayiladuthurai"),
    # ── Karnataka (common) ──────────────────────────────────────────────────
    "bengaluru urban": (12.9716, 77.5946, "Bengaluru"),
    "bangalore urban": (12.9716, 77.5946, "Bengaluru"),
    "bangalore rural": (13.1986, 77.7066, "Bangalore Rural"),
    "mysuru": (12.2958, 76.6394, "Mysuru"),
    "tumkur": (13.3379, 77.1173, "Tumkur"),
    "kolar": (13.1360, 78.1294, "Kolar"),
    "ramanagara": (12.7186, 77.2830, "Ramanagara"),
    "chikkaballapura": (13.4356, 77.7319, "Chikkaballapura"),
    # ── Maharashtra (common) ────────────────────────────────────────────────
    "pune": (18.5204, 73.8567, "Pune"),
    "nashik": (19.9975, 73.7898, "Nashik"),
    "aurangabad": (19.8762, 75.3433, "Aurangabad"),
    "nagpur": (21.1458, 79.0882, "Nagpur"),
    "amravati": (20.9374, 77.7796, "Amravati"),
}


def _lookup_district_coords(name: str) -> "Optional[tuple[float, float, str]]":
    """Return hardcoded (lat, lon, display_name) for *name* if available.

    Tries: exact lowercase match → strip honorific prefixes → partial match.
    """
    import re as _re
    key = name.lower().strip()

    if key in DISTRICT_COORDS:
        return DISTRICT_COORDS[key]

    # Strip common honorific / administrative prefixes
    stripped = _re.sub(
        r'^(ysr|dr\.?|sri|shri|babu|baba)\s+',
        '',
        key,
        flags=_re.IGNORECASE,
    ).strip()
    if stripped in DISTRICT_COORDS:
        return DISTRICT_COORDS[stripped]

    # Partial / substring match (e.g. "b.r. ambedkar konaseema" → "konaseema")
    for k, v in DISTRICT_COORDS.items():
        if k in key or key in k:
            return v

    return None


def _normalize_district_for_geocoding(name: str) -> str:
    """Return a geocodable name for *name* (fallback when coords not found)."""
    import re as _re
    key = name.lower().strip()
    stripped = _re.sub(
        r'^(ysr|dr\.?|sri|shri|babu|baba)\s+',
        '',
        key,
        flags=_re.IGNORECASE,
    ).strip()
    if stripped and stripped != key:
        return stripped.title()
    return name


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
        """Resolve *district_name* coordinates and return extended forecast."""
        coords = await self._geocode(district_name)
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
        """Return (lat, lon, display_name) for *name*.

        First checks the hardcoded DISTRICT_COORDS table (instant, no network).
        Falls back to Open-Meteo geocoding API if not found.
        """
        # 1. Fast path: hardcoded coordinates
        coords = _lookup_district_coords(name)
        if coords is not None:
            return coords

        # 2. Slow path: geocoding API (may be blocked on some networks)
        params = {
            "name": _normalize_district_for_geocoding(name),
            "count": 1,
            "language": "en",
            "format": "json",
            "countryCode": "IN",
        }
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(OPEN_METEO_GEOCODING_URL, params=params)
                resp.raise_for_status()
                body = resp.json()
                results = body.get("results")
                if not results:
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

