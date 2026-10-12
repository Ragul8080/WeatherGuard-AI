"""AI explanation and Ollama integration layer."""

from app.ai.explanation import AIExplanationService
from app.ai.llm import get_ollama_client, is_ollama_available

__all__ = ["AIExplanationService", "get_ollama_client", "is_ollama_available"]
