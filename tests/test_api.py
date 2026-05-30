"""Tests for the AI Agent Manager API endpoints and tool schemas."""

import json
import os
import sys
from io import BytesIO
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _mock_handler(handler_class, body: dict):
    """Create a BaseHTTPRequestHandler that processes a POST body
    and captures the response in _sent_data."""
    data = json.dumps(body).encode("utf-8")

    class PatchedHandler(handler_class):
        def __init__(self, *a, **kw):
            self.raw_requestline = b"POST / HTTP/1.1\r\n"
            self.rfile = BytesIO(data)
            self._sent_data = BytesIO()
            self.wfile = self._sent_data
            # Manually invoke the request cycle
            self.handle()

        def handle(self):
            self.command = "POST"
            self.path = "/"
            self.request_version = "HTTP/1.1"
            self.headers = MagicMock()
            self.headers.get.return_value = str(len(data))
            self.do_POST()

        def send_response(self, code, message=None):
            self._status_code = code

        def send_header(self, keyword, value):
            if not hasattr(self, "_sent_headers"):
                self._sent_headers = {}
            self._sent_headers[keyword] = value

        def end_headers(self):
            pass

    h = PatchedHandler.__new__(PatchedHandler)
    PatchedHandler.__init__(h, MagicMock(), ("127.0.0.1", 0), None)
    return h


class TestMoodAPI:
    def test_positive_mood(self):
        from api.mood import handler

        h = _mock_handler(handler, {"text": "I feel amazing today!"})
        sent = json.loads(h._sent_data.getvalue())
        assert sent["mood"] == "positive"
        assert sent["polarity"] > 0.2
        assert "trace_id" in sent
        assert h._sent_headers["X-Trace-Id"] == sent["trace_id"]

    def test_sarcastic_mood(self):
        from api.mood import handler

        # "oh great" is a marker, "broken" is a negative marker.
        # TextBlob would normally see "great" as positive.
        h = _mock_handler(handler, {"text": "Oh great, my car is broken again."})
        sent = json.loads(h._sent_data.getvalue())
        assert sent["mood"] == "negative"
        assert sent["polarity"] == -0.5
        assert "trace_id" in sent
        assert h._sent_headers["X-Trace-Id"] == sent["trace_id"]

    def test_negative_mood(self):
        from api.mood import handler

        h = _mock_handler(handler, {"text": "This is terrible and sad."})
        sent = json.loads(h._sent_data.getvalue())
        assert sent["mood"] == "negative"
        assert sent["polarity"] < -0.2

    def test_neutral_mood(self):
        from api.mood import handler

        h = _mock_handler(handler, {"text": "The door is blue."})
        sent = json.loads(h._sent_data.getvalue())
        assert sent["mood"] == "neutral"


class TestMusicTriggerAPI:
    def test_positive_recommendations(self):
        from api.music_trigger import handler

        h = _mock_handler(handler, {"mood": "positive"})
        sent = json.loads(h._sent_data.getvalue())
        assert sent["mood"] == "positive"
        assert "focus-pop" in sent["recommendations"]

    def test_negative_recommendations(self):
        from api.music_trigger import handler

        h = _mock_handler(handler, {"mood": "negative"})
        sent = json.loads(h._sent_data.getvalue())
        assert "grounding-ambient" in sent["recommendations"]

    def test_default_mood(self):
        from api.music_trigger import handler

        h = _mock_handler(handler, {})
        sent = json.loads(h._sent_data.getvalue())
        assert sent["mood"] == "neutral"


class TestAnythingLLMToolsSchema:
    def test_agent_tools_file_exists(self):
        tools_path = os.path.join(
            os.path.dirname(__file__), "..", "anythingllm", "agent_tools.json"
        )
        assert os.path.exists(tools_path)
        with open(tools_path) as f:
            data = json.load(f)
        assert "tools" in data
        assert len(data["tools"]) == 2
        tool_names = {t["name"] for t in data["tools"]}
        assert "mood_analyzer" in tool_names
        assert "music_recommender" in tool_names
        for t in data["tools"]:
            assert "<your-project>" in t["url"], f"{t['name']} URL needs updating"
