# AI Agent Manager

## Overview
This project now includes:
- lightweight API handlers in `api/`
- Gemini 2.5 Flash LLM integration via a modular adapter
- an automatic bug-fix workflow that can detect test/log failures, propose patches, apply them, and retry safely

## Gemini 2.5 Flash integration
Model setup is environment-driven:
- `LLM_PROVIDER` (default: `gemini`)
- `LLM_MODEL` (default: `gemini-2.5-flash`)
- `GEMINI_API_KEY` (required for live calls)
- `LLM_TEMPERATURE` (default: `0.0`)

The client is in `src/llm/gemini_client.py` and can be swapped through `src/llm/factory.py`.

## Auto bug-fix workflow
Workflow components are in `src/autobugfix/workflow.py`:
- `BugDetector`: detects actionable failures from logs/tests
- `ErrorParser`: extracts stack trace file locations
- `PatchProposer`: asks Gemini for a minimal unified diff
- `PatchApplier`: applies diff via `git apply`
- `TestRunner`: reruns tests (`python -m pytest -q`)
- `AutoBugFixWorkflow`: retry loop with `max_attempts` guard to avoid infinite loops

### Run it
```bash
PYTHONPATH=src python -m autobugfix.cli --repo-root . --max-attempts 3
```

Optional:
```bash
PYTHONPATH=src python -m autobugfix.cli --repo-root . --logs-file runtime.log
```

## Tests
```bash
PYTHONPATH=src python -m pytest -q
```
