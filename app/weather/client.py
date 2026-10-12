"""Weather API client for Open-Meteo with retries and mock provider."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import httpx
from pydantic import ValidationError

from app.config import settings
from app.logging_config import logger
from app.utils.time import now_utc, parse_datetime
from app.weather.schemas import HourlyForecastItem, WeatherForecastResponse


class WeatherAPIError(Exception):
    """Base exception for weather API communication failures."""
    pass


class OpenMeteoClient:
    """Client for retrieving forecast data from the Open-Meteo API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        self.base_url = base_url or settings.OPEN_METEO_BASE_URL
        self.timeout = timeout or settings.WEATHER_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.WEATHER_MAX_RETRIES

    def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Chennai",
        timezone_name: str = "Asia/Kolkata",
        forecast_days: int = 2,
    ) -> WeatherForecastResponse:
        """Retrieve and parse hourly weather forecast from Open-Meteo."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,rain,weather_code,wind_speed_10m",
            "timezone": timezone_name,
            "forecast_days": forecast_days,
        }

        logger.info(
            f"Fetching weather for {location_name} ({latitude}, {longitude}) "
            f"from {self.base_url}"
        )

        raw_data = self._request_with_retry(params)
        return self._parse_response(raw_data, location_name, latitude, longitude, timezone_name)

    def _request_with_retry(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform HTTP GET with exponential backoff on transient errors."""
        attempt = 0
        backoff = 1.0

        while attempt < self.max_retries:
            attempt += 1
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(self.base_url, params=params)

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception as err:
                        raise WeatherAPIError(f"Malformed JSON from Open-Meteo: {err}")

                # Rate limiting or server errors eligible for retry
                if resp.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        f"Open-Meteo HTTP {resp.status_code} (attempt {attempt}/{self.max_retries}). "
                        f"Retrying in {backoff:.1f}s..."
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue

                # Permanent client error
                raise WeatherAPIError(
                    f"Open-Meteo client error HTTP {resp.status_code}: {resp.text}"
                )

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(
                    f"Network error contacting Open-Meteo ({type(e).__name__}: {e}) "
                    f"attempt {attempt}/{self.max_retries}."
                )
                if attempt >= self.max_retries:
                    raise WeatherAPIError(f"Exceeded max retries contacting Open-Meteo: {e}")
                time.sleep(backoff)
                backoff *= 2.0

        raise WeatherAPIError(f"Failed to fetch weather after {self.max_retries} attempts.")

    def _parse_response(
        self,
        data: Dict[str, Any],
        location_name: str,
        latitude: float,
        longitude: float,
        timezone_name: str,
    ) -> WeatherForecastResponse:
        """Validate and parse raw response dictionary into domain schemas."""
        if not isinstance(data, dict):
            raise WeatherAPIError("Open-Meteo response is not a valid JSON object")

        if "hourly" not in data or not isinstance(data["hourly"], dict):
            raise WeatherAPIError("Missing 'hourly' data field in Open-Meteo response")

        hourly_raw = data["hourly"]
        times = hourly_raw.get("time")
        if not times or not isinstance(times, list):
            raise WeatherAPIError("Empty or missing 'time' array in forecast")

        count = len(times)
        temps = hourly_raw.get("temperature_2m", [None] * count)
        humidities = hourly_raw.get("relative_humidity_2m", [None] * count)
        precip_probs = hourly_raw.get("precipitation_probability", [None] * count)
        precips = hourly_raw.get("precipitation", [None] * count)
        rains = hourly_raw.get("rain", [None] * count)
        weather_codes = hourly_raw.get("weather_code", [None] * count)
        wind_speeds = hourly_raw.get("wind_speed_10m", [None] * count)

        items: List[HourlyForecastItem] = []
        for i in range(count):
            try:
                forecast_dt = parse_datetime(times[i], default_tz_name=timezone_name)
                item = HourlyForecastItem(
                    forecast_time=forecast_dt,
                    temperature_c=float(temps[i]) if temps[i] is not None else None,
                    humidity=float(humidities[i]) if humidities[i] is not None else None,
                    precipitation_probability=(
                        float(precip_probs[i]) if precip_probs[i] is not None else None
                    ),
                    precipitation_mm=float(precips[i]) if precips[i] is not None else None,
                    rain_mm=float(rains[i]) if rains[i] is not None else None,
                    weather_code=int(weather_codes[i]) if weather_codes[i] is not None else None,
                    wind_speed_kmh=(
                        float(wind_speeds[i]) if wind_speeds[i] is not None else None
                    ),
                )
                items.append(item)
            except Exception as e:
                logger.warning(f"Skipping malformed forecast hour index {i}: {e}")
                continue

        if not items:
            raise WeatherAPIError("No valid forecast items could be parsed")

        return WeatherForecastResponse(
            location=location_name,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone_name,
            fetched_at=now_utc(),
            hourly=items,
        )


class MockWeatherProvider:
    """Deterministic mock weather provider for unit tests and simulation."""

    def __init__(self, scenario: str = "normal"):
        self.scenario = scenario
        self.failure_error: Optional[Exception] = None

    def set_scenario(self, scenario: str) -> None:
        self.scenario = scenario
        self.failure_error = None

    def set_failure(self, error: Exception) -> None:
        self.failure_error = error

    def fetch_forecast(
        self,
        latitude: float = 13.0827,
        longitude: float = 80.2707,
        location_name: str = "Chennai",
        timezone_name: str = "Asia/Kolkata",
        forecast_days: int = 2,
    ) -> WeatherForecastResponse:
        """Return synthetic weather forecast according to configured scenario."""
        if self.failure_error:
            raise self.failure_error

        base_time = now_utc().replace(minute=0, second=0, microsecond=0)
        items: List[HourlyForecastItem] = []

        total_hours = forecast_days * 24
        for hour in range(total_hours):
            fc_time = base_time + timedelta(hours=hour)

            # Default values (normal weather)
            temp = 28.0 + (hour % 5)
            humidity = 60.0
            prob = 15.0
            precip = 0.0
            rain = 0.0
            code = 1  # Clear / partly cloudy
            wind = 12.0

            # Override per scenario in the early horizon hours (e.g. hour 2-4)
            if self.scenario == "rain":
                if 1 <= hour <= 4:
                    prob = 85.0
                    precip = 3.5
                    rain = 3.5
                    code = 61  # Slight rain
            elif self.scenario == "heavy_rain":
                if 1 <= hour <= 4:
                    prob = 95.0
                    precip = 18.0
                    rain = 18.0
                    code = 65  # Heavy rain
            elif self.scenario == "high_wind":
                if 1 <= hour <= 4:
                    wind = 55.0
                    code = 3
            elif self.scenario == "low_temperature":
                if 1 <= hour <= 4:
                    temp = 10.0
            elif self.scenario == "combined_storm":
                if 1 <= hour <= 4:
                    prob = 90.0
                    precip = 22.0
                    rain = 22.0
                    wind = 52.0
                    temp = 13.0
                    code = 95

            items.append(
                HourlyForecastItem(
                    forecast_time=fc_time,
                    temperature_c=temp,
                    humidity=humidity,
                    precipitation_probability=prob,
                    precipitation_mm=precip,
                    rain_mm=rain,
                    weather_code=code,
                    wind_speed_kmh=wind,
                )
            )

        return WeatherForecastResponse(
            location=location_name,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone_name,
            fetched_at=now_utc(),
            hourly=items,
        )
