from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from llm.base import LLMClient


@dataclass
class BugSignal:
    source: str
    summary: str
    details: str


class BugDetector:
    ERROR_PATTERN = re.compile(r"(traceback|exception|error|failed)", re.IGNORECASE)

    def detect(self, logs: str, test_output: str) -> list[BugSignal]:
        signals: list[BugSignal] = []
        for source, content in (("logs", logs), ("tests", test_output)):
            if not content.strip():
                continue
            if self.ERROR_PATTERN.search(content):
                signals.append(
                    BugSignal(
                        source=source,
                        summary=self._first_error_line(content),
                        details=content[-4000:],
                    )
                )
        return signals

    def _first_error_line(self, text: str) -> str:
        for line in text.splitlines():
            if self.ERROR_PATTERN.search(line):
                return line.strip()[:200]
        return "error detected"


class ErrorParser:
    STACK_LINE = re.compile(r'File "([^"]+)", line (\d+)')

    def parse_files(self, signal: BugSignal) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        for m in self.STACK_LINE.finditer(signal.details):
            out.append((m.group(1), int(m.group(2))))
        return out


class PatchProposer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def propose_patch(self, signals: Iterable[BugSignal], context: str) -> str:
        prompt = (
            "You are fixing a Python codebase. Return ONLY a unified diff patch. "
            "Apply minimal root-cause fix and preserve backward compatibility.\n\n"
            f"Signals:\n{self._render_signals(signals)}\n\n"
            f"Context:\n{context}\n"
        )
        return self.llm.generate(prompt)

    def _render_signals(self, signals: Iterable[BugSignal]) -> str:
        return "\n".join(f"- [{s.source}] {s.summary}" for s in signals)


class PatchApplier:
    def apply(self, patch_text: str, repo_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            input=patch_text,
            text=True,
            cwd=repo_root,
            capture_output=True,
        )


class TestRunner:
    def run(self, repo_root: Path) -> tuple[int, str]:
        proc = subprocess.run(
            ["python", "-m", "pytest", "-q"],
            cwd=repo_root,
            text=True,
            capture_output=True,
        )
        return proc.returncode, (proc.stdout + "\n" + proc.stderr)


class AutoBugFixWorkflow:
    def __init__(
        self,
        detector: BugDetector,
        parser: ErrorParser,
        proposer: PatchProposer,
        applier: PatchApplier,
        tests: TestRunner,
        max_attempts: int = 3,
    ):
        self.detector = detector
        self.parser = parser
        self.proposer = proposer
        self.applier = applier
        self.tests = tests
        self.max_attempts = max_attempts

    def run(self, repo_root: Path, logs: str = "") -> dict:
        attempts = []
        for n in range(1, self.max_attempts + 1):
            code, test_output = self.tests.run(repo_root)
            if code == 0:
                return {"status": "resolved", "attempts": attempts, "attempt_count": n - 1}

            signals = self.detector.detect(logs, test_output)
            if not signals:
                return {"status": "no-actionable-signal", "attempts": attempts, "attempt_count": n}

            parsed_locations = []
            for sig in signals:
                parsed_locations.extend(self.parser.parse_files(sig))
            context = "\n".join(f"{f}:{ln}" for f, ln in parsed_locations[:20])
            patch = self.proposer.propose_patch(signals, context)
            result = self.applier.apply(patch, repo_root)

            attempts.append(
                {
                    "attempt": n,
                    "signals": [s.summary for s in signals],
                    "patch_applied": result.returncode == 0,
                    "apply_stdout": result.stdout,
                    "apply_stderr": result.stderr,
                }
            )
            if result.returncode != 0:
                return {"status": "patch-failed", "attempts": attempts, "attempt_count": n}

        return {"status": "limit-reached", "attempts": attempts, "attempt_count": self.max_attempts}
