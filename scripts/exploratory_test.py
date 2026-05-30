import json
import os
import sys
from io import BytesIO
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.getcwd())

def mock_call(handler_module, body):
    data = json.dumps(body).encode("utf-8")
    class MockHandler(handler_module.handler):
        def __init__(self):
            self.rfile = BytesIO(data)
            self._sent_data = BytesIO()
            self.wfile = self._sent_data
            self.headers = {"content-length": str(len(data))}
            self.do_POST()
        def send_response(self, code, message=None): pass
        def send_header(self, k, v): pass
        def end_headers(self): pass
    
    h = MockHandler()
    return json.loads(h._sent_data.getvalue())

def run_exploratory_tests():
    print("--- Exploratory Testing: ai-agent-manager ---")
    from api import mood, music_trigger
    
    # Test 1: Sarcasm / Ambiguous mood
    print("Testing Sarcasm...")
    res = mock_call(mood, {"text": "Oh great, another wonderful rainy day where my car won't start."})
    print(f"Result: {res}")
    
    # Test 2: Multi-stage flow
    print("\nTesting Multi-stage flow...")
    mood_res = mock_call(mood, {"text": "I am feeling very focused and productive!"})
    print(f"Mood detected: {mood_res['mood']}")
    
    music_res = mock_call(music_trigger, {"mood": mood_res['mood']})
    print(f"Music Recommendations: {music_res['recommendations']}")
    
    # Test 3: Empty input
    print("\nTesting Empty input...")
    try:
        empty_res = mock_call(mood, {"text": ""})
        print(f"Empty Result: {empty_res}")
    except Exception as e:
        print(f"Empty input error: {e}")

if __name__ == "__main__":
    run_exploratory_tests()