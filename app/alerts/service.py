"""Alert service coordinating rules evaluation, deduplication, and persistence."""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.alerts.deduplication import DeduplicationService
from app.alerts.rules import AlertRulesEngine
from app.database.models import UserPreference, WeatherAlert
from app.database.repositories import UserPreferenceRepository, WeatherAlertRepository
from app.logging_config import logger
from app.weather.schemas import (
    AlertCandidate,
    WeatherAnalysisResult,
    WeatherForecastResponse,
)


class AlertService:
    """Service orchestrating alert business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.alert_repo = WeatherAlertRepository(db)
        self.pref_repo = UserPreferenceRepository(db)
        self.dedup_service = DeduplicationService(db)

    def analyze_and_evaluate(
        self,
        forecast: WeatherForecastResponse,
        user_pref: Optional[UserPreference] = None,
    ) -> WeatherAnalysisResult:
        """Run deterministic rules against forecast data."""
        pref = user_pref or self.pref_repo.get_preferences(forecast.location)
        if not pref.alert_enabled:
            logger.info(f"Alerts are disabled for location {forecast.location}. Skipping evaluation.")
            return WeatherAnalysisResult(
                alert_required=False,
                horizon_hours=6,
                evaluated_at=forecast.fetched_at,
                location=forecast.location,
                alerts=[],
            )

        engine = AlertRulesEngine(
            rain_probability_threshold=pref.rain_probability_threshold,
            min_rainfall_mm=pref.minimum_rainfall_mm,
            high_rainfall_mm=pref.high_rainfall_mm,
            low_temperature_threshold=pref.low_temperature_threshold,
            high_wind_threshold=pref.high_wind_threshold,
        )
        return engine.evaluate_forecast(forecast)

    def process_candidates(
        self,
        candidates: List[AlertCandidate],
    ) -> Tuple[List[AlertCandidate], List[AlertCandidate]]:
        """Separate candidate alerts into new and duplicates."""
        return self.dedup_service.filter_duplicates(candidates)

    def persist_alerts(
        self,
        candidates: List[AlertCandidate],
        location: str,
        latitude: float,
        longitude: float,
    ) -> List[WeatherAlert]:
        """Convert candidates to database WeatherAlert models and persist."""
        saved_alerts: List[WeatherAlert] = []
        for cand in candidates:
            alert = WeatherAlert(
                location=location,
                latitude=latitude,
                longitude=longitude,
                alert_type=cand.type,
                severity=cand.severity,
                forecast_time=cand.forecast_time,
                probability=cand.probability,
                rainfall_mm=cand.rainfall_mm,
                message=cand.message,
                alert_key=cand.alert_key,
                status="ACTIVE",
            )
            saved = self.alert_repo.create_alert(alert)
            saved_alerts.append(saved)
        return saved_alerts

    def get_latest_alerts(
        self,
        location: Optional[str] = None,
        limit: int = 50,
    ) -> List[WeatherAlert]:
        """Retrieve recent alerts."""
        return self.alert_repo.get_latest_alerts(location=location, limit=limit)
