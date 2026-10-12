"""Repository layer for database operations."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.database.models import (
    NotificationHistory,
    UserPreference,
    WeatherAlert,
    WeatherReading,
    WorkflowExecution,
)
from app.logging_config import logger


class WeatherReadingRepository:
    """Data access repository for weather readings."""

    def __init__(self, db: Session):
        self.db = db

    def save_readings(self, readings: List[WeatherReading]) -> int:
        """Batch save weather readings."""
        if not readings:
            return 0
        try:
            self.db.add_all(readings)
            self.db.flush()
            logger.info(f"Saved {len(readings)} weather readings to database.")
            return len(readings)
        except Exception as e:
            logger.error(f"Error saving weather readings: {e}")
            raise

    def get_latest_reading(self, location: str) -> Optional[WeatherReading]:
        """Fetch the single most recently fetched weather reading."""
        stmt = (
            select(WeatherReading)
            .where(WeatherReading.location == location)
            .order_by(desc(WeatherReading.forecast_time))
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def get_recent_readings(
        self,
        location: str,
        limit: int = 48,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[WeatherReading]:
        """Retrieve recent weather readings with optional time filtering."""
        stmt = select(WeatherReading).where(WeatherReading.location == location)
        if start_date:
            stmt = stmt.where(WeatherReading.forecast_time >= start_date)
        if end_date:
            stmt = stmt.where(WeatherReading.forecast_time <= end_date)
        stmt = stmt.order_by(desc(WeatherReading.forecast_time)).limit(limit)
        results = self.db.execute(stmt).scalars().all()
        return list(results)

    def get_forecast_horizon(
        self,
        location: str,
        start_time: datetime,
        hours: int = 6,
    ) -> List[WeatherReading]:
        """Fetch forecast readings for a given horizon window."""
        end_time = start_time + timedelta(hours=hours)
        stmt = (
            select(WeatherReading)
            .where(
                WeatherReading.location == location,
                WeatherReading.forecast_time >= start_time,
                WeatherReading.forecast_time <= end_time,
            )
            .order_by(WeatherReading.forecast_time.asc())
        )
        results = self.db.execute(stmt).scalars().all()
        return list(results)


class WeatherAlertRepository:
    """Data access repository for weather alerts."""

    def __init__(self, db: Session):
        self.db = db

    def create_alert(self, alert: WeatherAlert) -> WeatherAlert:
        """Persist a new weather alert."""
        try:
            self.db.add(alert)
            self.db.flush()
            self.db.refresh(alert)
            logger.info(f"Created weather alert ID {alert.id} with key '{alert.alert_key}'.")
            return alert
        except Exception as e:
            logger.error(f"Failed to create weather alert: {e}")
            raise

    def get_alert_by_key(self, alert_key: str) -> Optional[WeatherAlert]:
        """Lookup an alert by its unique idempotency key."""
        stmt = select(WeatherAlert).where(WeatherAlert.alert_key == alert_key)
        return self.db.execute(stmt).scalars().first()

    def get_latest_alerts(
        self,
        location: Optional[str] = None,
        limit: int = 50,
    ) -> List[WeatherAlert]:
        """Fetch recently triggered alerts."""
        stmt = select(WeatherAlert)
        if location:
            stmt = stmt.where(WeatherAlert.location == location)
        stmt = stmt.order_by(desc(WeatherAlert.triggered_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def update_ai_explanation(self, alert_id: int, explanation: str) -> None:
        """Update alert record with AI generated explanation."""
        alert = self.db.get(WeatherAlert, alert_id)
        if alert:
            alert.ai_explanation = explanation
            self.db.flush()


class NotificationRepository:
    """Data access repository for notifications."""

    def __init__(self, db: Session):
        self.db = db

    def record_attempt(self, notification: NotificationHistory) -> NotificationHistory:
        """Record notification attempt."""
        self.db.add(notification)
        self.db.flush()
        self.db.refresh(notification)
        return notification

    def get_notifications_for_alert(self, alert_id: int) -> List[NotificationHistory]:
        """Fetch all notification attempts for a given alert."""
        stmt = (
            select(NotificationHistory)
            .where(NotificationHistory.alert_id == alert_id)
            .order_by(desc(NotificationHistory.attempted_at))
        )
        return list(self.db.execute(stmt).scalars().all())

    def has_successful_notification(self, alert_id: int) -> bool:
        """Check if an alert was already successfully notified."""
        stmt = (
            select(NotificationHistory)
            .where(
                NotificationHistory.alert_id == alert_id,
                NotificationHistory.status == "SENT",
            )
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first() is not None


class UserPreferenceRepository:
    """Data access repository for user preferences."""

    def __init__(self, db: Session):
        self.db = db

    def get_preferences(self, location: Optional[str] = None) -> UserPreference:
        """Retrieve existing preferences or create default if none exists."""
        stmt = select(UserPreference)
        if location:
            stmt = stmt.where(UserPreference.location == location)
        pref = self.db.execute(stmt.limit(1)).scalars().first()

        if not pref:
            pref = UserPreference(
                email=settings.ALERT_RECIPIENT or "",
                location=location or settings.LOCATION_NAME,
                latitude=settings.LATITUDE,
                longitude=settings.LONGITUDE,
                timezone=settings.TIMEZONE,
                rain_probability_threshold=settings.RAIN_PROBABILITY_THRESHOLD,
                minimum_rainfall_mm=settings.MIN_RAINFALL_MM,
                high_rainfall_mm=settings.HIGH_RAINFALL_MM,
                low_temperature_threshold=settings.LOW_TEMPERATURE_C,
                high_wind_threshold=settings.HIGH_WIND_KMH,
                alert_enabled=True,
            )
            self.db.add(pref)
            self.db.flush()
            self.db.refresh(pref)
        return pref

    def update_preferences(self, updated: UserPreference) -> UserPreference:
        """Persist preference changes."""
        self.db.add(updated)
        self.db.flush()
        self.db.refresh(updated)
        return updated


class WorkflowExecutionRepository:
    """Observability repository for tracking workflow executions."""

    def __init__(self, db: Session):
        self.db = db

    def record_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Save a workflow execution run."""
        self.db.add(execution)
        self.db.flush()
        self.db.refresh(execution)
        return execution

    def get_latest_execution(self) -> Optional[WorkflowExecution]:
        """Fetch the most recent workflow execution."""
        stmt = select(WorkflowExecution).order_by(desc(WorkflowExecution.started_at)).limit(1)
        return self.db.execute(stmt).scalars().first()

    def get_executions(self, limit: int = 20) -> List[WorkflowExecution]:
        """Fetch recent workflow execution records."""
        stmt = select(WorkflowExecution).order_by(desc(WorkflowExecution.started_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
