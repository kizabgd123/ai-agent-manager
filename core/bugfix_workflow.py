import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from core.gemini_client import GeminiClient


@dataclass
class BugSignal:
    source: str
    content: str


class BugDetector:
    ERROR_PATTERNS = [r"Traceback", r"Exception", r"FAILED", r"ERROR"]

    def from_text(self, text: str, source: str = "log") -> Optional[BugSignal]:
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in self.ERROR_PATTERNS):
            return BugSignal(source=source, content=text)
        return None


class ErrorParser:
    FILE_LINE_PATTERN = re.compile(r'File "([^"]+)", line (\d+)')

    def parse(self, signal: BugSignal) -> Dict[str, List[Dict[str, str]]]:
        matches = self.FILE_LINE_PATTERN.findall(signal.content)
        frames = [{"file": f, "line": line} for f, line in matches]
        return {"source": signal.source, "frames": frames, "raw": signal.content}


class PatchProposer:
    def __init__(self, llm: GeminiClient):
        self.llm = llm

    def propose_unified_diff(self, parsed_error: Dict[str, object], related_files: Dict[str, str]) -> str:
        file_block = "\n\n".join(
            f"# FILE: {name}\n{content}" for name, content in related_files.items()
        )
        prompt = (
            "You are fixing a Python bug with minimal changes. "
            "Return ONLY unified diff patch text.\n\n"
            f"Error context:\n{json.dumps(parsed_error, indent=2)}\n\n"
            f"Files:\n{file_block}\n"
        )
        response = self.llm.generate(prompt)
        return self.llm.extract_text(response).strip()


class PatchApplier:
    def apply(self, patch_text: str, repo_root: Path) -> subprocess.CompletedProcess:
        if not patch_text:
            raise ValueError("Patch text is empty")
        return subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            input=patch_text,
            text=True,
            cwd=repo_root,
            capture_output=True,
            check=False,
        )


class TestRunner:
    def run(self, command: List[str], repo_root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(command, cwd=repo_root, capture_output=True, text=True, check=False)


class AutoBugFixWorkflow:
    def __init__(self, llm: GeminiClient, max_attempts: int = 3):
        self.detector = BugDetector()
        self.parser = ErrorParser()
        self.proposer = PatchProposer(llm)
        self.applier = PatchApplier()
        self.runner = TestRunner()
        self.max_attempts = max_attempts

    def execute(self, test_command: List[str], repo_root: Path, tracked_files: List[Path]) -> Dict[str, object]:
        history = []
        for attempt in range(1, self.max_attempts + 1):
            test_result = self.runner.run(test_command, repo_root)
            combined = f"{test_result.stdout}\n{test_result.stderr}"
            signal = self.detector.from_text(combined, source="test")

            if test_result.returncode == 0 and not signal:
                return {"status": "resolved", "attempts": attempt, "history": history}

            if not signal:
                return {
                    "status": "stopped_no_signal",
                    "attempts": attempt,
                    "history": history,
                    "last_output": combined,
                }

            parsed = self.parser.parse(signal)
            related_files = {
                str(path): path.read_text(encoding="utf-8")
                for path in tracked_files
                if path.exists()
            }
            patch = self.proposer.propose_unified_diff(parsed, related_files)
            apply_result = self.applier.apply(patch, repo_root)

            step = {
                "attempt": attempt,
                "test_code": test_result.returncode,
                "patch_applied": apply_result.returncode == 0,
                "apply_stdout": apply_result.stdout,
                "apply_stderr": apply_result.stderr,
            }
            history.append(step)

            if apply_result.returncode != 0:
                return {"status": "stopped_patch_failed", "attempts": attempt, "history": history}

        return {"status": "limit_reached", "attempts": self.max_attempts, "history": history}
