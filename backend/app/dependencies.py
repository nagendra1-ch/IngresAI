"""
Dependency injection helpers for FastAPI routes.
"""
from functools import lru_cache
from app.services.weather_service import WeatherService


@lru_cache(maxsize=1)
def _get_cached_weather_service() -> WeatherService:
    """Singleton WeatherService instance (cached for lifetime of the process)."""
    return WeatherService()


def get_weather_service() -> WeatherService:
    """FastAPI dependency that returns the singleton WeatherService."""
    return _get_cached_weather_service()
