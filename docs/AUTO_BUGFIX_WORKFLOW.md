# Auto Bug-Fix Workflow

This project now includes a modular auto bug-fix flow in `core/bugfix_workflow.py`.

## Components

- `BugDetector`: detects failures from logs/test output.
- `ErrorParser`: extracts traceback file/line information.
- `PatchProposer`: asks Gemini (`gemini-2.5-flash` by default) for a minimal unified diff.
- `PatchApplier`: applies proposed patch with `git apply`.
- `TestRunner`: reruns validation command.
- `AutoBugFixWorkflow`: retry loop with `max_attempts` safety guard.

## Gemini configuration

Set environment variables:

- `GEMINI_API_KEY` (required for LLM-driven patch proposals)
- `GEMINI_MODEL` (optional, default: `gemini-2.5-flash`)
- `GEMINI_TIMEOUT_SECONDS` (optional, default: `30`)

## Usage sketch

```python
from pathlib import Path
from core.gemini_client import GeminiClient
from core.bugfix_workflow import AutoBugFixWorkflow

workflow = AutoBugFixWorkflow(GeminiClient(), max_attempts=3)
result = workflow.execute(
    test_command=["python", "-m", "unittest", "discover", "-s", "tests"],
    repo_root=Path("."),
    tracked_files=[Path("api/mood.py"), Path("api/music_trigger.py")],
)
print(result)
```

If Gemini is unavailable, the workflow will fail safely when trying to propose a patch, without entering an infinite loop.
