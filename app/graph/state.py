"""LangGraph state representation for WeatherGuard AI workflow."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class WeatherGuardState(TypedDict, total=False):
    """Workflow state container exchanged between LangGraph nodes."""

    # Workflow Metadata
    workflow_id: str
    started_at: str
    completed_at: Optional[str]
    workflow_status: str  # INITIALIZED, FETCHED, SAVED, NO_ALERT, DUPLICATE_SKIPPED, COMPLETED, FAILED
    error: Optional[str]

    # Target Location
    location: str
    latitude: float
    longitude: float
    timezone: str

    # Forecast & Analysis Data
    forecast: Optional[Dict[str, Any]]
    analysis: Optional[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    duplicate_alerts: List[Dict[str, Any]]
    saved_alert_ids: List[int]

    # AI & Notifications
    ai_explanation: Optional[str]
    email_status: str  # PENDING, SENT, SKIPPED, MOCK_SENT, FAILED
    notifications_recorded: int

    # Test & Simulation Hooks
    _mock_scenario: Optional[str]
    _mock_error: Optional[Any]

