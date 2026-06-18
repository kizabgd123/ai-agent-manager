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
        """
        Create a one-shot schedule for execution at a specified datetime.
        
        Parameters:
            when (datetime): The datetime when the schedule should run.
            timezone_name (str): The timezone name (default: "UTC").
        
        Returns:
            CronSchedule: A one-shot schedule configured to run at the specified time.
        """
        return cls(expression="@once", timezone_name=timezone_name, one_shot_at=when)

    def should_run(self, now: datetime) -> bool:
        """
        Determine whether the schedule should run at the given time.
        
        Returns:
            bool: True if the schedule should run at the given time, False otherwise.
        """
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
        """
        Determine if the heartbeat is due to run.
        
        Returns:
            `True` if the heartbeat is due to run, `False` otherwise.
        """
        return last_run_at is None or now - last_run_at >= self.interval

    def scoped_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Filters context to specified keys, or provides a copy of the full context if none are specified.
        
        Parameters:
        	context (dict[str, Any]): The context dictionary to filter or copy.
        
        Returns:
        	dict[str, Any]: A dictionary containing only the specified context keys that exist in `context`, or a shallow copy of the entire `context` if no keys were specified.
        """
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
        """
        Infers a commitment from text if trigger words are detected.
        
        Returns:
            A list with a single InferredCommitment if triggers are found, or an empty list.
        """
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
        """
        Initialize the background task registry with a ledger file path.
        
        Ensures that the parent directory of the ledger exists, creating it if necessary.
        
        Parameters:
        	ledger_path (Path): The file path where task records will be persisted.
        """
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def register(self, mechanism: str, description: str, **metadata: Any) -> BackgroundTask:
        """
        Register a new background task in the ledger.
        
        Returns:
            BackgroundTask: The created and registered task.
        """
        task = BackgroundTask(str(uuid.uuid4()), mechanism, description, metadata=metadata)
        self._append(task)
        return task

    def list(self) -> list[BackgroundTask]:
        """
        Retrieve all persisted background tasks from the ledger.
        
        Returns:
        	list[BackgroundTask]: A list of all background tasks in the ledger, or an empty list if the ledger does not exist.
        """
        if not self.ledger_path.exists():
            return []
        return [BackgroundTask(**json.loads(line)) for line in self.ledger_path.read_text().splitlines() if line]

    def audit(self) -> dict[str, Any]:
        """
        Generate a summary of registered background tasks grouped by status and mechanism.
        
        Returns:
        	dict[str, Any]: A dictionary containing "total" (number of tasks), "by_status" (task count per status), and "by_mechanism" (task count per mechanism).
        """
        tasks = self.list()
        by_status: dict[str, int] = {}
        by_mechanism: dict[str, int] = {}
        for task in tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1
            by_mechanism[task.mechanism] = by_mechanism.get(task.mechanism, 0) + 1
        return {"total": len(tasks), "by_status": by_status, "by_mechanism": by_mechanism}

    def _append(self, task: BackgroundTask) -> None:
        """
        Appends a task entry to the ledger as a JSON line.
        """
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
        """
        Create a new task flow with an initial revision containing the provided steps.
        
        Returns:
            TaskFlow: The newly created task flow.
        """
        return cls(name=name, revisions=[TaskFlowRevision(1, tuple(steps))])

    def revise(self, steps: Iterable[str]) -> TaskFlowRevision:
        """
        Create a new revision with an incremented revision number and the provided steps.
        
        Returns:
            TaskFlowRevision: The newly created revision.
        """
        revision = TaskFlowRevision(self.revisions[-1].revision + 1, tuple(steps))
        self.revisions.append(revision)
        return revision

    @property
    def current(self) -> TaskFlowRevision:
        """
        Retrieve the current task flow revision.
        
        Returns:
        	The latest TaskFlowRevision.
        """
        return self.revisions[-1]


class HookRegistry:
    """Lifecycle hook registry for scripts/actions such as session reset."""

    def __init__(self) -> None:
        """
        Initialize an empty hook registry.
        """
        self._hooks: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def on(self, event: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """
        Register a handler to be invoked when an event is emitted.
        
        Parameters:
        	event (str): The event to listen for
        	handler (Callable[[dict[str, Any]], None]): The handler function to register
        """
        self._hooks.setdefault(event, []).append(handler)

    def emit(self, event: str, payload: dict[str, Any]) -> int:
        """
        Invoke all handlers registered for an event with the given payload.
        
        Returns:
        	int: The number of handlers registered for the event.
        """
        for handler in self._hooks.get(event, []):
            handler(payload)
        return len(self._hooks.get(event, []))


class PluginHookBus:
    """In-process interception point for tool calls."""

    def __init__(self) -> None:
        self._interceptors: list[Callable[[str, dict[str, Any]], dict[str, Any]]] = []

    def intercept(self, interceptor: Callable[[str, dict[str, Any]], dict[str, Any]]) -> None:
        """
        Register an interceptor for tool-call transformation.
        
        Parameters:
            interceptor: A callable that receives a tool name and payload dict, returning a modified payload dict.
        """
        self._interceptors.append(interceptor)

    def before_tool_call(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Applies registered interceptors to a tool call payload in sequence.
        
        Parameters:
        	tool (str): The name of the tool being called
        	payload (dict[str, Any]): The payload for the tool call
        
        Returns:
        	dict[str, Any]: The payload after all interceptors have been applied
        """
        for interceptor in self._interceptors:
            payload = interceptor(tool, payload)
        return payload


@dataclass
class StandingOrders:
    """Persistent instructions injected into every session."""

    orders: list[str] = field(default_factory=list)

    def add(self, instruction: str) -> None:
        """
        Add an instruction if it is not already present.
        """
        if instruction not in self.orders:
            self.orders.append(instruction)

    def inject(self, session_context: dict[str, Any]) -> dict[str, Any]:
        """
        Merges standing orders into a session context.
        
        Parameters:
            session_context (dict[str, Any]): The context dictionary to augment.
        
        Returns:
            dict[str, Any]: A new dictionary with standing orders added under the "standing_orders" key.
        """
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
        """
        Recommend a background mechanism for the given use-case text.
        
        Returns:
            The name of a recommended mechanism; defaults to "Task Flows" if no keywords match.
        """
        lowered = use_case.lower()
        for key, mechanism in cls.REFERENCE.items():
            if key in lowered:
                return mechanism
        return "Task Flows"


def _matches(field: str, value: int) -> bool:
    """
    Determine if a value matches a cron field pattern.
    
    Parameters:
        field (str): Cron field pattern ('*' matches any, '*/n' matches divisible by n, or a specific number)
    
    Returns:
        True if the value matches the field pattern, False otherwise.
    """
    if field == "*":
        return True
    if field.startswith("*/"):
        return value % int(field[2:]) == 0
    return int(field) == value


def _minute_floor(value: datetime) -> datetime:
    """
    Truncate a datetime to minute precision.
    
    Parameters:
    	value (datetime): A datetime object to truncate
    
    Returns:
    	datetime: The input datetime with seconds and microseconds set to zero
    """
    return value.replace(second=0, microsecond=0)


def _extract_due_hint(text: str) -> str | None:
    """
    Extract a temporal hint phrase from text.
    
    Returns:
        The matched temporal phrase (e.g., "tomorrow", "next week") if found, `None` otherwise.
    """
    match = re.search(r"\b(tomorrow|next week|next month|on \w+)\b", text, re.IGNORECASE)
    return match.group(0) if match else None


def _summarize(text: str) -> str:
    """
    Extract the first sentence of text, truncated to 120 characters.
    
    Returns:
        str: The first sentence of the input text, truncated to at most 120 characters.
    """
    return text.strip().split(".")[0][:120]
