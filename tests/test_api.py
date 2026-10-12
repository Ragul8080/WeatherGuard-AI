"""Tests for FastAPI backend routes and responses."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.database.connection import init_db
from app.main import app
from app.weather.client import MockWeatherProvider


@pytest.fixture(autouse=True)
def init_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def test_get_root(client):
    """Test / root endpoint returns service metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "WeatherGuard AI"
    assert data["status"] == "online"
    assert "interactive_docs" in data


def test_get_health(client):
    """Test /health endpoint returns valid system status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "weather_api" in data
    assert "version" in data


def test_get_settings(client):
    """Test /api/settings returns configuration object."""
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Chennai"
    assert "rain_probability_threshold" in data


def test_put_settings(client):
    """Test PUT /api/settings modifies user thresholds."""
    update_payload = {
        "location": "Chennai",
        "rain_probability_threshold": 65.0,
        "high_wind_threshold": 45.0,
        "alert_enabled": True,
    }
    response = client.put("/api/settings", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["rain_probability_threshold"] == 65.0
    assert data["high_wind_threshold"] == 45.0


def test_post_weather_check_manual_trigger(client):
    """Test POST /api/weather/check triggers workflow execution."""
    response = client.post("/api/weather/check", json={"location": "Chennai"})
    assert response.status_code == 200
    data = response.json()
    assert "workflow_id" in data
    assert data["workflow_status"] in ("COMPLETED", "NO_ALERT", "DUPLICATE_SKIPPED", "FETCHED")


def test_get_weather_history(client):
    """Test /api/weather/history returns list."""
    response = client.get("/api/weather/history?location=Chennai&limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_alerts(client):
    """Test /api/alerts returns alert list."""
    response = client.get("/api/alerts?location=Chennai&limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_post_test_email(client):
    """Test POST /api/alerts/test-email sends simulated or live email."""
    response = client.post("/api/alerts/test-email", json={"recipient": "test-dev@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] in ("MOCK_MODE", "SENT")


def test_post_chat(client):
    """Test POST /api/chat provides response even when Ollama is offline."""
    response = client.post("/api/chat", json={"message": "Will it rain today?"})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 5
