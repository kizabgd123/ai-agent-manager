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

## Background work mechanisms

Use this quick decision guide to pick the smallest mechanism that preserves timing, scope, and auditability:

| Use case | Recommended mechanism | Why |
| --- | --- | --- |
| Daily reports or exact one-shot reminders | Scheduled Tasks (Cron) | Runs at an exact wall-clock minute or a single scheduled instant. |
| Inbox monitoring or calendar awareness | Heartbeat | Flexible periodic checks that run when enough time has elapsed and can receive scoped context. |
| Follow-ups inferred from user context | Inferred Commitments | Stores memory-like obligations with evidence and due hints. |
| Detached work that must be auditable | Background Tasks | Registers work in a JSONL tasks ledger and supports `tasks list` plus `tasks audit`. |
| Multi-step durable orchestration | Task Flows | Tracks ordered steps with immutable revisions as plans change. |
| Lifecycle events such as session reset | Hooks | Invokes registered handlers for named lifecycle events. |
| In-process tool-call interception | Plugin hooks | Lets plugins transform payloads before tool execution. |
| Persistent compliance or behavior | Standing Orders | Injects durable instructions into every session context. |

The implementation lives in `src/background/mechanisms.py` and exposes:

- `CronSchedule` for exact cron or one-shot timing.
- `Heartbeat` for flexible periodic checks with context scoping.
- `InferredCommitment` for follow-ups inferred from user language.
- `BackgroundTaskRegistry` for registering background tasks and auditing the ledger.
- `TaskFlow` and `TaskFlowRevision` for durable orchestration and revision tracking.
- `HookRegistry` for lifecycle event handlers.
- `PluginHookBus` for in-process tool interception.
- `StandingOrders` for persistent instruction injection.
- `UseCaseMapper` for mapping common use cases to the reference mechanism.

### Inspect and audit tasks

```bash
PYTHONPATH=src python -m background.cli list --ledger .agent/tasks-ledger.jsonl
PYTHONPATH=src python -m background.cli audit --ledger .agent/tasks-ledger.jsonl
```
