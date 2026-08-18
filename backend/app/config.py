import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ingres_ai.db").replace("\\", "/")
    GEMINI_API_KEY: str = ""
    JWT_SECRET_KEY: str = "supersecretkeychangeinproduction12345678"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 1 day
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    # Weather configuration
    WEATHER_CACHE_TTL: int = 600  # seconds, default 10 minutes
    WEATHER_FORECAST_DAYS: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
