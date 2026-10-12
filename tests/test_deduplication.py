"""Tests for duplicate alert detection and prevention."""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.alerts.deduplication import DeduplicationService
from app.database.models import Base, WeatherAlert
from app.utils.time import now_utc
from app.weather.schemas import AlertCandidate


@pytest.fixture
def test_db():
    """In-memory SQLite database session for unit tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_deduplication_detects_existing_alert(test_db):
    """Test that an alert already in DB with identical alert_key is recognized as duplicate."""
    fc_time = now_utc().replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    key = f"Chennai:RAIN_WARNING:{fc_time.strftime('%Y-%m-%dT%H:00')}"

    # Insert existing alert
    existing = WeatherAlert(
        location="Chennai",
        latitude=13.0827,
        longitude=80.2707,
        alert_type="RAIN_WARNING",
        severity="WARNING",
        forecast_time=fc_time,
        probability=85.0,
        rainfall_mm=4.0,
        message="Initial rain warning",
        alert_key=key,
        status="ACTIVE",
    )
    test_db.add(existing)
    test_db.commit()

    # Create candidate with same key
    cand_dup = AlertCandidate(
        type="RAIN_WARNING",
        severity="WARNING",
        forecast_time=fc_time,
        probability=85.0,
        rainfall_mm=4.0,
        message="Duplicate rain warning check",
        alert_key=key,
    )

    # Create candidate with a different, future forecast time (new event)
    future_fc = fc_time + timedelta(hours=12)
    future_key = f"Chennai:RAIN_WARNING:{future_fc.strftime('%Y-%m-%dT%H:00')}"
    cand_new = AlertCandidate(
        type="RAIN_WARNING",
        severity="WARNING",
        forecast_time=future_fc,
        probability=80.0,
        rainfall_mm=3.0,
        message="New subsequent rain warning",
        alert_key=future_key,
    )

    dedup = DeduplicationService(test_db)
    new_alerts, duplicate_alerts = dedup.filter_duplicates([cand_dup, cand_new])

    assert len(duplicate_alerts) == 1
    assert duplicate_alerts[0].alert_key == key

    assert len(new_alerts) == 1
    assert new_alerts[0].alert_key == future_key
