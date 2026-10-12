"""Ollama connection discovery and ChatOllama factory."""

from typing import Optional
import httpx
from langchain_ollama import ChatOllama
from app.config import settings
from app.logging_config import logger


def is_ollama_available(base_url: Optional[str] = None) -> bool:
    """Check if the local Ollama daemon is reachable and responding."""
    url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{url}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


def get_ollama_client(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.1,
) -> Optional[ChatOllama]:
    """Return configured ChatOllama client if enabled and reachable, else None."""
    if not settings.OLLAMA_ENABLED:
        logger.debug("Ollama is disabled in configuration.")
        return None

    target_base = base_url or settings.OLLAMA_BASE_URL
    target_model = model or settings.OLLAMA_MODEL

    if not is_ollama_available(target_base):
        logger.debug(f"Ollama server is not reachable at {target_base}.")
        return None

    try:
        llm = ChatOllama(
            model=target_model,
            base_url=target_base,
            temperature=temperature,
        )
        return llm
    except Exception as e:
        logger.warning(f"Failed to instantiate ChatOllama: {e}")
        return None
