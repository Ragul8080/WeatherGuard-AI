"""Duplicate alert prevention and idempotency management."""

from typing import List, Tuple
from sqlalchemy.orm import Session
from app.database.models import WeatherAlert
from app.database.repositories import NotificationRepository, WeatherAlertRepository
from app.logging_config import logger
from app.weather.schemas import AlertCandidate


class DeduplicationService:
    """Filters out already-notified alerts using stable keys."""

    def __init__(self, db: Session):
        self.db = db
        self.alert_repo = WeatherAlertRepository(db)
        self.notification_repo = NotificationRepository(db)

    def filter_duplicates(
        self,
        candidates: List[AlertCandidate],
    ) -> Tuple[List[AlertCandidate], List[AlertCandidate]]:
        """Separate candidate alerts into new alerts vs duplicates."""
        new_alerts: List[AlertCandidate] = []
        duplicate_alerts: List[AlertCandidate] = []

        for candidate in candidates:
            existing = self.alert_repo.get_alert_by_key(candidate.alert_key)
            if existing:
                # Check if it was already notified successfully or exists in DB
                logger.info(
                    f"Duplicate alert detected for key '{candidate.alert_key}' (Alert ID {existing.id})."
                )
                duplicate_alerts.append(candidate)
            else:
                logger.info(f"New alert qualified: key '{candidate.alert_key}'.")
                new_alerts.append(candidate)

        return new_alerts, duplicate_alerts
