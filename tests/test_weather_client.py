"""Tests for weather client and mock weather provider."""

import pytest
import httpx
from unittest.mock import MagicMock, patch
from app.weather.client import OpenMeteoClient, MockWeatherProvider, WeatherAPIError


def test_mock_weather_provider_normal():
    """Verify mock provider generates standard normal weather forecast."""
    provider = MockWeatherProvider(scenario="normal")
    forecast = provider.fetch_forecast()
    assert forecast.location == "Chennai"
    assert len(forecast.hourly) == 48
    # Precipitation should be low in normal scenario
    assert all((item.precipitation_probability or 0.0) < 50 for item in forecast.hourly)


def test_mock_weather_provider_rain():
    """Verify mock provider generates rain event."""
    provider = MockWeatherProvider(scenario="rain")
    forecast = provider.fetch_forecast()
    rain_items = [i for i in forecast.hourly if (i.precipitation_probability or 0.0) >= 70]
    assert len(rain_items) > 0
    assert any((i.rain_mm or 0.0) >= 1.0 for i in rain_items)


def test_mock_weather_provider_heavy_rain():
    """Verify mock provider generates heavy rain event."""
    provider = MockWeatherProvider(scenario="heavy_rain")
    forecast = provider.fetch_forecast()
    heavy_items = [i for i in forecast.hourly if (i.rain_mm or 0.0) >= 10.0]
    assert len(heavy_items) > 0


def test_mock_weather_provider_high_wind():
    """Verify mock provider generates high wind scenario."""
    provider = MockWeatherProvider(scenario="high_wind")
    forecast = provider.fetch_forecast()
    wind_items = [i for i in forecast.hourly if (i.wind_speed_kmh or 0.0) >= 40.0]
    assert len(wind_items) > 0


def test_mock_weather_provider_low_temperature():
    """Verify mock provider generates cold scenario."""
    provider = MockWeatherProvider(scenario="low_temperature")
    forecast = provider.fetch_forecast()
    cold_items = [i for i in forecast.hourly if (i.temperature_c or 99.0) <= 15.0]
    assert len(cold_items) > 0


def test_mock_weather_provider_failure():
    """Verify mock provider simulates catastrophic API errors."""
    provider = MockWeatherProvider()
    provider.set_failure(WeatherAPIError("Simulated Open-Meteo outage"))
    with pytest.raises(WeatherAPIError, match="Simulated Open-Meteo outage"):
        provider.fetch_forecast()


def test_open_meteo_client_parser_success():
    """Verify OpenMeteoClient correctly parses standard response format."""
    client = OpenMeteoClient()
    sample_raw = {
        "latitude": 13.08,
        "longitude": 80.27,
        "timezone": "Asia/Kolkata",
        "hourly": {
            "time": ["2026-10-13T00:00", "2026-10-13T01:00"],
            "temperature_2m": [28.5, 27.8],
            "relative_humidity_2m": [75.0, 78.0],
            "precipitation_probability": [20, 85],
            "precipitation": [0.0, 4.2],
            "rain": [0.0, 4.2],
            "weather_code": [1, 61],
            "wind_speed_10m": [12.0, 15.5],
        },
    }
    parsed = client._parse_response(
        sample_raw,
        location_name="Chennai",
        latitude=13.08,
        longitude=80.27,
        timezone_name="Asia/Kolkata",
    )
    assert parsed.location == "Chennai"
    assert len(parsed.hourly) == 2
    assert parsed.hourly[1].precipitation_probability == 85.0
    assert parsed.hourly[1].rain_mm == 4.2


def test_open_meteo_client_parser_missing_fields():
    """Verify OpenMeteoClient raises WeatherAPIError on malformed structures."""
    client = OpenMeteoClient()
    with pytest.raises(WeatherAPIError, match="Missing 'hourly' data field"):
        client._parse_response({}, "Chennai", 13.0, 80.0, "Asia/Kolkata")

    with pytest.raises(WeatherAPIError, match="Empty or missing 'time' array"):
        client._parse_response({"hourly": {"time": []}}, "Chennai", 13.0, 80.0, "Asia/Kolkata")


def test_open_meteo_client_http_retry(monkeypatch):
    """Verify OpenMeteoClient retries on transient errors and eventually fails."""
    client = OpenMeteoClient(max_retries=2, timeout=1.0)

    mock_get = MagicMock(side_effect=httpx.NetworkError("Network unreachable"))
    with patch("httpx.Client.get", mock_get):
        with pytest.raises(WeatherAPIError, match="Exceeded max retries"):
            client.fetch_forecast(13.0827, 80.2707)
    assert mock_get.call_count == 2
