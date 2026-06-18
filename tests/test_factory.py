from ai_agent_manager.factory import (
    BenchmarkHarness,
    GitHubIssue,
    IssueType,
    MultiAgentPipeline,
    Orchestrator,
    PipelineStage,
    RetrospectiveLearningStore,
    RoutingEngine,
    default_registry,
)


def test_default_registry_registers_required_agents():
    registry = default_registry()
    assert {"gemini-cli", "kiro-cli", "ollama-local", "codex"} <= set(registry.agents)


def test_router_classifies_and_routes_sensitive_issues_to_local_agent():
    router = RoutingEngine(default_registry())
    issue = GitHubIssue(
        number=11,
        title="Security bug: leaked token in Python logs",
        body="Fix credential handling without sending secrets to cloud models.",
        labels=("security",),
        repository="org/service",
    )

    decision = router.route(issue)

    assert decision.issue_type == IssueType.SECURITY
    assert decision.language == "python"
    assert decision.sensitive is True
    assert decision.agent.name == "ollama-local"
    assert decision.agent.local_only is True


def test_learning_feedback_can_change_routing_weights():
    store = RetrospectiveLearningStore()
    registry = default_registry()
    router = RoutingEngine(registry, store)
    issue = GitHubIssue(1, "Build a Python feature", "Add FastAPI endpoint", ("feature",))

    before = router.route(issue)
    store.record("ollama-local", IssueType.FEATURE, 10.0, 1.5, 0.0)
    after = router.route(issue)

    assert before.agent.name == "codex"
    assert after.agent.name == "ollama-local"


def test_orchestrator_parses_github_payload_and_runs_all_pipeline_stages():
    router = RoutingEngine(default_registry())

    def worker(task):
        return f"{task.input_artifact}\n[{task.stage.value} by {task.route.agent.name}]"

    pipeline = MultiAgentPipeline(
        router=router,
        workers={stage: worker for stage in PipelineStage},
    )
    orchestrator = Orchestrator(router=router, pipeline=pipeline)
    result = orchestrator.handle_github_issue(
        {
            "issue": {
                "number": 42,
                "title": "Docs: explain GitHub Actions setup",
                "body": "Update README with workflow details.",
                "labels": [{"name": "documentation"}],
            },
            "repository": {"full_name": "org/factory"},
        }
    )

    assert result["issue"] == 42
    assert result["repository"] == "org/factory"
    assert result["classification"] == "documentation"
    assert set(result["outputs"]) == {stage.value for stage in PipelineStage}
    assert "documentation by" in result["outputs"]["documentation"]


def test_benchmark_harness_scores_all_agents_against_same_issue():
    registry = default_registry()
    issue = GitHubIssue(7, "Bug in tests", "pytest failure", ("bug",))
    harness = BenchmarkHarness(
        registry=registry,
        scoring=lambda agent, issue, output, elapsed: {
            "speed": max(0.0, 1.0 - elapsed),
            "correctness": 1.0 if issue.title in output else 0.0,
            "code_quality": agent.quality_score,
            "test_coverage": 0.8,
        },
    )

    results = harness.run([issue], lambda agent, issue: f"{agent.name}: {issue.title}")

    assert len(results) == 4
    assert {row["agent"] for row in results} == set(registry.agents)
    assert all(row["scores"]["correctness"] == 1.0 for row in results)


def test_benchmark_harness_keeps_sensitive_issues_on_local_agents():
    registry = default_registry()
    issue = GitHubIssue(8, "Security bug: leaked token", "Rotate secret credentials", ("security",))
    harness = BenchmarkHarness(
        registry=registry,
        scoring=lambda agent, issue, output, elapsed: {"correctness": 1.0},
    )

    results = harness.run([issue], lambda agent, issue: f"{agent.name}: {issue.title}")

    assert [row["agent"] for row in results] == ["ollama-local"]
