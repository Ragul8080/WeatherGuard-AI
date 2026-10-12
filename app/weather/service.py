"""Service layer for weather fetching, conversion, and caching."""

from datetime import datetime, timezone
from typing import List, Optional, Union
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import WeatherReading
from app.database.repositories import WeatherReadingRepository
from app.logging_config import logger
from app.weather.client import MockWeatherProvider, OpenMeteoClient
from app.weather.schemas import HourlyForecastItem, WeatherForecastResponse


class WeatherService:
    """Orchestrates weather retrieval and persistence."""

    def __init__(
        self,
        db: Session,
        client: Optional[Union[OpenMeteoClient, MockWeatherProvider]] = None,
    ):
        self.db = db
        self.repo = WeatherReadingRepository(db)
        self.client = client or OpenMeteoClient()

    def fetch_and_save_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Chennai",
        timezone_name: str = "Asia/Kolkata",
        forecast_days: int = 2,
    ) -> WeatherForecastResponse:
        """Fetch weather data from client and store readings in database."""
        logger.info(f"WeatherService: Fetching forecast for {location_name}")
        forecast = self.client.fetch_forecast(
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
            timezone_name=timezone_name,
            forecast_days=forecast_days,
        )

        readings = self.to_reading_models(forecast)
        self.repo.save_readings(readings)
        return forecast

    def to_reading_models(
        self,
        forecast: WeatherForecastResponse,
    ) -> List[WeatherReading]:
        """Transform response schema into SQLAlchemy models."""
        readings: List[WeatherReading] = []
        for item in forecast.hourly:
            reading = WeatherReading(
                location=forecast.location,
                latitude=forecast.latitude,
                longitude=forecast.longitude,
                forecast_time=item.forecast_time,
                fetched_at=forecast.fetched_at,
                temperature_c=item.temperature_c,
                humidity=item.humidity,
                precipitation_probability=item.precipitation_probability,
                precipitation_mm=item.precipitation_mm,
                rain_mm=item.rain_mm,
                weather_code=item.weather_code,
                wind_speed_kmh=item.wind_speed_kmh,
            )
            readings.append(reading)
        return readings

    def get_latest_reading(self, location: str) -> Optional[WeatherReading]:
        """Get latest weather reading for a location."""
        return self.repo.get_latest_reading(location)

    def get_history(
        self,
        location: str,
        limit: int = 48,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[WeatherReading]:
        """Fetch history readings."""
        return self.repo.get_recent_readings(
            location=location,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )

    def get_forecast_horizon(
        self,
        location: str,
        start_time: datetime,
        hours: int = 6,
    ) -> List[WeatherReading]:
        """Fetch forecast readings for alert evaluation window."""
        return self.repo.get_forecast_horizon(location, start_time, hours)
