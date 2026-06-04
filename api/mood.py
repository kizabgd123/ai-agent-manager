from http.server import BaseHTTPRequestHandler
import json
from textblob import TextBlob

from core.gemini_client import GeminiClient


def _mood_from_polarity(polarity: float) -> str:
    if polarity > 0.2:
        return "positive"
    if polarity < -0.2:
        return "negative"
    return "neutral"


def _mood_from_gemini(text: str):
    client = GeminiClient()
    if not client.is_configured():
        return None

    prompt = (
        "Classify sentiment as one label: positive, neutral, or negative. "
        "Return JSON only with keys mood and confidence. "
        f"Text: {text}"
    )
    try:
        raw = client.generate(prompt)
        response_text = client.extract_text(raw).strip()
        if response_text.startswith("```"):
            lines = response_text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            response_text = "\n".join(lines).strip()
        parsed = json.loads(response_text)
        if isinstance(parsed, dict):
            mood = parsed.get("mood")
            if mood in {"positive", "neutral", "negative"}:
                return {"provider": "gemini", "mood": mood, "confidence": parsed.get("confidence")}
    except Exception:
        return None
    return None


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        text = payload.get("text", "")

        gemini_result = _mood_from_gemini(text)
        polarity = TextBlob(text).sentiment.polarity

        if gemini_result:
            mood = gemini_result["mood"]
            provider = gemini_result["provider"]
        else:
            mood = _mood_from_polarity(polarity)
            provider = "textblob"

        response = {
            "mood": mood,
            "polarity": polarity,
            "input_length": len(text),
            "provider": provider,
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
