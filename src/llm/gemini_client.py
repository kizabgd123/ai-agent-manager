from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

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

    def generate_with_tools(self, prompt: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate a response with tool calling using Gemini's function calling API.
        
        Args:
            prompt: The user's input prompt
            tools: List of tool definitions with name, description, and parameters
            
        Returns:
            A dict containing content, tool_calls, and raw_response
        """
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.config.model}:generateContent?key={self.config.api_key}"
        )
        
        # Convert tools to Gemini's function declaration format
        function_declarations = []
        for tool in tools:
            function_declarations.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters", {
                    "type": "OBJECT",
                    "properties": {}
                })
            })
        
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": self.config.temperature},
            "tools": [
                {
                    "functionDeclarations": function_declarations
                }
            ]
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return {
                "content": f"Error calling Gemini API: {e.code} {e.reason}",
                "tool_calls": [],
                "raw_response": {"error": error_body},
            }
        
        candidates = payload.get("candidates", [])
        if not candidates:
            return {"content": "", "tool_calls": [], "raw_response": payload}
        
        content_parts = []
        tool_calls = []
        
        candidate = candidates[0]
        content_data = candidate.get("content", {})
        parts = content_data.get("parts", [])
        
        for part in parts:
            if "text" in part:
                content_parts.append(part["text"])
            if "functionCall" in part:
                func_call = part["functionCall"]
                tool_calls.append({
                    "name": func_call.get("name", ""),
                    "arguments": func_call.get("args", {}),
                })
        
        return {
            "content": "\n".join(content_parts).strip(),
            "tool_calls": tool_calls,
            "raw_response": payload,
        }


def gemini_config_from_env() -> LLMConfig:
    return LLMConfig(
        provider=os.getenv("LLM_PROVIDER", "gemini"),
        model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
    )
