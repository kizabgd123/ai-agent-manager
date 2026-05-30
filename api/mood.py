import json
import uuid
from http.server import BaseHTTPRequestHandler

from textblob import TextBlob

SARCASM_MARKERS = ["oh great", "wonderful", "amazing", "fantastic"]
NEGATIVES = ["won't", "wont", "can't", "cant", "fail", "broken", "rainy", "bad", "down", "no", "not"]


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        text = payload.get("text", "")
        trace_id = str(uuid.uuid4())

        blob = TextBlob(text)
        polarity = blob.sentiment.polarity

        # Heuristic Sarcasm Detection
        text_lower = text.lower()
        is_sarcastic = any(m in text_lower for m in SARCASM_MARKERS) and any(
            n in text_lower for n in NEGATIVES
        )

        if is_sarcastic and polarity > 0:
            mood = "negative"
            polarity = -0.5  # Force negative
        elif polarity > 0.2:
            mood = "positive"
        elif polarity < -0.2:
            mood = "negative"
        else:
            mood = "neutral"

        response = {
            "mood": mood,
            "polarity": polarity,
            "input_length": len(text),
            "trace_id": trace_id,
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Trace-Id", trace_id)
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
