import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import request


@dataclass
class GeminiConfig:
    api_key: str
    model: str = "gemini-2.5-flash"
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        api_key = os.getenv("GEMINI_API_KEY", "")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        try:
            timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
        except ValueError:
            timeout_seconds = 30
        return cls(api_key=api_key, model=model, timeout_seconds=timeout_seconds)


class GeminiClient:
    def __init__(self, config: Optional[GeminiConfig] = None):
        self.config = config or GeminiConfig.from_env()

    def is_configured(self) -> bool:
        return bool(self.config.api_key)

    def generate(self, prompt: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY is required")

        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.config.model}:generateContent?key={self.config.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)

    @staticmethod
    def extract_text(response_json: Dict[str, Any]) -> str:
        candidates = response_json.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(part.get("text", "") for part in parts if part.get("text"))
