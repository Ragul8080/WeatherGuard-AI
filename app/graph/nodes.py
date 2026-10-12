"""Individual LangGraph execution nodes."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.ai.explanation import AIExplanationService
from app.alerts.deduplication import DeduplicationService
from app.alerts.rules import AlertRulesEngine
from app.config import settings
from app.database.connection import get_db_context
from app.database.models import (
    NotificationHistory,
    WeatherAlert,
    WeatherReading,
    WorkflowExecution,
)
from app.database.repositories import (
    NotificationRepository,
    UserPreferenceRepository,
    WeatherAlertRepository,
    WeatherReadingRepository,
    WorkflowExecutionRepository,
)
from app.graph.state import WeatherGuardState
from app.logging_config import logger
from app.notifications.email import EmailSender
from app.notifications.templates import render_alert_email
from app.utils.time import now_utc, parse_datetime
from app.weather.client import MockWeatherProvider, OpenMeteoClient
from app.weather.schemas import (
    AlertCandidate,
    HourlyForecastItem,
    WeatherForecastResponse,
)


def initialize_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 1: Initialize execution metadata and location defaults."""
    wf_id = state.get("workflow_id") or f"wf_{uuid.uuid4().hex[:10]}"
    started_at = state.get("started_at") or now_utc().isoformat()
    location = state.get("location") or settings.LOCATION_NAME
    latitude = state.get("latitude") if state.get("latitude") is not None else settings.LATITUDE
    longitude = state.get("longitude") if state.get("longitude") is not None else settings.LONGITUDE
    tz_name = state.get("timezone") or settings.TIMEZONE

    logger.info(f"[Workflow {wf_id}] Initializing for {location} ({latitude}, {longitude}).")

    res: WeatherGuardState = {
        "workflow_id": wf_id,
        "started_at": started_at,
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": tz_name,
        "workflow_status": "INITIALIZED",
        "alerts": [],
        "duplicate_alerts": [],
        "saved_alert_ids": [],
        "email_status": "PENDING",
        "notifications_recorded": 0,
        "error": None,
    }
    if "_mock_scenario" in state:
        res["_mock_scenario"] = state["_mock_scenario"]
    if "_mock_error" in state:
        res["_mock_error"] = state["_mock_error"]
    return res


def fetch_weather_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 2: Retrieve weather forecast from Open-Meteo or configured provider."""
    wf_id = state["workflow_id"]
    location = state["location"]
    lat = state["latitude"]
    lon = state["longitude"]
    tz_name = state["timezone"]

    logger.info(f"[Workflow {wf_id}] Fetching weather for {location}...")

    # Allow injecting a mock client through state for unit tests
    mock_scenario = state.get("_mock_scenario")
    mock_error = state.get("_mock_error")

    try:
        if mock_error:
            raise mock_error
        elif mock_scenario:
            provider = MockWeatherProvider(scenario=mock_scenario)
            forecast = provider.fetch_forecast(
                latitude=lat,
                longitude=lon,
                location_name=location,
                timezone_name=tz_name,
                forecast_days=settings.FORECAST_DAYS,
            )
        else:
            client = OpenMeteoClient()
            forecast = client.fetch_forecast(
                latitude=lat,
                longitude=lon,
                location_name=location,
                timezone_name=tz_name,
                forecast_days=settings.FORECAST_DAYS,
            )

        logger.info(
            f"[Workflow {wf_id}] Weather fetched successfully. "
            f"Received {len(forecast.hourly)} hourly forecast points."
        )

        return {
            "workflow_status": "FETCHED",
            "forecast": forecast.model_dump(mode="json"),
        }
    except Exception as e:
        logger.error(f"[Workflow {wf_id}] Weather fetch failed: {e}")
        return {
            "workflow_status": "FAILED",
            "error": f"Weather fetch failed: {e}",
        }


def validate_forecast_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 3: Verify the integrity of the retrieved forecast."""
    wf_id = state["workflow_id"]
    if state.get("error"):
        return state

    forecast_data = state.get("forecast")
    if not forecast_data or not forecast_data.get("hourly"):
        err = "Forecast data is empty or missing hourly array"
        logger.error(f"[Workflow {wf_id}] Validation error: {err}")
        return {
            "workflow_status": "FAILED",
            "error": err,
        }

    logger.info(f"[Workflow {wf_id}] Forecast validated successfully.")
    return {"workflow_status": "VALIDATED"}


def save_forecast_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 4: Persist forecast readings into the database."""
    wf_id = state["workflow_id"]
    if state.get("error"):
        return state

    forecast_data = state["forecast"]
    fetched_at = parse_datetime(forecast_data["fetched_at"], state["timezone"])
    location = state["location"]
    lat = state["latitude"]
    lon = state["longitude"]

    readings: List[WeatherReading] = []
    for item in forecast_data["hourly"]:
        fc_dt = parse_datetime(item["forecast_time"], state["timezone"])
        readings.append(
            WeatherReading(
                location=location,
                latitude=lat,
                longitude=lon,
                forecast_time=fc_dt,
                fetched_at=fetched_at,
                temperature_c=item.get("temperature_c"),
                humidity=item.get("humidity"),
                precipitation_probability=item.get("precipitation_probability"),
                precipitation_mm=item.get("precipitation_mm"),
                rain_mm=item.get("rain_mm"),
                weather_code=item.get("weather_code"),
                wind_speed_kmh=item.get("wind_speed_kmh"),
            )
        )

    try:
        with get_db_context() as db:
            repo = WeatherReadingRepository(db)
            repo.save_readings(readings)
        logger.info(f"[Workflow {wf_id}] Saved {len(readings)} readings to database.")
        return {"workflow_status": "SAVED"}
    except Exception as e:
        logger.error(f"[Workflow {wf_id}] Failed to save forecast: {e}")
        return {
            "workflow_status": "FAILED",
            "error": f"Failed to save readings: {e}",
        }


def analyse_forecast_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 5: Execute deterministic rules engine on forecast data."""
    wf_id = state["workflow_id"]
    if state.get("error"):
        return state

    forecast_data = state["forecast"]
    location = state["location"]

    # Reconstitute schemas
    items = [
        HourlyForecastItem(
            forecast_time=parse_datetime(it["forecast_time"], state["timezone"]),
            temperature_c=it.get("temperature_c"),
            humidity=it.get("humidity"),
            precipitation_probability=it.get("precipitation_probability"),
            precipitation_mm=it.get("precipitation_mm"),
            rain_mm=it.get("rain_mm"),
            weather_code=it.get("weather_code"),
            wind_speed_kmh=it.get("wind_speed_kmh"),
        )
        for it in forecast_data["hourly"]
    ]
    fc_resp = WeatherForecastResponse(
        location=location,
        latitude=state["latitude"],
        longitude=state["longitude"],
        timezone=state["timezone"],
        fetched_at=parse_datetime(forecast_data["fetched_at"], state["timezone"]),
        hourly=items,
    )

    with get_db_context() as db:
        pref_repo = UserPreferenceRepository(db)
        pref = pref_repo.get_preferences(location)

        if not pref.alert_enabled:
            logger.info(f"[Workflow {wf_id}] Alerts are globally disabled in preferences.")
            return {
                "workflow_status": "NO_ALERT",
                "alerts": [],
                "analysis": {"alert_required": False, "reason": "Alerts disabled by preference"},
            }

        engine = AlertRulesEngine(
            rain_probability_threshold=pref.rain_probability_threshold,
            min_rainfall_mm=pref.minimum_rainfall_mm,
            high_rainfall_mm=pref.high_rainfall_mm,
            low_temperature_threshold=pref.low_temperature_threshold,
            high_wind_threshold=pref.high_wind_threshold,
            horizon_hours=settings.ALERT_HORIZON_HOURS,
        )
        analysis = engine.evaluate_forecast(fc_resp)

    logger.info(
        f"[Workflow {wf_id}] Forecast analysis complete. "
        f"Alert required: {analysis.alert_required}, Candidate count: {len(analysis.alerts)}"
    )

    return {
        "analysis": analysis.model_dump(mode="json"),
        "alerts": [cand.model_dump(mode="json") for cand in analysis.alerts],
        "workflow_status": "ANALYZED",
    }


def check_alert_required_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 6: Determine if any candidate alerts need further processing."""
    wf_id = state["workflow_id"]
    if state.get("error"):
        return state

    alerts = state.get("alerts", [])
    if not alerts:
        logger.info(f"[Workflow {wf_id}] No weather conditions reached alert threshold.")
        return {"workflow_status": "NO_ALERT"}

    logger.info(f"[Workflow {wf_id}] {len(alerts)} alerts require deduplication check.")
    return {"workflow_status": "ALERT_EXISTS"}


def check_duplicate_alerts_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 7: Screen candidate alerts against database for deduplication."""
    wf_id = state["workflow_id"]
    if state.get("error"):
        return state

    candidates_raw = state.get("alerts", [])
    candidates = [
        AlertCandidate(
            type=c["type"],
            severity=c["severity"],
            forecast_time=parse_datetime(c["forecast_time"], state["timezone"]),
            probability=c.get("probability"),
            rainfall_mm=c.get("rainfall_mm"),
            wind_speed_kmh=c.get("wind_speed_kmh"),
            temperature_c=c.get("temperature_c"),
            message=c["message"],
            alert_key=c["alert_key"],
        )
        for c in candidates_raw
    ]

    with get_db_context() as db:
        dedup = DeduplicationService(db)
        new_cands, dup_cands = dedup.filter_duplicates(candidates)

    if not new_cands:
        logger.info(f"[Workflow {wf_id}] All candidate alerts have already been notified. Skipping.")
        return {
            "workflow_status": "DUPLICATE_SKIPPED",
            "alerts": [],
            "duplicate_alerts": [c.model_dump(mode="json") for c in dup_cands],
        }

    logger.info(
        f"[Workflow {wf_id}] Found {len(new_cands)} new alerts ({len(dup_cands)} duplicates skipped)."
    )
    return {
        "workflow_status": "NEW_ALERTS_QUALIFIED",
        "alerts": [c.model_dump(mode="json") for c in new_cands],
        "duplicate_alerts": [c.model_dump(mode="json") for c in dup_cands],
    }


def create_alerts_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 8: Persist qualified new alerts into weather_alerts table."""
    wf_id = state["workflow_id"]
    if state.get("error"):
        return state

    location = state["location"]
    lat = state["latitude"]
    lon = state["longitude"]
    tz_name = state["timezone"]

    saved_ids: List[int] = []
    with get_db_context() as db:
        repo = WeatherAlertRepository(db)
        for raw in state.get("alerts", []):
            fc_dt = parse_datetime(raw["forecast_time"], tz_name)
            alert = WeatherAlert(
                location=location,
                latitude=lat,
                longitude=lon,
                alert_type=raw["type"],
                severity=raw["severity"],
                forecast_time=fc_dt,
                probability=raw.get("probability"),
                rainfall_mm=raw.get("rainfall_mm"),
                message=raw["message"],
                alert_key=raw["alert_key"],
                status="ACTIVE",
            )
            created = repo.create_alert(alert)
            saved_ids.append(created.id)

    logger.info(f"[Workflow {wf_id}] Created {len(saved_ids)} alert records in database: {saved_ids}")
    return {
        "saved_alert_ids": saved_ids,
        "workflow_status": "ALERTS_CREATED",
    }


def generate_ai_explanation_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 9: Synthesize natural language explanation via Ollama or fallback."""
    wf_id = state["workflow_id"]
    if state.get("error"):
        return state

    saved_ids = state.get("saved_alert_ids", [])
    if not saved_ids:
        return state

    explanation = None
    with get_db_context() as db:
        alert_repo = WeatherAlertRepository(db)
        first_alert = db.get(WeatherAlert, saved_ids[0])
        if first_alert:
            expl_service = AIExplanationService()
            explanation = expl_service.generate_explanation(first_alert, user_timezone=state["timezone"])
            # Update all saved alerts in this run with explanation
            for aid in saved_ids:
                alert_repo.update_ai_explanation(aid, explanation)

    logger.info(f"[Workflow {wf_id}] AI explanation generated.")
    return {
        "ai_explanation": explanation,
        "workflow_status": "EXPLANATION_GENERATED",
    }


def send_email_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 10: Dispatch email notifications for the new alerts."""
    wf_id = state["workflow_id"]
    if state.get("error"):
        return state

    saved_ids = state.get("saved_alert_ids", [])
    if not saved_ids:
        return {"email_status": "SKIPPED"}

    sender = EmailSender()
    explanation = state.get("ai_explanation")
    tz_name = state["timezone"]

    overall_status = "SENT"
    with get_db_context() as db:
        pref_repo = UserPreferenceRepository(db)
        pref = pref_repo.get_preferences(state["location"])
        recipient = pref.email or settings.ALERT_RECIPIENT

        if not recipient or not settings.is_smtp_configured:
            logger.info(
                f"[Workflow {wf_id}] SMTP host or recipient unconfigured. Operating in safe MOCK mode."
            )
            overall_status = "MOCK_SENT"
        else:
            for aid in saved_ids:
                alert = db.get(WeatherAlert, aid)
                if alert:
                    subj, text, html = render_alert_email(
                        alert=alert,
                        ai_explanation=explanation,
                        user_timezone=tz_name,
                    )
                    try:
                        sender.send_email(recipient, subj, text, html)
                    except Exception as exc:
                        logger.error(f"[Workflow {wf_id}] Email delivery failed for alert {aid}: {exc}")
                        overall_status = "FAILED"

    return {"email_status": overall_status}


def record_notification_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 11: Audit log notification attempts in notification_history table."""
    wf_id = state["workflow_id"]
    saved_ids = state.get("saved_alert_ids", [])
    email_status = state.get("email_status", "PENDING")

    count = 0
    with get_db_context() as db:
        pref_repo = UserPreferenceRepository(db)
        notif_repo = NotificationRepository(db)
        pref = pref_repo.get_preferences(state["location"])
        recipient = pref.email or settings.ALERT_RECIPIENT or "unconfigured@local"

        for aid in saved_ids:
            history = NotificationHistory(
                alert_id=aid,
                recipient=recipient,
                attempted_at=now_utc(),
                sent_at=now_utc() if email_status in ("SENT", "MOCK_SENT") else None,
                status=email_status,
                error_message="Simulated mock dispatch" if email_status == "MOCK_SENT" else None,
                retry_count=0 if email_status != "FAILED" else 3,
            )
            notif_repo.record_attempt(history)
            count += 1

    logger.info(f"[Workflow {wf_id}] Recorded {count} notification history audit records.")
    return {"notifications_recorded": count}


def finalize_node(state: WeatherGuardState) -> WeatherGuardState:
    """Node 12: Finalize execution, persist workflow run, and produce summary."""
    wf_id = state["workflow_id"]
    completed_at = now_utc().isoformat()
    if state.get("error"):
        status = "FAILED"
    elif state.get("workflow_status") == "NO_ALERT":
        status = "NO_ALERT"
    elif state.get("workflow_status") == "DUPLICATE_SKIPPED":
        status = "DUPLICATE_SKIPPED"
    else:
        status = "COMPLETED"

    alerts_count = len(state.get("saved_alert_ids", []))

    # Persist observability record
    try:
        with get_db_context() as db:
            wf_repo = WorkflowExecutionRepository(db)
            exec_record = WorkflowExecution(
                workflow_id=wf_id,
                location=state["location"],
                started_at=parse_datetime(state["started_at"], state.get("timezone", "Asia/Kolkata")),
                completed_at=parse_datetime(completed_at, state.get("timezone", "Asia/Kolkata")),
                status=status,
                alerts_count=alerts_count,
                error=state.get("error"),
                details=f"Email status: {state.get('email_status')}, New: {alerts_count}, Dupes: {len(state.get('duplicate_alerts', []))}",
            )
            wf_repo.record_execution(exec_record)
    except Exception as e:
        logger.warning(f"[Workflow {wf_id}] Could not save workflow execution log: {e}")

    logger.info(f"[Workflow {wf_id}] Finished with status '{status}'. Alerts created: {alerts_count}.")
    return {
        "completed_at": completed_at,
        "workflow_status": status,
    }
