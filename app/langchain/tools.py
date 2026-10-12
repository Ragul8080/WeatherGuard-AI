"""Controlled LangChain tools for AI assistant and workflows."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.alerts.rules import AlertRulesEngine
from app.config import settings
from app.database.connection import get_db_context
from app.database.models import WeatherAlert
from app.database.repositories import (
    NotificationRepository,
    UserPreferenceRepository,
    WeatherAlertRepository,
    WeatherReadingRepository,
)
from app.notifications.email import EmailSender
from app.utils.time import now_utc
from app.weather.client import OpenMeteoClient


class FetchWeatherInput(BaseModel):
    latitude: float = Field(default=13.0827, description="Latitude of the location")
    longitude: float = Field(default=80.2707, description="Longitude of the location")
    location_name: str = Field(default="Chennai", description="Name of the city or location")
    forecast_days: int = Field(default=2, description="Days of forecast to fetch (1-7)")


class WeatherHistoryInput(BaseModel):
    location: str = Field(default="Chennai", description="Location name to query")
    limit: int = Field(default=24, description="Max number of readings to return")


class AnalyseWeatherInput(BaseModel):
    location_name: str = Field(default="Chennai", description="Location name")
    latitude: float = Field(default=13.0827, description="Latitude of location")
    longitude: float = Field(default=80.2707, description="Longitude of location")
    horizon_hours: int = Field(default=6, description="Hours ahead to evaluate")


class AlertHistoryInput(BaseModel):
    location: Optional[str] = Field(default=None, description="Optional location filter")
    limit: int = Field(default=10, description="Max number of alerts to return")


class CreateAlertInput(BaseModel):
    location: str = Field(..., description="Location name")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    alert_type: str = Field(..., description="Type of alert e.g. RAIN_WARNING, HIGH_RAINFALL")
    severity: str = Field(default="WARNING", description="Severity level: NORMAL, WARNING, HIGH")
    forecast_time: str = Field(..., description="ISO 8601 forecast time")
    message: str = Field(..., description="Alert description message")
    probability: Optional[float] = Field(default=None, description="Precipitation probability %")
    rainfall_mm: Optional[float] = Field(default=None, description="Rainfall in mm")


class SendEmailInput(BaseModel):
    recipient: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    message: str = Field(..., description="Plain text or summary message")


class UserPreferencesInput(BaseModel):
    location: Optional[str] = Field(default=None, description="Location to get thresholds for")


@tool("fetch_weather", args_schema=FetchWeatherInput)
def fetch_weather(
    latitude: float = 13.0827,
    longitude: float = 80.2707,
    location_name: str = "Chennai",
    forecast_days: int = 2,
) -> Dict[str, Any]:
    """Fetch live forecast from Open-Meteo for a specific coordinate and location."""
    client = OpenMeteoClient()
    response = client.fetch_forecast(
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        forecast_days=forecast_days,
    )
    first_few = [
        {
            "time": item.forecast_time.isoformat(),
            "temp_c": item.temperature_c,
            "rain_prob": item.precipitation_probability,
            "rain_mm": item.rain_mm,
            "wind_kmh": item.wind_speed_kmh,
        }
        for item in response.hourly[:12]
    ]
    return {
        "location": response.location,
        "fetched_at": response.fetched_at.isoformat(),
        "total_hours": len(response.hourly),
        "sample_forecast": first_few,
    }


@tool("get_weather_history", args_schema=WeatherHistoryInput)
def get_weather_history(location: str = "Chennai", limit: int = 24) -> List[Dict[str, Any]]:
    """Retrieve historical stored weather readings for a location from the local database."""
    with get_db_context() as db:
        repo = WeatherReadingRepository(db)
        readings = repo.get_recent_readings(location=location, limit=limit)
        return [
            {
                "time": r.forecast_time.isoformat(),
                "temperature_c": r.temperature_c,
                "humidity": r.humidity,
                "rain_probability": r.precipitation_probability,
                "rain_mm": r.rain_mm,
                "wind_kmh": r.wind_speed_kmh,
            }
            for r in readings
        ]


@tool("analyse_weather", args_schema=AnalyseWeatherInput)
def analyse_weather(
    location_name: str = "Chennai",
    latitude: float = 13.0827,
    longitude: float = 80.2707,
    horizon_hours: int = 6,
) -> Dict[str, Any]:
    """Fetch latest weather and evaluate whether safety alert thresholds are breached."""
    client = OpenMeteoClient()
    forecast = client.fetch_forecast(
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
    )
    with get_db_context() as db:
        pref_repo = UserPreferenceRepository(db)
        pref = pref_repo.get_preferences(location_name)
        engine = AlertRulesEngine(
            rain_probability_threshold=pref.rain_probability_threshold,
            min_rainfall_mm=pref.minimum_rainfall_mm,
            high_rainfall_mm=pref.high_rainfall_mm,
            low_temperature_threshold=pref.low_temperature_threshold,
            high_wind_threshold=pref.high_wind_threshold,
            horizon_hours=horizon_hours,
        )
        analysis = engine.evaluate_forecast(forecast)
        return {
            "alert_required": analysis.alert_required,
            "max_rain_probability": analysis.max_rain_probability,
            "max_rainfall_mm": analysis.max_rainfall_mm,
            "min_temperature_c": analysis.min_temperature_c,
            "max_wind_speed_kmh": analysis.max_wind_speed_kmh,
            "alerts": [a.model_dump() for a in analysis.alerts],
        }


@tool("get_alert_history", args_schema=AlertHistoryInput)
def get_alert_history(location: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Query recent alerts triggered and stored in the database."""
    with get_db_context() as db:
        repo = WeatherAlertRepository(db)
        alerts = repo.get_latest_alerts(location=location, limit=limit)
        return [
            {
                "id": a.id,
                "location": a.location,
                "type": a.alert_type,
                "severity": a.severity,
                "forecast_time": a.forecast_time.isoformat(),
                "triggered_at": a.triggered_at.isoformat(),
                "message": a.message,
                "ai_explanation": a.ai_explanation,
            }
            for a in alerts
        ]


@tool("create_weather_alert", args_schema=CreateAlertInput)
def create_weather_alert(
    location: str,
    latitude: float,
    longitude: float,
    alert_type: str,
    severity: str,
    forecast_time: str,
    message: str,
    probability: Optional[float] = None,
    rainfall_mm: Optional[float] = None,
) -> Dict[str, Any]:
    """Manually insert and store a new weather alert in the system."""
    with get_db_context() as db:
        repo = WeatherAlertRepository(db)
        fc_dt = datetime.fromisoformat(forecast_time)
        if fc_dt.tzinfo is None:
            fc_dt = fc_dt.replace(tzinfo=timezone.utc)
        alert_key = f"{location}:{alert_type}:{fc_dt.strftime('%Y-%m-%dT%H:00')}"
        existing = repo.get_alert_by_key(alert_key)
        if existing:
            return {"status": "DUPLICATE", "alert_id": existing.id, "alert_key": alert_key}
        alert = WeatherAlert(
            location=location,
            latitude=latitude,
            longitude=longitude,
            alert_type=alert_type,
            severity=severity,
            forecast_time=fc_dt,
            probability=probability,
            rainfall_mm=rainfall_mm,
            message=message,
            alert_key=alert_key,
        )
        saved = repo.create_alert(alert)
        return {"status": "CREATED", "alert_id": saved.id, "alert_key": alert_key}


@tool("send_weather_email", args_schema=SendEmailInput)
def send_weather_email(recipient: str, subject: str, message: str) -> Dict[str, Any]:
    """Send an alert email to the recipient with safe mock fallback."""
    sender = EmailSender()
    try:
        sent = sender.send_email(
            recipient=recipient,
            subject=subject,
            plain_text=message,
            html_content=f"<p>{message}</p>",
        )
        return {"success": sent, "recipient": recipient, "mode": "LIVE" if sent else "MOCK"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool("get_user_preferences", args_schema=UserPreferencesInput)
def get_user_preferences(location: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve safety threshold preferences configured for a location."""
    with get_db_context() as db:
        repo = UserPreferenceRepository(db)
        pref = repo.get_preferences(location)
        return {
            "location": pref.location,
            "email": pref.email,
            "rain_probability_threshold": pref.rain_probability_threshold,
            "minimum_rainfall_mm": pref.minimum_rainfall_mm,
            "high_rainfall_mm": pref.high_rainfall_mm,
            "low_temperature_threshold": pref.low_temperature_threshold,
            "high_wind_threshold": pref.high_wind_threshold,
            "alert_enabled": pref.alert_enabled,
        }
