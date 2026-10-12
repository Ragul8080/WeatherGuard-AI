"""Database seeding script for local development and dashboard demonstration."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_db_context, init_db
from app.database.models import (
    NotificationHistory,
    UserPreference,
    WeatherAlert,
    WeatherReading,
    WorkflowExecution,
)
from app.logging_config import logger
from app.utils.time import now_utc


def seed():
    """Populate database with sample user preferences and weather data."""
    init_db()
    logger.info("Seeding sample data...")

    with get_db_context() as db:
        # 1. User Preference
        pref = db.query(UserPreference).filter_by(location="Chennai").first()
        if not pref:
            pref = UserPreference(
                location="Chennai",
                email="alert-tester@example.com",
                latitude=13.0827,
                longitude=80.2707,
                timezone="Asia/Kolkata",
                rain_probability_threshold=70.0,
                minimum_rainfall_mm=1.0,
                high_rainfall_mm=10.0,
                low_temperature_threshold=15.0,
                high_wind_threshold=40.0,
                alert_enabled=True,
            )
            db.add(pref)
            db.flush()
            logger.info("Created default user preferences for Chennai.")

        # 2. Historical & Forecast Readings
        now = now_utc().replace(minute=0, second=0, microsecond=0)
        existing_readings = db.query(WeatherReading).filter_by(location="Chennai").count()
        if existing_readings < 24:
            readings = []
            for h in range(-12, 36):
                fc_time = now + timedelta(hours=h)
                temp = 29.5 + (2.0 if 10 <= fc_time.hour <= 16 else -2.5)
                prob = 80.0 if 2 <= h <= 5 else 15.0
                rain = 3.5 if 2 <= h <= 5 else 0.0
                wind = 18.0 + (5.0 if h % 3 == 0 else 0.0)
                readings.append(
                    WeatherReading(
                        location="Chennai",
                        latitude=13.0827,
                        longitude=80.2707,
                        forecast_time=fc_time,
                        fetched_at=now,
                        temperature_c=round(temp, 1),
                        humidity=68.0,
                        precipitation_probability=prob,
                        precipitation_mm=rain,
                        rain_mm=rain,
                        weather_code=61 if rain > 0 else 1,
                        wind_speed_kmh=round(wind, 1),
                    )
                )
            db.add_all(readings)
            db.flush()
            logger.info(f"Seeded {len(readings)} weather readings.")

        # 3. Sample Alert & Notification
        alert_key = f"Chennai:RAIN_WARNING:{(now + timedelta(hours=3)).strftime('%Y-%m-%dT%H:00')}"
        existing_alert = db.query(WeatherAlert).filter_by(alert_key=alert_key).first()
        if not existing_alert:
            sample_alert = WeatherAlert(
                location="Chennai",
                latitude=13.0827,
                longitude=80.2707,
                alert_type="RAIN_WARNING",
                severity="WARNING",
                forecast_time=now + timedelta(hours=3),
                triggered_at=now,
                probability=80.0,
                rainfall_mm=3.5,
                message="Rain expected for Chennai: 80% probability with 3.5 mm precipitation.",
                ai_explanation=(
                    "Rain is expected across Chennai in approximately 3 hours. "
                    "The model forecasts an 80% precipitation chance and 3.5 mm rainfall. "
                    "Remember to take an umbrella if travelling outdoors."
                ),
                alert_key=alert_key,
                status="ACTIVE",
            )
            db.add(sample_alert)
            db.flush()

            notif = NotificationHistory(
                alert_id=sample_alert.id,
                recipient="alert-tester@example.com",
                attempted_at=now,
                sent_at=now,
                status="MOCK_SENT",
                error_message="Simulated mock dispatch for local demonstration",
                retry_count=0,
            )
            db.add(notif)
            db.flush()
            logger.info("Seeded sample weather alert and notification history.")

        # 4. Sample Workflow Execution
        existing_exec = db.query(WorkflowExecution).first()
        if not existing_exec:
            wf_exec = WorkflowExecution(
                workflow_id="wf_demo_init",
                location="Chennai",
                started_at=now,
                completed_at=now + timedelta(seconds=2),
                status="ALERT_SENT",
                alerts_count=1,
                details="Seeded baseline execution",
            )
            db.add(wf_exec)
            db.flush()
            logger.info("Seeded sample workflow execution record.")

    print("SUCCESS: Sample data seeded successfully.")


if __name__ == "__main__":
    seed()
