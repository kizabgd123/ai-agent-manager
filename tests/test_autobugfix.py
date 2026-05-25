from pathlib import Path

from autobugfix.workflow import AutoBugFixWorkflow, BugDetector, ErrorParser


class DummyProposer:
    def __init__(self, patch: str):
        self.patch = patch

    def propose_patch(self, signals, context):
        return self.patch


class DummyApplier:
    def __init__(self, returncode=0):
        self.returncode = returncode

    def apply(self, patch_text, repo_root):
        class R:
            pass

        r = R()
        r.returncode = self.returncode
        r.stdout = "ok"
        r.stderr = ""
        return r


class DummyTests:
    def __init__(self, codes):
        self.codes = list(codes)

    def run(self, repo_root):
        c = self.codes.pop(0)
        out = "1 failed\nTraceback\nFile \"api/mood.py\", line 10"
        return c, out


def test_error_parser_extracts_stack_locations():
    parser = ErrorParser()
    signal = type("S", (), {"details": 'Traceback\nFile "api/mood.py", line 10\n'})
    assert parser.parse_files(signal) == [("api/mood.py", 10)]


def test_workflow_resolves_when_tests_pass_after_patch(tmp_path: Path):
    workflow = AutoBugFixWorkflow(
        detector=BugDetector(),
        parser=ErrorParser(),
        proposer=DummyProposer("diff --git a/a b/a"),
        applier=DummyApplier(returncode=0),
        tests=DummyTests([1, 0]),
        max_attempts=3,
    )
    result = workflow.run(tmp_path)
    assert result["status"] == "resolved"
    assert result["attempt_count"] == 1


def test_workflow_stops_on_patch_apply_failure(tmp_path: Path):
    workflow = AutoBugFixWorkflow(
        detector=BugDetector(),
        parser=ErrorParser(),
        proposer=DummyProposer("bad patch"),
        applier=DummyApplier(returncode=1),
        tests=DummyTests([1]),
        max_attempts=2,
    )
    result = workflow.run(tmp_path)
    assert result["status"] == "patch-failed"
