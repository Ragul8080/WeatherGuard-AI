"""Assembles and compiles the LangGraph StateGraph workflow."""

from typing import Any, Dict, Optional
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    analyse_forecast_node,
    check_alert_required_node,
    check_duplicate_alerts_node,
    create_alerts_node,
    fetch_weather_node,
    finalize_node,
    generate_ai_explanation_node,
    initialize_node,
    record_notification_node,
    save_forecast_node,
    send_email_node,
    validate_forecast_node,
)
from app.graph.routing import (
    route_after_check_alert_required,
    route_after_duplicate_check,
    route_after_fetch,
    route_after_save,
    route_after_validation,
)
from app.graph.state import WeatherGuardState
from app.logging_config import logger


def create_weatherguard_workflow():
    """Build and compile the LangGraph workflow for autonomous weather monitoring."""
    workflow = StateGraph(WeatherGuardState)

    # Register all 12 nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("fetch_weather", fetch_weather_node)
    workflow.add_node("validate_forecast", validate_forecast_node)
    workflow.add_node("save_forecast", save_forecast_node)
    workflow.add_node("analyse_forecast", analyse_forecast_node)
    workflow.add_node("check_alert_required", check_alert_required_node)
    workflow.add_node("check_duplicate_alerts", check_duplicate_alerts_node)
    workflow.add_node("create_alerts", create_alerts_node)
    workflow.add_node("generate_ai_explanation", generate_ai_explanation_node)
    workflow.add_node("send_email", send_email_node)
    workflow.add_node("record_notification", record_notification_node)
    workflow.add_node("finalize", finalize_node)

    # Define linear and conditional edges
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "fetch_weather")

    workflow.add_conditional_edges(
        "fetch_weather",
        route_after_fetch,
        {"validate_forecast": "validate_forecast", "finalize": "finalize"},
    )
    workflow.add_conditional_edges(
        "validate_forecast",
        route_after_validation,
        {"save_forecast": "save_forecast", "finalize": "finalize"},
    )
    workflow.add_conditional_edges(
        "save_forecast",
        route_after_save,
        {"analyse_forecast": "analyse_forecast", "finalize": "finalize"},
    )

    workflow.add_edge("analyse_forecast", "check_alert_required")

    workflow.add_conditional_edges(
        "check_alert_required",
        route_after_check_alert_required,
        {"check_duplicate_alerts": "check_duplicate_alerts", "finalize": "finalize"},
    )

    workflow.add_conditional_edges(
        "check_duplicate_alerts",
        route_after_duplicate_check,
        {"create_alerts": "create_alerts", "finalize": "finalize"},
    )

    workflow.add_edge("create_alerts", "generate_ai_explanation")
    workflow.add_edge("generate_ai_explanation", "send_email")
    workflow.add_edge("send_email", "record_notification")
    workflow.add_edge("record_notification", "finalize")
    workflow.add_edge("finalize", END)

    app = workflow.compile()
    logger.info("LangGraph StateGraph compiled successfully.")
    return app


# Cached compiled instance
weatherguard_app = create_weatherguard_workflow()


def run_workflow(
    location: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    extra_state: Optional[Dict[str, Any]] = None,
) -> WeatherGuardState:
    """Run one single autonomous execution of the WeatherGuard workflow."""
    initial_state: Dict[str, Any] = {}
    if location:
        initial_state["location"] = location
    if latitude is not None:
        initial_state["latitude"] = latitude
    if longitude is not None:
        initial_state["longitude"] = longitude
    if extra_state:
        initial_state.update(extra_state)

    result = weatherguard_app.invoke(initial_state)
    return result
