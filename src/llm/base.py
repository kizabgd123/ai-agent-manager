from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMConfig:
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    api_key: str | None = None
    temperature: float = 0.0


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...
