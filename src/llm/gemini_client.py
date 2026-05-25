from __future__ import annotations

import json
import os
import urllib.request

from .base import LLMClient, LLMConfig


class GeminiClient(LLMClient):
    def __init__(self, config: LLMConfig):
        self.config = config
        if not config.api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini client")

    def generate(self, prompt: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.config.model}:generateContent?key={self.config.api_key}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": self.config.temperature},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        candidates = payload.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(part.get("text", "") for part in parts).strip()


def gemini_config_from_env() -> LLMConfig:
    return LLMConfig(
        provider=os.getenv("LLM_PROVIDER", "gemini"),
        model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
    )
