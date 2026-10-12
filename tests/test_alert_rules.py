"""Tests for deterministic alert rules engine."""

import pytest
from datetime import datetime, timezone, timedelta
from app.alerts.rules import AlertRulesEngine
from app.weather.client import MockWeatherProvider
from app.weather.schemas import HourlyForecastItem, WeatherForecastResponse
from app.utils.time import now_utc


@pytest.fixture
def base_forecast():
    """Create a default benign forecast with 6 hours of clear conditions."""
    now = now_utc().replace(minute=0, second=0, microsecond=0)
    items = [
        HourlyForecastItem(
            forecast_time=now + timedelta(hours=i),
            temperature_c=28.0,
            humidity=60.0,
            precipitation_probability=20.0,
            precipitation_mm=0.0,
            rain_mm=0.0,
            weather_code=1,
            wind_speed_kmh=15.0,
        )
        for i in range(12)
    ]
    return WeatherForecastResponse(
        location="Chennai",
        latitude=13.0827,
        longitude=80.2707,
        timezone="Asia/Kolkata",
        fetched_at=now,
        hourly=items,
    )


def test_no_alert_on_low_probability(base_forecast):
    """Test 20% probability -> no alert triggered."""
    engine = AlertRulesEngine(
        rain_probability_threshold=70.0,
        min_rainfall_mm=1.0,
        high_rainfall_mm=10.0,
        low_temperature_threshold=15.0,
        high_wind_threshold=40.0,
    )
    result = engine.evaluate_forecast(base_forecast)
    assert not result.alert_required
    assert len(result.alerts) == 0


def test_rain_alert_at_70_percent(base_forecast):
    """Test 70% probability + sufficient rainfall -> RAIN_WARNING."""
    # Modify hour 2 to hit exact 70% and 1.5mm
    base_forecast.hourly[2].precipitation_probability = 70.0
    base_forecast.hourly[2].rain_mm = 1.5

    engine = AlertRulesEngine(rain_probability_threshold=70.0, min_rainfall_mm=1.0)
    result = engine.evaluate_forecast(base_forecast)

    assert result.alert_required
    types = [a.type for a in result.alerts]
    assert "RAIN_WARNING" in types
    alert = [a for a in result.alerts if a.type == "RAIN_WARNING"][0]
    assert alert.severity == "WARNING"
    assert alert.probability == 70.0


def test_rain_alert_at_85_percent(base_forecast):
    """Test 85% probability + sufficient rainfall -> RAIN_WARNING."""
    base_forecast.hourly[1].precipitation_probability = 85.0
    base_forecast.hourly[1].rain_mm = 4.2

    engine = AlertRulesEngine(rain_probability_threshold=70.0, min_rainfall_mm=1.0)
    result = engine.evaluate_forecast(base_forecast)

    assert result.alert_required
    alert = [a for a in result.alerts if a.type == "RAIN_WARNING"][0]
    assert alert.probability == 85.0
    assert alert.rainfall_mm == 4.2


def test_rain_alert_skipped_if_rainfall_insufficient(base_forecast):
    """Test high probability but near-zero rainfall (< min_rainfall) -> no RAIN_WARNING."""
    base_forecast.hourly[1].precipitation_probability = 90.0
    base_forecast.hourly[1].rain_mm = 0.2  # Below min threshold 1.0mm

    engine = AlertRulesEngine(rain_probability_threshold=70.0, min_rainfall_mm=1.0)
    result = engine.evaluate_forecast(base_forecast)

    # Should NOT trigger RAIN_WARNING
    rain_alerts = [a for a in result.alerts if a.type == "RAIN_WARNING"]
    assert len(rain_alerts) == 0


def test_high_rainfall_alert(base_forecast):
    """Test high rainfall threshold -> HIGH_RAINFALL alert with HIGH severity."""
    base_forecast.hourly[3].rain_mm = 15.0
    base_forecast.hourly[3].precipitation_probability = 95.0

    engine = AlertRulesEngine(high_rainfall_mm=10.0)
    result = engine.evaluate_forecast(base_forecast)

    assert result.alert_required
    high_rain_alerts = [a for a in result.alerts if a.type == "HIGH_RAINFALL"]
    assert len(high_rain_alerts) == 1
    assert high_rain_alerts[0].severity == "HIGH"
    assert high_rain_alerts[0].rainfall_mm == 15.0


def test_high_wind_alert(base_forecast):
    """Test wind speed >= 40 km/h -> HIGH_WIND alert."""
    base_forecast.hourly[2].wind_speed_kmh = 48.0

    engine = AlertRulesEngine(high_wind_threshold=40.0)
    result = engine.evaluate_forecast(base_forecast)

    assert result.alert_required
    wind_alerts = [a for a in result.alerts if a.type == "HIGH_WIND"]
    assert len(wind_alerts) == 1
    assert wind_alerts[0].wind_speed_kmh == 48.0


def test_low_temperature_alert(base_forecast):
    """Test temperature <= 15 C -> LOW_TEMPERATURE alert."""
    base_forecast.hourly[4].temperature_c = 11.5

    engine = AlertRulesEngine(low_temperature_threshold=15.0)
    result = engine.evaluate_forecast(base_forecast)

    assert result.alert_required
    temp_alerts = [a for a in result.alerts if a.type == "LOW_TEMPERATURE"]
    assert len(temp_alerts) == 1
    assert temp_alerts[0].temperature_c == 11.5


def test_multiple_alerts_simultaneous(base_forecast):
    """Test compound storm event triggering multiple alerts simultaneously."""
    base_forecast.hourly[2].precipitation_probability = 90.0
    base_forecast.hourly[2].rain_mm = 14.0
    base_forecast.hourly[2].wind_speed_kmh = 55.0
    base_forecast.hourly[2].temperature_c = 12.0

    engine = AlertRulesEngine(
        rain_probability_threshold=70.0,
        min_rainfall_mm=1.0,
        high_rainfall_mm=10.0,
        low_temperature_threshold=15.0,
        high_wind_threshold=40.0,
    )
    result = engine.evaluate_forecast(base_forecast)

    types = {a.type for a in result.alerts}
    assert "RAIN_WARNING" in types
    assert "HIGH_RAINFALL" in types
    assert "HIGH_WIND" in types
    assert "LOW_TEMPERATURE" in types
