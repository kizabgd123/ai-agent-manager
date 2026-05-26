import unittest

from core.bugfix_workflow import BugDetector, ErrorParser


class TestBugDetector(unittest.TestCase):
    def test_detects_failed_test_signal(self):
        signal = BugDetector().from_text("FAILED test_example.py::test_x - Exception")
        self.assertIsNotNone(signal)


class TestErrorParser(unittest.TestCase):
    def test_parses_traceback_frames(self):
        text = 'Traceback\n  File "api/mood.py", line 12, in do_POST\nValueError'
        parsed = ErrorParser().parse(type("Signal", (), {"source": "test", "content": text})())
        self.assertEqual(parsed["frames"][0]["file"], "api/mood.py")
        self.assertEqual(parsed["frames"][0]["line"], "12")


if __name__ == "__main__":
    unittest.main()
