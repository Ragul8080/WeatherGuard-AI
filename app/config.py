"""Configuration management for WeatherGuard AI."""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    APP_ENV: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./weather.db"

    # Default Weather Location
    LATITUDE: float = 13.0827
    LONGITUDE: float = 80.2707
    LOCATION_NAME: str = "Chennai"
    TIMEZONE: str = "Asia/Kolkata"

    # Weather API
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    FORECAST_DAYS: int = 2
    WEATHER_TIMEOUT_SECONDS: float = 10.0
    WEATHER_MAX_RETRIES: int = 3

    # Scheduler & Horizon
    WEATHER_CHECK_INTERVAL_MINUTES: int = 60
    ALERT_HORIZON_HOURS: int = 6

    # Alert Thresholds (Deterministic Defaults)
    RAIN_PROBABILITY_THRESHOLD: float = 70.0
    MIN_RAINFALL_MM: float = 1.0
    HIGH_RAINFALL_MM: float = 10.0
    LOW_TEMPERATURE_C: float = 15.0
    HIGH_WIND_KMH: float = 40.0

    # Local AI / Ollama Configuration
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT_SECONDS: float = 15.0

    # SMTP Email Configuration
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_SENDER_EMAIL: str = "alerts@weatherguard.ai"
    ALERT_RECIPIENT: str = ""
    EMAIL_MAX_RETRIES: int = 3

    # FastAPI Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["*"])

    @property
    def is_smtp_configured(self) -> bool:
        """Check whether minimum SMTP details are provided."""
        return bool(self.SMTP_HOST and self.ALERT_RECIPIENT)


settings = Settings()
