import json
import os
import sys
from io import BytesIO

# Add project root to path
sys.path.insert(0, os.getcwd())

def verify_mood_api(text):
    from api import mood
    data = json.dumps({"text": text}).encode("utf-8")
    
    headers_sent = {}
    class MockHandler(mood.handler):
        def __init__(self):
            self.rfile = BytesIO(data)
            self._sent_data = BytesIO()
            self.wfile = self._sent_data
            self.headers = {"content-length": str(len(data))}
            self.do_POST()
        def send_response(self, code, message=None): self.status_code = code
        def send_header(self, k, v): headers_sent[k] = v
        def end_headers(self): pass
    
    h = MockHandler()
    body = json.loads(h._sent_data.getvalue())
    return body, headers_sent

def verify_music_trigger_api(mood_val):
    from api import music_trigger
    data = json.dumps({"mood": mood_val}).encode("utf-8")
    
    headers_sent = {}
    class MockHandler(music_trigger.handler):
        def __init__(self):
            self.rfile = BytesIO(data)
            self._sent_data = BytesIO()
            self.wfile = self._sent_data
            self.headers = {"content-length": str(len(data))}
            self.do_POST()
        def send_response(self, code, message=None): self.status_code = code
        def send_header(self, k, v): headers_sent[k] = v
        def end_headers(self): pass
    
    h = MockHandler()
    body = json.loads(h._sent_data.getvalue())
    return body, headers_sent

def run_verification():
    print("=== Systematic Verification Report ===")
    
    # 1. End-to-End Flow: Sarcastic Input
    print("\n1. Verification: End-to-End Flow (Sarcastic)")
    sarcastic_text = "Wonderful, my internet is down."
    mood_res, mood_headers = verify_mood_api(sarcastic_text)
    print(f"Input: '{sarcastic_text}'")
    print(f"Mood API Result: {mood_res}")
    
    if mood_res['mood'] == 'negative':
        print("PASS: Sarcastic input resulted in 'negative' mood.")
    else:
        print(f"FAIL: Expected 'negative' mood for sarcastic input, got '{mood_res['mood']}'")

    music_res, music_headers = verify_music_trigger_api(mood_res['mood'])
    print(f"Music Trigger Input: mood='{mood_res['mood']}'")
    print(f"Music Trigger Result: {music_res}")
    
    if "grounding-ambient" in music_res['recommendations']:
        print("PASS: 'negative' mood resulted in 'grounding-ambient' recommendation.")
    else:
        print("FAIL: 'negative' mood did not result in 'grounding-ambient' recommendation.")

    # 2. Regression Check: Positive Input
    print("\n2. Verification: Regression Check (Positive)")
    positive_text = "This is a wonderful day!"
    mood_res_p, _ = verify_mood_api(positive_text)
    print(f"Input: '{positive_text}'")
    print(f"Mood API Result: {mood_res_p}")
    
    if mood_res_p['mood'] == 'positive':
        print("PASS: Positive input resulted in 'positive' mood.")
    else:
        print(f"FAIL: Expected 'positive' mood, got '{mood_res_p['mood']}'")

    # 3. Compliance Audit: music_trigger.py trace_id
    print("\n3. Verification: Compliance Audit (music_trigger.py)")
    _, music_headers_audit = verify_music_trigger_api("neutral")
    if "X-Trace-Id" in music_headers_audit:
        print("PASS: music_trigger.py implements X-Trace-Id header.")
    else:
        print("GAP: music_trigger.py DOES NOT implement X-Trace-Id header.")
        
    # 4. Header Consistency: mood.py X-Trace-Id
    print("\n4. Verification: Header Consistency (mood.py)")
    if "X-Trace-Id" in mood_headers:
        print(f"PASS: mood.py sends X-Trace-Id header. Value: {mood_headers['X-Trace-Id']}")
    else:
        print("FAIL: mood.py DOES NOT send X-Trace-Id header.")

if __name__ == "__main__":
    run_verification()