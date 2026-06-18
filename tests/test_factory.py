import pytest

from ai_agent_manager.factory import (
    Agent,
    AgentRegistry,
    AgentTask,
    BenchmarkHarness,
    GitHubIssue,
    IssueType,
    MultiAgentPipeline,
    Orchestrator,
    PipelineStage,
    RetrospectiveLearningStore,
    RouteDecision,
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


# ---------------------------------------------------------------------------
# GitHubIssue
# ---------------------------------------------------------------------------

class TestGitHubIssue:
    def test_text_combines_title_body_labels_lowercased(self):
        issue = GitHubIssue(1, "Fix BUG", "Error in Python", ("Bug",))
        text = issue.text
        assert "fix bug" in text
        assert "error in python" in text
        assert "bug" in text

    def test_text_is_fully_lowercase(self):
        issue = GitHubIssue(2, "UPPERCASE TITLE", "UPPERCASE BODY", ("LABEL",))
        assert issue.text == issue.text.lower()

    def test_default_labels_and_repository(self):
        issue = GitHubIssue(3, "title", "body")
        assert issue.labels == ()
        assert issue.repository == "default"

    def test_text_with_no_labels(self):
        issue = GitHubIssue(4, "Add feature", "description")
        assert "add feature" in issue.text
        assert "description" in issue.text

    def test_multiple_labels_included_in_text(self):
        issue = GitHubIssue(5, "t", "b", ("alpha", "beta", "gamma"))
        for label in ("alpha", "beta", "gamma"):
            assert label in issue.text


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class TestAgent:
    def test_can_handle_via_general_capability(self):
        agent = Agent("gen", frozenset({"general"}), 1.0, 500)
        assert agent.can_handle(IssueType.SECURITY, "cobol", "aerospace")

    def test_can_handle_via_issue_type_capability(self):
        agent = Agent("spec", frozenset({"bug"}), 1.0, 500)
        assert agent.can_handle(IssueType.BUG, "cobol", "aerospace")

    def test_can_handle_via_language_capability(self):
        agent = Agent("py", frozenset({"python"}), 1.0, 500)
        assert agent.can_handle(IssueType.FEATURE, "python", "aerospace")

    def test_can_handle_via_domain_capability(self):
        agent = Agent("dom", frozenset({"ci"}), 1.0, 500)
        assert agent.can_handle(IssueType.FEATURE, "cobol", "ci")

    def test_cannot_handle_no_matching_capability(self):
        agent = Agent("none", frozenset({"sql"}), 1.0, 500)
        assert not agent.can_handle(IssueType.BUG, "python", "aerospace")

    def test_default_available_and_quality(self):
        agent = Agent("a", frozenset({"general"}), 0.5, 200)
        assert agent.available is True
        assert agent.local_only is False
        assert agent.quality_score == 1.0


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    def test_register_adds_agent(self):
        registry = AgentRegistry()
        agent = Agent("alpha", frozenset({"general"}), 0.0, 100)
        registry.register(agent)
        assert "alpha" in registry.agents

    def test_register_without_health_check_stores_no_check(self):
        registry = AgentRegistry()
        agent = Agent("beta", frozenset({"general"}), 0.0, 100)
        registry.register(agent)
        assert "beta" not in registry.health_checks

    def test_register_with_health_check(self):
        registry = AgentRegistry()
        agent = Agent("gamma", frozenset({"general"}), 0.0, 100)
        registry.register(agent, health_check=lambda: True)
        assert "gamma" in registry.health_checks

    def test_available_agents_excludes_unavailable(self):
        registry = AgentRegistry()
        available = Agent("up", frozenset({"general"}), 0.0, 100, available=True)
        unavailable = Agent("down", frozenset({"general"}), 0.0, 100, available=False)
        registry.register(available)
        registry.register(unavailable)
        names = [a.name for a in registry.available_agents()]
        assert "up" in names
        assert "down" not in names

    def test_refresh_availability_marks_agent_unavailable(self):
        registry = AgentRegistry()
        agent = Agent("svc", frozenset({"general"}), 0.0, 100, available=True)
        registry.register(agent, health_check=lambda: False)
        registry.refresh_availability()
        assert registry.agents["svc"].available is False

    def test_refresh_availability_marks_agent_available(self):
        registry = AgentRegistry()
        agent = Agent("svc2", frozenset({"general"}), 0.0, 100, available=False)
        registry.register(agent, health_check=lambda: True)
        registry.refresh_availability()
        assert registry.agents["svc2"].available is True

    def test_refresh_preserves_other_agent_attributes(self):
        registry = AgentRegistry()
        agent = Agent("svc3", frozenset({"python", "general"}), 2.5, 400, local_only=True, available=True, quality_score=0.77)
        registry.register(agent, health_check=lambda: False)
        registry.refresh_availability()
        refreshed = registry.agents["svc3"]
        assert refreshed.name == "svc3"
        assert refreshed.capabilities == frozenset({"python", "general"})
        assert refreshed.cost_per_task == 2.5
        assert refreshed.latency_ms == 400
        assert refreshed.local_only is True
        assert refreshed.quality_score == 0.77
        assert refreshed.available is False

    def test_refresh_only_updates_agents_with_health_checks(self):
        registry = AgentRegistry()
        with_check = Agent("checked", frozenset({"general"}), 0.0, 100, available=True)
        without_check = Agent("unchecked", frozenset({"general"}), 0.0, 100, available=True)
        registry.register(with_check, health_check=lambda: False)
        registry.register(without_check)
        registry.refresh_availability()
        assert registry.agents["checked"].available is False
        assert registry.agents["unchecked"].available is True


# ---------------------------------------------------------------------------
# RetrospectiveLearningStore
# ---------------------------------------------------------------------------

class TestRetrospectiveLearningStore:
    def test_quality_weight_returns_one_when_no_data(self):
        store = RetrospectiveLearningStore()
        assert store.quality_weight("any-agent", IssueType.BUG) == 1.0

    def test_quality_weight_returns_one_for_different_issue_type(self):
        store = RetrospectiveLearningStore()
        store.record("agent-a", IssueType.BUG, 5.0, 0.9, 1.0)
        assert store.quality_weight("agent-a", IssueType.FEATURE) == 1.0

    def test_quality_weight_returns_recorded_score(self):
        store = RetrospectiveLearningStore()
        store.record("agent-a", IssueType.BUG, 5.0, 0.8, 1.0)
        assert store.quality_weight("agent-a", IssueType.BUG) == pytest.approx(0.8)

    def test_quality_weight_averages_multiple_records(self):
        store = RetrospectiveLearningStore()
        store.record("agent-a", IssueType.FEATURE, 5.0, 0.6, 1.0)
        store.record("agent-a", IssueType.FEATURE, 3.0, 1.0, 0.5)
        assert store.quality_weight("agent-a", IssueType.FEATURE) == pytest.approx(0.8)

    def test_quality_weight_isolates_agents(self):
        store = RetrospectiveLearningStore()
        store.record("agent-a", IssueType.BUG, 5.0, 0.5, 1.0)
        store.record("agent-b", IssueType.BUG, 5.0, 0.9, 1.0)
        assert store.quality_weight("agent-a", IssueType.BUG) == pytest.approx(0.5)
        assert store.quality_weight("agent-b", IssueType.BUG) == pytest.approx(0.9)

    def test_record_stores_all_fields(self):
        store = RetrospectiveLearningStore()
        store.record("my-agent", IssueType.SECURITY, 12.5, 0.95, 2.0)
        row = store.outcomes[0]
        assert row["agent"] == "my-agent"
        assert row["issue_type"] == "security"
        assert row["resolution_time"] == 12.5
        assert row["quality_score"] == 0.95
        assert row["cost"] == 2.0


# ---------------------------------------------------------------------------
# RoutingEngine – classify_issue
# ---------------------------------------------------------------------------

class TestRoutingEngineClassifyIssue:
    def setup_method(self):
        self.router = RoutingEngine(default_registry())

    def _issue(self, title, body="", labels=()):
        return GitHubIssue(1, title, body, labels)

    def test_classifies_security_via_cve(self):
        assert self.router.classify_issue(self._issue("CVE-2024-1234")) == IssueType.SECURITY

    def test_classifies_security_via_vulnerability(self):
        assert self.router.classify_issue(self._issue("vulnerability found")) == IssueType.SECURITY

    def test_classifies_security_via_secret(self):
        assert self.router.classify_issue(self._issue("secret key exposed")) == IssueType.SECURITY

    def test_classifies_security_has_higher_priority_than_bug(self):
        # "security" and "bug" both present – security wins
        assert self.router.classify_issue(self._issue("security bug")) == IssueType.SECURITY

    def test_classifies_dependency(self):
        assert self.router.classify_issue(self._issue("Bump dependency version")) == IssueType.DEPENDENCY

    def test_classifies_dependency_via_upgrade(self):
        assert self.router.classify_issue(self._issue("upgrade package to latest")) == IssueType.DEPENDENCY

    def test_classifies_documentation_via_docs(self):
        assert self.router.classify_issue(self._issue("Update docs")) == IssueType.DOCUMENTATION

    def test_classifies_documentation_via_readme(self):
        assert self.router.classify_issue(self._issue("Fix README typo")) == IssueType.DOCUMENTATION

    def test_classifies_bug_via_error(self):
        assert self.router.classify_issue(self._issue("error thrown on startup")) == IssueType.BUG

    def test_classifies_bug_via_exception(self):
        assert self.router.classify_issue(self._issue("exception in parser")) == IssueType.BUG

    def test_classifies_bug_via_fix(self):
        assert self.router.classify_issue(self._issue("fix broken login")) == IssueType.BUG

    def test_classifies_feature_as_default(self):
        assert self.router.classify_issue(self._issue("Add new export button")) == IssueType.FEATURE


# ---------------------------------------------------------------------------
# RoutingEngine – detect_language / detect_domain / is_sensitive
# ---------------------------------------------------------------------------

class TestRoutingEngineDetect:
    def setup_method(self):
        self.router = RoutingEngine(default_registry())

    def _issue(self, body):
        return GitHubIssue(1, body, body)

    def test_detect_language_python(self):
        assert self.router.detect_language(self._issue("pytest failure in .py file")) == "python"

    def test_detect_language_javascript(self):
        assert self.router.detect_language(self._issue("react component error")) == "javascript"

    def test_detect_language_sql(self):
        assert self.router.detect_language(self._issue("postgres migration needed")) == "sql"

    def test_detect_language_documentation(self):
        assert self.router.detect_language(self._issue("update readme markdown")) == "documentation"

    def test_detect_language_general_default(self):
        assert self.router.detect_language(self._issue("unrelated topic")) == "general"

    def test_detect_domain_security(self):
        assert self.router.detect_domain(self._issue("auth token validation")) == "security"

    def test_detect_domain_ci(self):
        assert self.router.detect_domain(self._issue("github actions workflow deploy")) == "ci"

    def test_detect_domain_data(self):
        assert self.router.detect_domain(self._issue("database schema analytics")) == "data"

    def test_detect_domain_general_default(self):
        assert self.router.detect_domain(self._issue("unrelated topic")) == "general"

    def test_is_sensitive_with_token(self):
        assert self.router.is_sensitive(self._issue("api token exposed")) is True

    def test_is_sensitive_with_credential(self):
        assert self.router.is_sensitive(self._issue("credential leak")) is True

    def test_is_sensitive_with_private_key(self):
        assert self.router.is_sensitive(self._issue("private key in source")) is True

    def test_is_sensitive_with_pii(self):
        assert self.router.is_sensitive(self._issue("pii data stored")) is True

    def test_is_sensitive_with_security(self):
        assert self.router.is_sensitive(self._issue("security audit")) is True

    def test_is_not_sensitive_generic_issue(self):
        assert self.router.is_sensitive(self._issue("add pagination to list view")) is False


# ---------------------------------------------------------------------------
# RoutingEngine – route edge cases
# ---------------------------------------------------------------------------

class TestRoutingEngineRoute:
    def test_route_raises_when_no_candidates(self):
        registry = AgentRegistry()
        registry.register(Agent("cloud-only", frozenset({"general"}), 1.0, 500, local_only=False))
        router = RoutingEngine(registry)
        sensitive_issue = GitHubIssue(1, "secret token leaked", "credential exposure")
        with pytest.raises(ValueError, match="No available agent satisfies routing and security policy"):
            router.route(sensitive_issue)

    def test_route_raises_when_registry_empty(self):
        router = RoutingEngine(AgentRegistry())
        with pytest.raises(ValueError):
            router.route(GitHubIssue(1, "any issue", "body"))

    def test_route_non_sensitive_issue_can_use_cloud_agent(self):
        registry = AgentRegistry()
        registry.register(Agent("cloud", frozenset({"general"}), 0.5, 300, local_only=False))
        router = RoutingEngine(registry)
        decision = router.route(GitHubIssue(1, "Add feature", "description"))
        assert decision.agent.name == "cloud"
        assert decision.sensitive is False

    def test_route_prefers_local_agent_for_sensitive_issues(self):
        registry = AgentRegistry()
        registry.register(Agent("cloud", frozenset({"general"}), 0.0, 100, local_only=False))
        registry.register(Agent("local", frozenset({"general"}), 0.0, 100, local_only=True))
        router = RoutingEngine(registry)
        decision = router.route(GitHubIssue(1, "secret exposed", "credential leak"))
        assert decision.agent.name == "local"

    def test_route_skips_unavailable_agents(self):
        registry = AgentRegistry()
        registry.register(Agent("up", frozenset({"general"}), 0.0, 100, available=True))
        registry.register(Agent("down", frozenset({"general"}), 0.0, 100, available=False))
        router = RoutingEngine(registry)
        decision = router.route(GitHubIssue(1, "any", "body"))
        assert decision.agent.name == "up"

    def test_route_decision_contains_all_fields(self):
        router = RoutingEngine(default_registry())
        issue = GitHubIssue(1, "Python bug", "error in .py file")
        decision = router.route(issue)
        assert isinstance(decision.issue_type, IssueType)
        assert isinstance(decision.language, str)
        assert isinstance(decision.domain, str)
        assert isinstance(decision.sensitive, bool)
        assert isinstance(decision.score, float)

    def test_local_bonus_increases_score(self):
        """Local-only agent should receive a 0.02 bonus in its score."""
        registry = AgentRegistry()
        # Identical quality/cost/latency except local_only
        cloud = Agent("cloud", frozenset({"general"}), 1.0, 500, local_only=False, quality_score=1.0)
        local = Agent("local", frozenset({"general"}), 1.0, 500, local_only=True, quality_score=1.0)
        registry.register(cloud)
        registry.register(local)
        router = RoutingEngine(registry)
        decision = router.route(GitHubIssue(1, "generic feature", "description"))
        assert decision.agent.name == "local"


# ---------------------------------------------------------------------------
# MultiAgentPipeline
# ---------------------------------------------------------------------------

class TestMultiAgentPipeline:
    def _make_pipeline(self, registry=None):
        if registry is None:
            registry = default_registry()
        router = RoutingEngine(registry)
        call_log = []

        def worker(task):
            call_log.append(task.stage)
            return f"[{task.stage.value}]{task.input_artifact}"

        workers = {stage: worker for stage in PipelineStage}
        pipeline = MultiAgentPipeline(router=router, workers=workers)
        return pipeline, call_log

    def test_run_returns_output_for_every_stage(self):
        pipeline, _ = self._make_pipeline()
        issue = GitHubIssue(1, "Add feature", "body text")
        outputs = pipeline.run(issue)
        assert set(outputs.keys()) == {stage.value for stage in PipelineStage}

    def test_run_chains_artifacts_between_stages(self):
        pipeline, _ = self._make_pipeline()
        issue = GitHubIssue(1, "Add feature", "initial body")
        outputs = pipeline.run(issue)
        # Each stage wraps the previous artifact, so later stages contain earlier content
        assert "initial body" in outputs[PipelineStage.IMPLEMENTATION.value]
        assert PipelineStage.IMPLEMENTATION.value in outputs[PipelineStage.REVIEW.value]

    def test_run_invokes_all_four_stages(self):
        pipeline, call_log = self._make_pipeline()
        issue = GitHubIssue(1, "feature", "body")
        pipeline.run(issue)
        assert set(call_log) == set(PipelineStage)

    def test_pipeline_with_custom_stages_subset(self):
        router = RoutingEngine(default_registry())
        worker = lambda task: f"done:{task.stage.value}"
        pipeline = MultiAgentPipeline(
            router=router,
            workers={stage: worker for stage in PipelineStage},
            stages=(PipelineStage.IMPLEMENTATION, PipelineStage.TEST_GENERATION),
        )
        issue = GitHubIssue(1, "minimal pipeline", "body")
        outputs = pipeline.run(issue)
        assert set(outputs.keys()) == {"implementation", "test_generation"}
        assert "review" not in outputs


# ---------------------------------------------------------------------------
# Orchestrator – parse_issue edge cases
# ---------------------------------------------------------------------------

class TestOrchestratorParseIssue:
    def _make_orchestrator(self):
        registry = default_registry()
        router = RoutingEngine(registry)
        worker = lambda task: task.input_artifact
        pipeline = MultiAgentPipeline(router=router, workers={stage: worker for stage in PipelineStage})
        return Orchestrator(router=router, pipeline=pipeline)

    def test_parse_issue_minimal_payload(self):
        orch = self._make_orchestrator()
        issue = orch.parse_issue({})
        assert issue.number == 0
        assert issue.title == ""
        assert issue.body == ""
        assert issue.labels == ()
        assert issue.repository == "default"

    def test_parse_issue_full_payload(self):
        orch = self._make_orchestrator()
        payload = {
            "issue": {
                "number": 99,
                "title": "My Title",
                "body": "My Body",
                "labels": [{"name": "feature"}, {"name": "help wanted"}],
            },
            "repository": {"full_name": "user/repo"},
        }
        issue = orch.parse_issue(payload)
        assert issue.number == 99
        assert issue.title == "My Title"
        assert issue.body == "My Body"
        assert "feature" in issue.labels
        assert "help wanted" in issue.labels
        assert issue.repository == "user/repo"

    def test_parse_issue_non_mapping_issue_value_defaults(self):
        orch = self._make_orchestrator()
        issue = orch.parse_issue({"issue": "not-a-mapping"})
        assert issue.number == 0
        assert issue.title == ""

    def test_parse_issue_labels_with_non_mapping_entries_skipped(self):
        orch = self._make_orchestrator()
        payload = {
            "issue": {
                "number": 1,
                "title": "t",
                "body": "b",
                "labels": [{"name": "valid"}, "not-a-dict", None],
            }
        }
        issue = orch.parse_issue(payload)
        assert issue.labels == ("valid",)

    def test_parse_issue_missing_repository_defaults(self):
        orch = self._make_orchestrator()
        payload = {"issue": {"number": 5, "title": "t", "body": "b", "labels": []}}
        issue = orch.parse_issue(payload)
        assert issue.repository == "default"

    def test_handle_github_issue_returns_all_keys(self):
        orch = self._make_orchestrator()
        payload = {
            "issue": {"number": 1, "title": "Add feature", "body": "body", "labels": []},
            "repository": {"full_name": "org/repo"},
        }
        result = orch.handle_github_issue(payload)
        for key in ("issue", "repository", "agent", "classification", "language", "domain", "sensitive", "outputs"):
            assert key in result


# ---------------------------------------------------------------------------
# BenchmarkHarness – edge cases
# ---------------------------------------------------------------------------

class TestBenchmarkHarnessEdgeCases:
    def _simple_scoring(self, agent, issue, output, elapsed):
        return {"speed": 1.0, "correctness": 1.0}

    def test_empty_issues_returns_empty_results(self):
        harness = BenchmarkHarness(registry=default_registry(), scoring=self._simple_scoring)
        results = harness.run([], lambda a, i: "output")
        assert results == []

    def test_no_available_agents_returns_empty_results(self):
        registry = AgentRegistry()
        registry.register(Agent("down", frozenset({"general"}), 0.0, 100, available=False))
        harness = BenchmarkHarness(registry=registry, scoring=self._simple_scoring)
        issue = GitHubIssue(1, "title", "body")
        results = harness.run([issue], lambda a, i: "output")
        assert results == []

    def test_multiple_issues_multiplies_results(self):
        registry = AgentRegistry()
        registry.register(Agent("single", frozenset({"general"}), 0.0, 100))
        harness = BenchmarkHarness(registry=registry, scoring=self._simple_scoring)
        issues = [GitHubIssue(i, f"issue {i}", "body") for i in range(3)]
        results = harness.run(issues, lambda a, i: f"{a.name}:{i.number}")
        assert len(results) == 3

    def test_result_structure_contains_required_keys(self):
        registry = AgentRegistry()
        registry.register(Agent("single", frozenset({"general"}), 0.0, 100))
        harness = BenchmarkHarness(registry=registry, scoring=self._simple_scoring)
        results = harness.run([GitHubIssue(1, "t", "b")], lambda a, i: "out")
        row = results[0]
        assert "issue" in row
        assert "agent" in row
        assert "output" in row
        assert "scores" in row

    def test_elapsed_time_is_non_negative(self):
        """Elapsed time passed to scoring is always >= 0."""
        elapsed_values = []

        def capture_scoring(agent, issue, output, elapsed):
            elapsed_values.append(elapsed)
            return {"elapsed": elapsed}

        registry = AgentRegistry()
        registry.register(Agent("fast", frozenset({"general"}), 0.0, 100))
        harness = BenchmarkHarness(registry=registry, scoring=capture_scoring)
        harness.run([GitHubIssue(1, "t", "b")], lambda a, i: "output")
        assert all(e >= 0 for e in elapsed_values)


# ---------------------------------------------------------------------------
# Enum sanity checks
# ---------------------------------------------------------------------------

class TestEnumValues:
    def test_issue_type_values(self):
        assert IssueType.BUG.value == "bug"
        assert IssueType.FEATURE.value == "feature"
        assert IssueType.SECURITY.value == "security"
        assert IssueType.DEPENDENCY.value == "dependency"
        assert IssueType.DOCUMENTATION.value == "documentation"

    def test_pipeline_stage_values(self):
        assert PipelineStage.IMPLEMENTATION.value == "implementation"
        assert PipelineStage.REVIEW.value == "review"
        assert PipelineStage.TEST_GENERATION.value == "test_generation"
        assert PipelineStage.DOCUMENTATION.value == "documentation"

    def test_issue_type_is_str(self):
        for item in IssueType:
            assert isinstance(item, str)

    def test_pipeline_stage_is_str(self):
        for item in PipelineStage:
            assert isinstance(item, str)
