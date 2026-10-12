"""Pydantic API request and response schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: bool
    weather_api: bool
    ollama: bool
    smtp_configured: bool
    timestamp: datetime
    version: str


class WeatherReadingOut(BaseModel):
    id: int
    location: str
    latitude: float
    longitude: float
    forecast_time: datetime
    fetched_at: datetime
    temperature_c: Optional[float] = None
    humidity: Optional[float] = None
    precipitation_probability: Optional[float] = None
    precipitation_mm: Optional[float] = None
    rain_mm: Optional[float] = None
    weather_code: Optional[int] = None
    wind_speed_kmh: Optional[float] = None

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    location: str
    alert_type: str
    severity: str
    forecast_time: datetime
    triggered_at: datetime
    probability: Optional[float] = None
    rainfall_mm: Optional[float] = None
    message: str
    ai_explanation: Optional[str] = None
    status: str
    alert_key: str

    model_config = {"from_attributes": True}


class SettingsOut(BaseModel):
    id: int
    location: str
    email: Optional[str] = None
    latitude: float
    longitude: float
    timezone: str
    rain_probability_threshold: float
    minimum_rainfall_mm: float
    high_rainfall_mm: float
    low_temperature_threshold: float
    high_wind_threshold: float
    alert_enabled: bool

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    location: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    timezone: Optional[str] = None
    rain_probability_threshold: Optional[float] = Field(None, ge=0.0, le=100.0)
    minimum_rainfall_mm: Optional[float] = Field(None, ge=0.0)
    high_rainfall_mm: Optional[float] = Field(None, ge=0.0)
    low_temperature_threshold: Optional[float] = None
    high_wind_threshold: Optional[float] = Field(None, ge=0.0)
    alert_enabled: Optional[bool] = None


class WeatherCheckRequest(BaseModel):
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class WeatherCheckResponse(BaseModel):
    workflow_id: str
    workflow_status: str
    location: str
    alerts_count: int
    email_status: str
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class TestEmailRequest(BaseModel):
    recipient: Optional[str] = None


class TestEmailResponse(BaseModel):
    success: bool
    status: str
    message: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources_used: List[str] = Field(default_factory=list)
