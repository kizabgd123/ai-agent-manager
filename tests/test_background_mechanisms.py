from datetime import datetime, timedelta, timezone

from background.mechanisms import (
    BackgroundTaskRegistry,
    CronSchedule,
    Heartbeat,
    HookRegistry,
    InferredCommitment,
    PluginHookBus,
    StandingOrders,
    TaskFlow,
    UseCaseMapper,
)


def test_cron_supports_exact_and_one_shot_timing():
    now = datetime(2026, 6, 18, 9, 30, tzinfo=timezone.utc)
    assert CronSchedule("30 9 * * *").should_run(now)
    assert CronSchedule.one_shot(now).should_run(now.replace(second=20))


def test_heartbeat_uses_interval_and_scoped_context():
    heartbeat = Heartbeat("inbox", timedelta(minutes=15), ("inbox",))
    now = datetime(2026, 6, 18, 9, 30, tzinfo=timezone.utc)
    assert heartbeat.due(now - timedelta(minutes=16), now)
    assert heartbeat.scoped_context({"inbox": 3, "private": "hidden"}) == {"inbox": 3}


def test_inferred_commitment_detects_follow_up_language():
    commitments = InferredCommitment.infer("u1", "Please remind me tomorrow to send the report.")
    assert len(commitments) == 1
    assert commitments[0].due_hint == "tomorrow"


def test_registry_lists_and_audits_tasks(tmp_path):
    registry = BackgroundTaskRegistry(tmp_path / "tasks.jsonl")
    registry.register("Heartbeat", "check inbox")
    registry.register("Task Flows", "durable onboarding")
    assert len(registry.list()) == 2
    assert registry.audit()["by_status"] == {"registered": 2}


def test_task_flow_tracks_revisions():
    flow = TaskFlow.create("report", ["collect", "summarize"])
    flow.revise(["collect", "summarize", "send"])
    assert flow.current.revision == 2
    assert flow.current.steps[-1] == "send"


def test_hooks_plugin_hooks_and_standing_orders():
    calls = []
    hooks = HookRegistry()
    hooks.on("session.reset", lambda payload: calls.append(payload["session_id"]))
    assert hooks.emit("session.reset", {"session_id": "s1"}) == 1
    assert calls == ["s1"]

    bus = PluginHookBus()
    bus.intercept(lambda tool, payload: {**payload, "tool": tool})
    assert bus.before_tool_call("shell", {"cmd": "echo ok"})["tool"] == "shell"

    orders = StandingOrders()
    orders.add("Always audit background work.")
    assert orders.inject({"session_id": "s1"})["standing_orders"] == ("Always audit background work.",)


def test_use_case_mapper_recommends_reference_mechanism():
    assert UseCaseMapper.recommend("daily report") == "Scheduled Tasks (Cron)"
    assert UseCaseMapper.recommend("calendar awareness") == "Heartbeat"
    assert UseCaseMapper.recommend("persistent compliance") == "Standing Orders"
