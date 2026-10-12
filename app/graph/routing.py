"""Conditional routing logic for the LangGraph workflow."""

from typing import Literal
from app.graph.state import WeatherGuardState
from app.logging_config import logger


def route_after_fetch(
    state: WeatherGuardState,
) -> Literal["validate_forecast", "finalize"]:
    """Route after weather fetch: abort to finalize if error occurred."""
    if state.get("error"):
        logger.warning("Routing to finalize due to weather fetch failure.")
        return "finalize"
    return "validate_forecast"


def route_after_validation(
    state: WeatherGuardState,
) -> Literal["save_forecast", "finalize"]:
    """Route after forecast validation: abort to finalize if invalid."""
    if state.get("error"):
        logger.warning("Routing to finalize due to invalid forecast.")
        return "finalize"
    return "save_forecast"


def route_after_save(
    state: WeatherGuardState,
) -> Literal["analyse_forecast", "finalize"]:
    """Route after saving forecast: abort to finalize if db save failed."""
    if state.get("error"):
        logger.warning("Routing to finalize due to database error.")
        return "finalize"
    return "analyse_forecast"


def route_after_check_alert_required(
    state: WeatherGuardState,
) -> Literal["check_duplicate_alerts", "finalize"]:
    """Decide whether to check duplicates or finalize when no alert is needed."""
    if state.get("error"):
        return "finalize"
    if state.get("workflow_status") == "NO_ALERT":
        logger.info("Routing directly to finalize: No alert threshold breached.")
        return "finalize"
    return "check_duplicate_alerts"


def route_after_duplicate_check(
    state: WeatherGuardState,
) -> Literal["create_alerts", "finalize"]:
    """Decide whether to proceed with alert dispatch or finalize if all are duplicates."""
    if state.get("error"):
        return "finalize"
    if state.get("workflow_status") == "DUPLICATE_SKIPPED":
        logger.info("Routing directly to finalize: All candidate alerts are duplicates.")
        return "finalize"
    return "create_alerts"
