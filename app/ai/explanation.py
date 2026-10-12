"""AI explanation service with graceful deterministic template fallback."""

from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from app.ai.llm import get_ollama_client
from app.ai.prompts import EXPLANATION_SYSTEM_PROMPT, EXPLANATION_USER_PROMPT
from app.database.models import WeatherAlert
from app.logging_config import logger
from app.utils.time import format_display_time


class AIExplanationService:
    """Generates natural language explanations of alerts using Ollama or fallback templates."""

    def __init__(self, ollama_client=None):
        self._llm = ollama_client

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_ollama_client()
        return self._llm

    def generate_explanation(
        self,
        alert: WeatherAlert,
        user_timezone: str = "Asia/Kolkata",
    ) -> str:
        """Generate human-readable explanation via LLM if reachable, otherwise template fallback."""
        formatted_time = format_display_time(alert.forecast_time, user_timezone)
        prob = f"{alert.probability:.0f}" if alert.probability is not None else "0"
        rain = f"{alert.rainfall_mm:.1f}" if alert.rainfall_mm is not None else "0.0"

        llm = self._get_llm()
        if llm:
            try:
                logger.info(f"Generating AI explanation via Ollama for alert {alert.id} ({alert.alert_type}).")
                user_content = EXPLANATION_USER_PROMPT.format(
                    location=alert.location,
                    alert_type=alert.alert_type,
                    severity=alert.severity,
                    forecast_time=formatted_time,
                    probability=prob,
                    rainfall_mm=rain,
                    wind_speed_kmh="N/A",
                    temperature_c="N/A",
                    message=alert.message,
                )
                messages = [
                    SystemMessage(content=EXPLANATION_SYSTEM_PROMPT),
                    HumanMessage(content=user_content),
                ]
                response = llm.invoke(messages)
                content = response.content if hasattr(response, "content") else str(response)
                if content and content.strip():
                    logger.info("AI explanation generated successfully via Ollama.")
                    return content.strip()
            except Exception as e:
                logger.warning(
                    f"Ollama generation failed ({e}). Falling back to deterministic template."
                )

        # High quality deterministic template fallback
        return self._fallback_template(alert, formatted_time, prob, rain)

    def _fallback_template(
        self,
        alert: WeatherAlert,
        formatted_time: str,
        prob: str,
        rain: str,
    ) -> str:
        """Deterministic fallback explanation when Ollama is unavailable."""
        alert_type = alert.alert_type.upper()

        if alert_type == "RAIN_WARNING":
            return (
                f"Rain is likely in {alert.location} around {formatted_time}. "
                f"The forecast shows a {prob}% precipitation probability with approximately "
                f"{rain} mm of expected rainfall. Consider carrying an umbrella or planning indoor activities."
            )
        elif alert_type == "HIGH_RAINFALL":
            return (
                f"Heavy rainfall is projected for {alert.location} around {formatted_time}, "
                f"with approximately {rain} mm of accumulation expected. "
                f"Road surfaces may become waterlogged and travel delays are possible. Please exercise caution if commuting."
            )
        elif alert_type == "LOW_TEMPERATURE":
            return (
                f"A drop in temperature is expected for {alert.location} around {formatted_time}. "
                f"Please ensure adequate warm clothing and protect sensitive plants or pets."
            )
        elif alert_type == "HIGH_WIND":
            return (
                f"Strong wind gusts are anticipated for {alert.location} around {formatted_time}. "
                f"Secure loose outdoor objects and drive carefully on exposed roads."
            )
        else:
            return (
                f"Weather alert ({alert.alert_type}) active for {alert.location} around {formatted_time}: "
                f"{alert.message}. Please monitor current conditions before travelling."
            )
