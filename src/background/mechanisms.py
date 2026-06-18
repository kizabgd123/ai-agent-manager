from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class CronSchedule:
    """Simple cron/one-shot schedule for exact timing needs."""

    expression: str
    timezone_name: str = "UTC"
    one_shot_at: datetime | None = None

    @classmethod
    def one_shot(cls, when: datetime, timezone_name: str = "UTC") -> "CronSchedule":
        return cls(expression="@once", timezone_name=timezone_name, one_shot_at=when)

    def should_run(self, now: datetime) -> bool:
        if self.one_shot_at is not None:
            return _minute_floor(now) == _minute_floor(self.one_shot_at)
        minute, hour, day, month, weekday = self.expression.split()
        return all(
            (
                _matches(minute, now.minute),
                _matches(hour, now.hour),
                _matches(day, now.day),
                _matches(month, now.month),
                _matches(weekday, now.weekday()),
            )
        )


@dataclass(frozen=True)
class Heartbeat:
    """Flexible periodic check that runs when enough time elapsed."""

    name: str
    interval: timedelta
    context_keys: tuple[str, ...] = ()

    def due(self, last_run_at: datetime | None, now: datetime) -> bool:
        return last_run_at is None or now - last_run_at >= self.interval

    def scoped_context(self, context: dict[str, Any]) -> dict[str, Any]:
        if not self.context_keys:
            return dict(context)
        return {key: context[key] for key in self.context_keys if key in context}


@dataclass(frozen=True)
class InferredCommitment:
    """Memory-like follow-up inferred from user language."""

    id: str
    user_id: str
    summary: str
    evidence: str
    due_hint: str | None = None

    @classmethod
    def infer(cls, user_id: str, text: str) -> list["InferredCommitment"]:
        triggers = ("remind", "follow up", "check back", "tomorrow", "next week")
        if not any(trigger in text.lower() for trigger in triggers):
            return []
        return [
            cls(
                id=str(uuid.uuid4()),
                user_id=user_id,
                summary=_summarize(text),
                evidence=text,
                due_hint=_extract_due_hint(text),
            )
        ]


@dataclass
class BackgroundTask:
    """Detached work entry persisted in the tasks ledger."""

    id: str
    mechanism: str
    description: str
    status: str = "registered"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class BackgroundTaskRegistry:
    """Register, list, and audit background runs with a JSONL ledger."""

    def __init__(self, ledger_path: Path):
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def register(self, mechanism: str, description: str, **metadata: Any) -> BackgroundTask:
        task = BackgroundTask(str(uuid.uuid4()), mechanism, description, metadata=metadata)
        self._append(task)
        return task

    def list(self) -> list[BackgroundTask]:
        if not self.ledger_path.exists():
            return []
        return [BackgroundTask(**json.loads(line)) for line in self.ledger_path.read_text().splitlines() if line]

    def audit(self) -> dict[str, Any]:
        tasks = self.list()
        by_status: dict[str, int] = {}
        by_mechanism: dict[str, int] = {}
        for task in tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1
            by_mechanism[task.mechanism] = by_mechanism.get(task.mechanism, 0) + 1
        return {"total": len(tasks), "by_status": by_status, "by_mechanism": by_mechanism}

    def _append(self, task: BackgroundTask) -> None:
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(task), sort_keys=True) + "\n")


@dataclass(frozen=True)
class TaskFlowRevision:
    revision: int
    steps: tuple[str, ...]
    changed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TaskFlow:
    """Multi-step durable orchestration with immutable revisions."""

    name: str
    revisions: list[TaskFlowRevision]

    @classmethod
    def create(cls, name: str, steps: Iterable[str]) -> "TaskFlow":
        return cls(name=name, revisions=[TaskFlowRevision(1, tuple(steps))])

    def revise(self, steps: Iterable[str]) -> TaskFlowRevision:
        revision = TaskFlowRevision(self.revisions[-1].revision + 1, tuple(steps))
        self.revisions.append(revision)
        return revision

    @property
    def current(self) -> TaskFlowRevision:
        return self.revisions[-1]


class HookRegistry:
    """Lifecycle hook registry for scripts/actions such as session reset."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def on(self, event: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._hooks.setdefault(event, []).append(handler)

    def emit(self, event: str, payload: dict[str, Any]) -> int:
        for handler in self._hooks.get(event, []):
            handler(payload)
        return len(self._hooks.get(event, []))


class PluginHookBus:
    """In-process interception point for tool calls."""

    def __init__(self) -> None:
        self._interceptors: list[Callable[[str, dict[str, Any]], dict[str, Any]]] = []

    def intercept(self, interceptor: Callable[[str, dict[str, Any]], dict[str, Any]]) -> None:
        self._interceptors.append(interceptor)

    def before_tool_call(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        for interceptor in self._interceptors:
            payload = interceptor(tool, payload)
        return payload


@dataclass
class StandingOrders:
    """Persistent instructions injected into every session."""

    orders: list[str] = field(default_factory=list)

    def add(self, instruction: str) -> None:
        if instruction not in self.orders:
            self.orders.append(instruction)

    def inject(self, session_context: dict[str, Any]) -> dict[str, Any]:
        return {**session_context, "standing_orders": tuple(self.orders)}


class UseCaseMapper:
    REFERENCE = {
        "daily report": "Scheduled Tasks (Cron)",
        "one-shot reminder": "Scheduled Tasks (Cron)",
        "inbox monitoring": "Heartbeat",
        "calendar awareness": "Heartbeat",
        "user follow-up": "Inferred Commitments",
        "detached work audit": "Background Tasks",
        "multi-step orchestration": "Task Flows",
        "session reset": "Hooks",
        "tool interception": "Plugin hooks",
        "persistent compliance": "Standing Orders",
    }

    @classmethod
    def recommend(cls, use_case: str) -> str:
        lowered = use_case.lower()
        for key, mechanism in cls.REFERENCE.items():
            if key in lowered:
                return mechanism
        return "Task Flows"


def _matches(field: str, value: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        return value % int(field[2:]) == 0
    return int(field) == value


def _minute_floor(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def _extract_due_hint(text: str) -> str | None:
    match = re.search(r"\b(tomorrow|next week|next month|on \w+)\b", text, re.IGNORECASE)
    return match.group(0) if match else None


def _summarize(text: str) -> str:
    return text.strip().split(".")[0][:120]
