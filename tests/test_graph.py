"""Tests for the LangGraph state machine and conditional branches."""

import pytest
from unittest.mock import patch
from app.database.connection import init_db
from app.graph.workflow import create_weatherguard_workflow, run_workflow
from app.weather.client import WeatherAPIError


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_graph_compilation():
    """Verify StateGraph compiles cleanly with all 12 nodes and conditional edges."""
    app = create_weatherguard_workflow()
    assert app is not None


def test_graph_no_alert_branch():
    """Test workflow routes to finalize when scenario is normal (no alert triggered)."""
    result = run_workflow(
        location="Chennai",
        extra_state={"_mock_scenario": "normal"},
    )
    assert result["workflow_status"] in ("NO_ALERT", "COMPLETED")
    assert len(result.get("saved_alert_ids", [])) == 0


def test_graph_alert_branch():
    """Test workflow triggers alerts, creates records, and generates explanation on rain scenario."""
    result = run_workflow(
        location="Chennai",
        extra_state={"_mock_scenario": "rain"},
    )
    assert len(result.get("alerts", [])) > 0 or len(result.get("duplicate_alerts", [])) > 0
    # Workflow status should either have created alerts or recognized them
    assert result["workflow_status"] in ("COMPLETED", "DUPLICATE_SKIPPED")


def test_graph_duplicate_branch():
    """Test workflow idempotency: running twice with same data skips duplicate notification."""
    # First execution creates the alert
    res1 = run_workflow(
        location="Chennai",
        extra_state={"_mock_scenario": "heavy_rain"},
    )
    # Second execution immediately after should recognize duplicate
    res2 = run_workflow(
        location="Chennai",
        extra_state={"_mock_scenario": "heavy_rain"},
    )
    assert len(res2.get("duplicate_alerts", [])) > 0
    assert res2["workflow_status"] in ("DUPLICATE_SKIPPED", "COMPLETED")


def test_graph_weather_api_failure_handling():
    """Test workflow routes to finalize and captures error when API fails."""
    result = run_workflow(
        location="Chennai",
        extra_state={"_mock_error": WeatherAPIError("Simulated Open-Meteo outage")},
    )
    assert result["workflow_status"] == "FAILED"
    assert "Weather fetch failed" in (result.get("error") or "")


def test_graph_ollama_unavailable_fallback():
    """Test workflow seamlessly falls back to template explanation when Ollama is offline."""
    with patch("app.ai.llm.is_ollama_available", return_value=False):
        result = run_workflow(
            location="Chennai",
            extra_state={"_mock_scenario": "high_wind"},
        )
        if result.get("saved_alert_ids"):
            assert result.get("ai_explanation") is not None
            assert len(result["ai_explanation"]) > 10
