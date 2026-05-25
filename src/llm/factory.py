from __future__ import annotations

from .base import LLMClient
from .gemini_client import GeminiClient, gemini_config_from_env


def create_llm_client() -> LLMClient:
    config = gemini_config_from_env()
    if config.provider.lower() == "gemini":
        return GeminiClient(config)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
