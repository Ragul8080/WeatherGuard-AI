"""FastAPI endpoint route definitions."""

from datetime import datetime
from typing import List, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.ai.llm import get_ollama_client, is_ollama_available
from app.ai.prompts import CHAT_ASSISTANT_SYSTEM_PROMPT
from app.api.schemas import (
    AlertOut,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SettingsOut,
    SettingsUpdate,
    TestEmailRequest,
    TestEmailResponse,
    WeatherCheckRequest,
    WeatherCheckResponse,
    WeatherReadingOut,
)
from app.config import settings
from app.database.connection import get_db
from app.database.models import UserPreference
from app.database.repositories import (
    UserPreferenceRepository,
    WeatherAlertRepository,
    WeatherReadingRepository,
)
from app.graph.workflow import run_workflow
from app.langchain.tools import (
    get_alert_history,
    get_user_preferences,
    get_weather_history,
)
from app.logging_config import logger
from app.notifications.email import EmailSender
from app.utils.time import now_utc
from app.weather.client import OpenMeteoClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Application Health Check")
async def health_check(db: Session = Depends(get_db)):
    """Verify application health and connectivity of database, weather API, and Ollama."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error(f"Health check DB error: {e}")

    weather_ok = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(
                settings.OPEN_METEO_BASE_URL,
                params={"latitude": 13.0, "longitude": 80.0, "forecast_days": 1},
            )
            weather_ok = resp.status_code in (200, 400)
    except Exception:
        pass

    ollama_ok = is_ollama_available()

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        database=db_ok,
        weather_api=weather_ok,
        ollama=ollama_ok,
        smtp_configured=settings.is_smtp_configured,
        timestamp=now_utc(),
        version=__version__,
    )


@router.get("/api/weather/latest", response_model=Optional[WeatherReadingOut], summary="Get Latest Weather Reading")
def get_latest_weather(
    location: Optional[str] = Query(None, description="Location name"),
    db: Session = Depends(get_db),
):
    """Retrieve the single latest recorded forecast/reading for a location."""
    repo = WeatherReadingRepository(db)
    loc = location or settings.LOCATION_NAME
    reading = repo.get_latest_reading(loc)
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No weather readings available for location '{loc}'. Run a check first.",
        )
    return reading


@router.get("/api/weather/history", response_model=List[WeatherReadingOut], summary="Get Weather Readings History")
def get_weather_history_route(
    location: Optional[str] = Query(None),
    limit: int = Query(48, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Retrieve historical weather readings."""
    repo = WeatherReadingRepository(db)
    loc = location or settings.LOCATION_NAME
    return repo.get_recent_readings(location=loc, limit=limit)


@router.get("/api/weather/forecast", summary="Get Current Live Forecast")
def get_forecast(
    latitude: Optional[float] = Query(None),
    longitude: Optional[float] = Query(None),
    location: Optional[str] = Query(None),
    days: int = Query(2, ge=1, le=7),
):
    """Fetch live multi-day forecast directly from Open-Meteo."""
    client = OpenMeteoClient()
    lat = latitude if latitude is not None else settings.LATITUDE
    lon = longitude if longitude is not None else settings.LONGITUDE
    loc = location or settings.LOCATION_NAME

    try:
        forecast = client.fetch_forecast(
            latitude=lat,
            longitude=lon,
            location_name=loc,
            forecast_days=days,
        )
        return forecast.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch forecast from Open-Meteo: {e}",
        )


@router.get("/api/alerts", response_model=List[AlertOut], summary="Get Alerts")
def get_alerts(
    location: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retrieve list of triggered weather alerts."""
    repo = WeatherAlertRepository(db)
    return repo.get_latest_alerts(location=location, limit=limit)


@router.get("/api/alerts/latest", response_model=Optional[AlertOut], summary="Get Latest Alert")
def get_latest_alert(
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Retrieve the single most recent alert."""
    repo = WeatherAlertRepository(db)
    alerts = repo.get_latest_alerts(location=location, limit=1)
    if not alerts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No alerts currently on record.",
        )
    return alerts[0]


@router.get("/api/settings", response_model=SettingsOut, summary="Get User Preferences and Thresholds")
def get_settings(
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Retrieve current configured thresholds and monitoring settings."""
    repo = UserPreferenceRepository(db)
    return repo.get_preferences(location or settings.LOCATION_NAME)


@router.put("/api/settings", response_model=SettingsOut, summary="Update Settings")
def update_settings(
    update_data: SettingsUpdate,
    db: Session = Depends(get_db),
):
    """Update monitoring location and alert thresholds."""
    repo = UserPreferenceRepository(db)
    pref = repo.get_preferences(update_data.location or settings.LOCATION_NAME)

    if update_data.email is not None:
        pref.email = update_data.email
    if update_data.location is not None:
        pref.location = update_data.location
    if update_data.latitude is not None:
        pref.latitude = update_data.latitude
    if update_data.longitude is not None:
        pref.longitude = update_data.longitude
    if update_data.timezone is not None:
        pref.timezone = update_data.timezone
    if update_data.rain_probability_threshold is not None:
        pref.rain_probability_threshold = update_data.rain_probability_threshold
    if update_data.minimum_rainfall_mm is not None:
        pref.minimum_rainfall_mm = update_data.minimum_rainfall_mm
    if update_data.high_rainfall_mm is not None:
        pref.high_rainfall_mm = update_data.high_rainfall_mm
    if update_data.low_temperature_threshold is not None:
        pref.low_temperature_threshold = update_data.low_temperature_threshold
    if update_data.high_wind_threshold is not None:
        pref.high_wind_threshold = update_data.high_wind_threshold
    if update_data.alert_enabled is not None:
        pref.alert_enabled = update_data.alert_enabled

    return repo.update_preferences(pref)


@router.post("/api/weather/check", response_model=WeatherCheckResponse, summary="Trigger Manual Weather Check")
def trigger_weather_check(
    req: Optional[WeatherCheckRequest] = None,
):
    """Manually invoke one execution of the LangGraph autonomous monitoring workflow."""
    location = req.location if req else None
    lat = req.latitude if req else None
    lon = req.longitude if req else None

    logger.info("Manual weather check initiated via API.")
    state = run_workflow(location=location, latitude=lat, longitude=lon)

    return WeatherCheckResponse(
        workflow_id=state.get("workflow_id", "unknown"),
        workflow_status=state.get("workflow_status", "UNKNOWN"),
        location=state.get("location", settings.LOCATION_NAME),
        alerts_count=len(state.get("saved_alert_ids", [])),
        email_status=state.get("email_status", "PENDING"),
        started_at=state.get("started_at", ""),
        completed_at=state.get("completed_at"),
        error=state.get("error"),
    )


@router.post("/api/alerts/test-email", response_model=TestEmailResponse, summary="Send Test Alert Email")
def test_email(
    req: Optional[TestEmailRequest] = None,
    db: Session = Depends(get_db),
):
    """Send a diagnostic test email to verify SMTP configuration."""
    pref_repo = UserPreferenceRepository(db)
    pref = pref_repo.get_preferences()
    target_email = (req.recipient if req and req.recipient else None) or pref.email or settings.ALERT_RECIPIENT

    if not target_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recipient email specified in request, user preferences, or ALERT_RECIPIENT env.",
        )

    sender = EmailSender()
    if not settings.is_smtp_configured:
        return TestEmailResponse(
            success=True,
            status="MOCK_MODE",
            message=f"SMTP host not configured. Test email to {target_email} simulated successfully in MOCK mode.",
        )

    subject = "[TEST] WeatherGuard AI Test Notification"
    text = f"This is an automated test message from WeatherGuard AI sent to {target_email} at {now_utc().isoformat()}."
    html = f"<div style='font-family:sans-serif;'><h3>WeatherGuard AI Test</h3><p>{text}</p></div>"

    try:
        sender.send_email(target_email, subject, text, html)
        return TestEmailResponse(
            success=True,
            status="SENT",
            message=f"Test email successfully dispatched to {target_email}.",
        )
    except Exception as e:
        logger.error(f"Test email dispatch failed: {e}")
        return TestEmailResponse(
            success=False,
            status="FAILED",
            message=f"Failed to send email via SMTP: {e}",
        )


@router.post("/api/chat", response_model=ChatResponse, summary="Conversational Weather Assistant (Optional AI)")
def chat_assistant(
    req: ChatRequest,
    db: Session = Depends(get_db),
):
    """Ask questions about weather conditions, historical data, and alerts using LangChain tools."""
    llm = get_ollama_client()
    if not llm:
        # Fallback response if Ollama is not running
        repo = WeatherReadingRepository(db)
        alert_repo = WeatherAlertRepository(db)
        latest = repo.get_latest_reading(settings.LOCATION_NAME)
        alerts = alert_repo.get_latest_alerts(settings.LOCATION_NAME, limit=3)

        fallback_msg = (
            f"Ollama local LLM is currently unavailable, so I am providing direct system facts:\n"
            f"- Location: {settings.LOCATION_NAME}\n"
            f"- Current Temperature: {latest.temperature_c if latest else 'N/A'}°C\n"
            f"- Rain Probability: {latest.precipitation_probability if latest else 'N/A'}%\n"
            f"- Active Alerts Recorded: {len(alerts)}\n"
            f"Start Ollama with 'ollama run {settings.OLLAMA_MODEL}' for conversational AI responses."
        )
        return ChatResponse(reply=fallback_msg, sources_used=["local_database"])

    try:
        # Use LangChain Ollama chat with system instructions
        from langchain_core.messages import HumanMessage, SystemMessage

        user_q = req.message
        # Gather local context to prevent hallucination
        repo = WeatherReadingRepository(db)
        latest = repo.get_latest_reading(settings.LOCATION_NAME)
        alerts = WeatherAlertRepository(db).get_latest_alerts(settings.LOCATION_NAME, limit=3)

        context_str = (
            f"Location: {settings.LOCATION_NAME}\n"
            f"Latest Reading: Temp={latest.temperature_c if latest else 'N/A'}C, "
            f"Rain Prob={latest.precipitation_probability if latest else 'N/A'}%, "
            f"Rain MM={latest.rain_mm if latest else 'N/A'}mm\n"
            f"Recent Alerts: {', '.join([a.alert_type for a in alerts]) if alerts else 'None'}\n"
        )

        messages = [
            SystemMessage(content=CHAT_ASSISTANT_SYSTEM_PROMPT + "\nCurrent Context:\n" + context_str),
            HumanMessage(content=user_q),
        ]
        res = llm.invoke(messages)
        content = res.content if hasattr(res, "content") else str(res)
        return ChatResponse(reply=content, sources_used=["open_meteo", "database"])
    except Exception as exc:
        return ChatResponse(
            reply=f"Unable to process chat request through Ollama: {exc}",
            sources_used=[],
        )
