"""Tests for database repositories and models."""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    Base,
    NotificationHistory,
    UserPreference,
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
from app.utils.time import now_utc


@pytest.fixture
def session():
    """Create in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_weather_reading_repository(session):
    """Test saving and querying weather readings."""
    repo = WeatherReadingRepository(session)
    now = now_utc()

    readings = [
        WeatherReading(
            location="Chennai",
            latitude=13.0827,
            longitude=80.2707,
            forecast_time=now + timedelta(hours=i),
            fetched_at=now,
            temperature_c=28.0 + i,
            humidity=65.0,
            precipitation_probability=10.0 * i,
            precipitation_mm=0.5 * i,
            rain_mm=0.5 * i,
            weather_code=1,
            wind_speed_kmh=12.0,
        )
        for i in range(5)
    ]
    saved_count = repo.save_readings(readings)
    session.commit()
    assert saved_count == 5

    latest = repo.get_latest_reading("Chennai")
    assert latest is not None
    assert latest.location == "Chennai"

    history = repo.get_recent_readings("Chennai", limit=10)
    assert len(history) == 5


def test_weather_alert_repository(session):
    """Test creating and retrieving alerts and uniqueness."""
    repo = WeatherAlertRepository(session)
    now = now_utc()
    key = f"Chennai:RAIN_WARNING:{now.strftime('%Y-%m-%dT%H:00')}"

    alert = WeatherAlert(
        location="Chennai",
        latitude=13.0827,
        longitude=80.2707,
        alert_type="RAIN_WARNING",
        severity="WARNING",
        forecast_time=now + timedelta(hours=1),
        probability=85.0,
        rainfall_mm=3.2,
        message="Rain warning message",
        alert_key=key,
        status="ACTIVE",
    )
    created = repo.create_alert(alert)
    session.commit()

    assert created.id is not None
    assert created.alert_key == key

    queried = repo.get_alert_by_key(key)
    assert queried is not None
    assert queried.id == created.id

    repo.update_ai_explanation(created.id, "AI explanation update test")
    session.commit()
    assert repo.get_alert_by_key(key).ai_explanation == "AI explanation update test"


def test_notification_history_repository(session):
    """Test recording notifications and checking dispatch status."""
    alert_repo = WeatherAlertRepository(session)
    notif_repo = NotificationRepository(session)
    now = now_utc()

    alert = WeatherAlert(
        location="Chennai",
        latitude=13.0827,
        longitude=80.2707,
        alert_type="HIGH_WIND",
        severity="WARNING",
        forecast_time=now + timedelta(hours=2),
        message="High wind",
        alert_key="Chennai:HIGH_WIND:test",
    )
    saved_alert = alert_repo.create_alert(alert)
    session.commit()

    history = NotificationHistory(
        alert_id=saved_alert.id,
        recipient="user@example.com",
        status="SENT",
        sent_at=now,
    )
    notif_repo.record_attempt(history)
    session.commit()

    attempts = notif_repo.get_notifications_for_alert(saved_alert.id)
    assert len(attempts) == 1
    assert attempts[0].status == "SENT"
    assert notif_repo.has_successful_notification(saved_alert.id)


def test_user_preferences_repository(session):
    """Test fetching and updating user preferences."""
    repo = UserPreferenceRepository(session)
    pref = repo.get_preferences("Chennai")
    session.commit()
    assert pref.location == "Chennai"
    assert pref.rain_probability_threshold == 70.0

    pref.rain_probability_threshold = 60.0
    pref.email = "custom@example.com"
    repo.update_preferences(pref)
    session.commit()

    updated = repo.get_preferences("Chennai")
    assert updated.rain_probability_threshold == 60.0
    assert updated.email == "custom@example.com"
