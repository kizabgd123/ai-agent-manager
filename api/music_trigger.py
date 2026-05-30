import json
import uuid
from http.server import BaseHTTPRequestHandler


PLAYLIST_MAP = {
    "positive": ["focus-pop", "upbeat-acoustic"],
    "neutral": ["lofi-balance", "calm-instrumental"],
    "negative": ["grounding-ambient", "soft-piano"],
}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        mood = payload.get("mood", "neutral")
        trace_id = str(uuid.uuid4())

        response = {
            "mood": mood,
            "recommendations": PLAYLIST_MAP.get(mood, PLAYLIST_MAP["neutral"]),
            "action": "return_playlist_seed",
            "trace_id": trace_id,
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Trace-Id", trace_id)
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
