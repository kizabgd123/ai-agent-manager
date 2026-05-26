import os
import unittest

from core.gemini_client import GeminiConfig, GeminiClient


class TestGeminiConfig(unittest.TestCase):
    def test_defaults_to_gemini_flash(self):
        os.environ.pop("GEMINI_MODEL", None)
        cfg = GeminiConfig.from_env()
        self.assertEqual(cfg.model, "gemini-2.5-flash")


class TestGeminiClient(unittest.TestCase):
    def test_extract_text(self):
        payload = {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
        self.assertEqual(GeminiClient.extract_text(payload), "hello")


if __name__ == "__main__":
    unittest.main()
