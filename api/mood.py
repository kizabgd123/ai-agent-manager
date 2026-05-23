from http.server import BaseHTTPRequestHandler
import json
from textblob import TextBlob


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        text = payload.get("text", "")

        polarity = TextBlob(text).sentiment.polarity
        if polarity > 0.2:
            mood = "positive"
        elif polarity < -0.2:
            mood = "negative"
        else:
            mood = "neutral"

        response = {
            "mood": mood,
            "polarity": polarity,
            "input_length": len(text),
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
