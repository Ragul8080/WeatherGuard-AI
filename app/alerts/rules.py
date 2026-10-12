"""Deterministic rules engine for weather alert evaluation."""

from datetime import datetime, timezone
from typing import List, Optional
from app.config import settings
from app.logging_config import logger
from app.utils.time import now_utc
from app.weather.schemas import (
    AlertCandidate,
    HourlyForecastItem,
    WeatherAnalysisResult,
    WeatherForecastResponse,
)


class AlertRulesEngine:
    """Evaluates numerical weather forecasts against configurable safety thresholds."""

    def __init__(
        self,
        rain_probability_threshold: Optional[float] = None,
        min_rainfall_mm: Optional[float] = None,
        high_rainfall_mm: Optional[float] = None,
        low_temperature_threshold: Optional[float] = None,
        high_wind_threshold: Optional[float] = None,
        horizon_hours: Optional[int] = None,
    ):
        self.rain_prob_threshold = (
            rain_probability_threshold
            if rain_probability_threshold is not None
            else settings.RAIN_PROBABILITY_THRESHOLD
        )
        self.min_rainfall_mm = (
            min_rainfall_mm
            if min_rainfall_mm is not None
            else settings.MIN_RAINFALL_MM
        )
        self.high_rainfall_mm = (
            high_rainfall_mm
            if high_rainfall_mm is not None
            else settings.HIGH_RAINFALL_MM
        )
        self.low_temp_threshold = (
            low_temperature_threshold
            if low_temperature_threshold is not None
            else settings.LOW_TEMPERATURE_C
        )
        self.high_wind_threshold = (
            high_wind_threshold
            if high_wind_threshold is not None
            else settings.HIGH_WIND_KMH
        )
        self.horizon_hours = (
            horizon_hours if horizon_hours is not None else settings.ALERT_HORIZON_HOURS
        )

    def evaluate_forecast(
        self,
        forecast: WeatherForecastResponse,
        current_time: Optional[datetime] = None,
    ) -> WeatherAnalysisResult:
        """Inspect the next horizon_hours and return structured analysis with any triggered alerts."""
        now = current_time or now_utc()
        location = forecast.location

        # Filter items strictly to the next horizon_hours
        horizon_items: List[HourlyForecastItem] = []
        for item in forecast.hourly:
            # item.forecast_time is timezone aware
            if item.forecast_time >= now:
                horizon_items.append(item)
            if len(horizon_items) >= self.horizon_hours:
                break

        # If all forecast times are in the future or no horizon items, take the first N items
        if not horizon_items and forecast.hourly:
            horizon_items = forecast.hourly[: self.horizon_hours]

        if not horizon_items:
            logger.warning(f"No horizon items found to analyze for {location}.")
            return WeatherAnalysisResult(
                alert_required=False,
                horizon_hours=self.horizon_hours,
                evaluated_at=now,
                location=location,
                alerts=[],
            )

        # Aggregate calculations across the entire horizon window
        max_prob = 0.0
        total_precip = 0.0
        max_rain = 0.0
        min_temp = 999.0
        max_wind = 0.0
        weather_codes: List[int] = []

        peak_rain_item: Optional[HourlyForecastItem] = None
        peak_heavy_rain_item: Optional[HourlyForecastItem] = None
        min_temp_item: Optional[HourlyForecastItem] = None
        max_wind_item: Optional[HourlyForecastItem] = None

        for item in horizon_items:
            prob = item.precipitation_probability or 0.0
            precip = item.precipitation_mm or 0.0
            rain = item.rain_mm or precip
            temp = item.temperature_c if item.temperature_c is not None else 999.0
            wind = item.wind_speed_kmh or 0.0

            if prob > max_prob:
                max_prob = prob
            total_precip += precip
            if rain > max_rain:
                max_rain = rain
                peak_rain_item = item
            if temp < min_temp:
                min_temp = temp
                min_temp_item = item
            if wind > max_wind:
                max_wind = wind
                max_wind_item = item
            if item.weather_code is not None and item.weather_code not in weather_codes:
                weather_codes.append(item.weather_code)

            if rain >= self.high_rainfall_mm and (
                peak_heavy_rain_item is None
                or rain > (peak_heavy_rain_item.rain_mm or 0.0)
            ):
                peak_heavy_rain_item = item

        candidates: List[AlertCandidate] = []

        # 1. High Rainfall Warning check (evaluated first or alongside)
        if max_rain >= self.high_rainfall_mm and peak_heavy_rain_item:
            fc_str = peak_heavy_rain_item.forecast_time.strftime("%Y-%m-%dT%H:00")
            key = f"{location}:HIGH_RAINFALL:{fc_str}"
            msg = (
                f"High rainfall warning for {location}: Expected {max_rain:.1f} mm "
                f"(threshold: {self.high_rainfall_mm:.1f} mm) around {fc_str}."
            )
            candidates.append(
                AlertCandidate(
                    type="HIGH_RAINFALL",
                    severity="HIGH",
                    forecast_time=peak_heavy_rain_item.forecast_time,
                    probability=peak_heavy_rain_item.precipitation_probability or max_prob,
                    rainfall_mm=max_rain,
                    wind_speed_kmh=peak_heavy_rain_item.wind_speed_kmh,
                    temperature_c=peak_heavy_rain_item.temperature_c,
                    message=msg,
                    alert_key=key,
                )
            )

        # 2. Rain Warning check
        # Condition: prob >= rain_prob_threshold AND expected rain >= min_rainfall_mm
        if (
            max_prob >= self.rain_prob_threshold
            and max_rain >= self.min_rainfall_mm
            and peak_rain_item
        ):
            fc_str = peak_rain_item.forecast_time.strftime("%Y-%m-%dT%H:00")
            key = f"{location}:RAIN_WARNING:{fc_str}"
            msg = (
                f"Rain expected for {location}: {max_prob:.0f}% probability with "
                f"{max_rain:.1f} mm precipitation at {fc_str}."
            )
            candidates.append(
                AlertCandidate(
                    type="RAIN_WARNING",
                    severity="WARNING",
                    forecast_time=peak_rain_item.forecast_time,
                    probability=max_prob,
                    rainfall_mm=max_rain,
                    wind_speed_kmh=peak_rain_item.wind_speed_kmh,
                    temperature_c=peak_rain_item.temperature_c,
                    message=msg,
                    alert_key=key,
                )
            )

        # 3. Low Temperature Warning check
        if min_temp <= self.low_temp_threshold and min_temp_item:
            fc_str = min_temp_item.forecast_time.strftime("%Y-%m-%dT%H:00")
            key = f"{location}:LOW_TEMPERATURE:{fc_str}"
            severity = "HIGH" if min_temp <= 5.0 else "WARNING"
            msg = (
                f"Low temperature advisory for {location}: Temperature dropping to "
                f"{min_temp:.1f}°C (threshold: {self.low_temp_threshold:.1f}°C) at {fc_str}."
            )
            candidates.append(
                AlertCandidate(
                    type="LOW_TEMPERATURE",
                    severity=severity,
                    forecast_time=min_temp_item.forecast_time,
                    temperature_c=min_temp,
                    wind_speed_kmh=min_temp_item.wind_speed_kmh,
                    message=msg,
                    alert_key=key,
                )
            )

        # 4. High Wind Warning check
        if max_wind >= self.high_wind_threshold and max_wind_item:
            fc_str = max_wind_item.forecast_time.strftime("%Y-%m-%dT%H:00")
            key = f"{location}:HIGH_WIND:{fc_str}"
            severity = "HIGH" if max_wind >= 60.0 else "WARNING"
            msg = (
                f"High wind warning for {location}: Wind gusts reaching "
                f"{max_wind:.1f} km/h (threshold: {self.high_wind_threshold:.1f} km/h) at {fc_str}."
            )
            candidates.append(
                AlertCandidate(
                    type="HIGH_WIND",
                    severity=severity,
                    forecast_time=max_wind_item.forecast_time,
                    wind_speed_kmh=max_wind,
                    temperature_c=max_wind_item.temperature_c,
                    message=msg,
                    alert_key=key,
                )
            )

        alert_required = len(candidates) > 0
        logger.info(
            f"Alert analysis for {location}: {len(candidates)} alerts triggered. "
            f"Max Prob: {max_prob}%, Max Rain: {max_rain}mm, Min Temp: {min_temp}°C, Max Wind: {max_wind}km/h."
        )

        return WeatherAnalysisResult(
            alert_required=alert_required,
            horizon_hours=self.horizon_hours,
            evaluated_at=now,
            location=location,
            max_rain_probability=max_prob,
            total_expected_precipitation_mm=round(total_precip, 2),
            max_rainfall_mm=round(max_rain, 2),
            min_temperature_c=min_temp if min_temp != 999.0 else 0.0,
            max_wind_speed_kmh=round(max_wind, 2),
            weather_codes=weather_codes,
            alerts=candidates,
        )
