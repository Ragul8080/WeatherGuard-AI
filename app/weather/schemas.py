"""Pydantic schemas for weather data and analysis."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class HourlyForecastItem(BaseModel):
    """Normalized single hour forecast observation."""

    forecast_time: datetime
    temperature_c: Optional[float] = None
    humidity: Optional[float] = None
    precipitation_probability: Optional[float] = None
    precipitation_mm: Optional[float] = None
    rain_mm: Optional[float] = None
    weather_code: Optional[int] = None
    wind_speed_kmh: Optional[float] = None


class WeatherForecastResponse(BaseModel):
    """Complete forecast response holding parsed hourly data points."""

    location: str
    latitude: float
    longitude: float
    timezone: str
    fetched_at: datetime
    hourly: List[HourlyForecastItem] = Field(default_factory=list)


class AlertCandidate(BaseModel):
    """Candidate alert evaluated by the deterministic rules engine."""

    type: str  # RAIN_WARNING, HIGH_RAINFALL, LOW_TEMPERATURE, HIGH_WIND
    severity: str  # NORMAL, INFORMATIONAL, WARNING, HIGH
    forecast_time: datetime
    probability: Optional[float] = None
    rainfall_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    temperature_c: Optional[float] = None
    message: str
    alert_key: str


class WeatherAnalysisResult(BaseModel):
    """Structured weather evaluation for the evaluated horizon."""

    alert_required: bool
    horizon_hours: int
    evaluated_at: datetime
    location: str
    max_rain_probability: float = 0.0
    total_expected_precipitation_mm: float = 0.0
    max_rainfall_mm: float = 0.0
    min_temperature_c: float = 999.0
    max_wind_speed_kmh: float = 0.0
    weather_codes: List[int] = Field(default_factory=list)
    alerts: List[AlertCandidate] = Field(default_factory=list)
