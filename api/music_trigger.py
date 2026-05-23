from http.server import BaseHTTPRequestHandler
import json


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

        response = {
            "mood": mood,
            "recommendations": PLAYLIST_MAP.get(mood, PLAYLIST_MAP["neutral"]),
            "action": "return_playlist_seed",
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
