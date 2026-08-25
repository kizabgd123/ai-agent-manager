from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any


@dataclass
class LLMConfig:
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    api_key: str | None = None
    temperature: float = 0.0


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...

    def generate_with_tools(self, prompt: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate a response with tool calling capability.
        
        Args:
            prompt: The user's input prompt
            tools: List of tool definitions with name, description, and parameters
            
        Returns:
            A dict containing:
                - content: The text response (if any)
                - tool_calls: List of tool calls to execute
                - raw_response: The full API response for debugging
        """
        ...
