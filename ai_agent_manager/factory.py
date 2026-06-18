"""GitHub-centric multi-agent software factory primitives.

The module intentionally keeps external integration points abstract so it can be
used in GitHub Actions, a webhook service, or local tests without network calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from statistics import mean
from time import perf_counter
from typing import Callable, Iterable, Mapping, Protocol


class IssueType(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    SECURITY = "security"
    DEPENDENCY = "dependency"
    DOCUMENTATION = "documentation"


class PipelineStage(str, Enum):
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    TEST_GENERATION = "test_generation"
    DOCUMENTATION = "documentation"


@dataclass(frozen=True)
class GitHubIssue:
    """Normalized GitHub Issue payload consumed by the orchestrator."""

    number: int
    title: str
    body: str
    labels: tuple[str, ...] = ()
    repository: str = "default"

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.body}\n{' '.join(self.labels)}".lower()


@dataclass(frozen=True)
class Agent:
    """Registered agent metadata used for dynamic discovery and routing."""

    name: str
    capabilities: frozenset[str]
    cost_per_task: float
    latency_ms: int
    local_only: bool = False
    available: bool = True
    quality_score: float = 1.0

    def can_handle(self, issue_type: IssueType, language: str, domain: str) -> bool:
        required = {issue_type.value, language, domain}
        return bool(required & self.capabilities) or "general" in self.capabilities


@dataclass
class AgentRegistry:
    """In-memory registry with health-check based availability updates."""

    agents: dict[str, Agent] = field(default_factory=dict)
    health_checks: dict[str, Callable[[], bool]] = field(default_factory=dict)

    def register(self, agent: Agent, health_check: Callable[[], bool] | None = None) -> None:
        self.agents[agent.name] = agent
        if health_check is not None:
            self.health_checks[agent.name] = health_check

    def refresh_availability(self) -> None:
        for name, check in self.health_checks.items():
            agent = self.agents[name]
            self.agents[name] = Agent(
                name=agent.name,
                capabilities=agent.capabilities,
                cost_per_task=agent.cost_per_task,
                latency_ms=agent.latency_ms,
                local_only=agent.local_only,
                available=bool(check()),
                quality_score=agent.quality_score,
            )

    def available_agents(self) -> list[Agent]:
        return [agent for agent in self.agents.values() if agent.available]


@dataclass(frozen=True)
class RouteDecision:
    agent: Agent
    issue_type: IssueType
    language: str
    domain: str
    sensitive: bool
    score: float


@dataclass
class RetrospectiveLearningStore:
    """Captures completed-task outcomes and exposes routing weights."""

    outcomes: list[dict[str, float | str]] = field(default_factory=list)

    def record(self, agent: str, issue_type: IssueType, resolution_time: float, quality_score: float, cost: float) -> None:
        self.outcomes.append(
            {
                "agent": agent,
                "issue_type": issue_type.value,
                "resolution_time": resolution_time,
                "quality_score": quality_score,
                "cost": cost,
            }
        )

    def quality_weight(self, agent: str, issue_type: IssueType) -> float:
        scores = [
            float(row["quality_score"])
            for row in self.outcomes
            if row["agent"] == agent and row["issue_type"] == issue_type.value
        ]
        return mean(scores) if scores else 1.0


class RoutingEngine:
    """Context-aware router with local-first cost optimization and security policy."""

    LANGUAGE_KEYWORDS = {
        "python": ("python", ".py", "pytest", "django", "fastapi"),
        "javascript": ("javascript", "typescript", ".js", ".ts", "react", "node"),
        "sql": ("sql", "postgres", "supabase", "migration"),
        "documentation": ("readme", "docs", "markdown"),
    }
    DOMAIN_KEYWORDS = {
        "security": ("secret", "token", "credential", "vulnerability", "auth"),
        "ci": ("github actions", "workflow", "ci", "cd", "deploy"),
        "data": ("database", "schema", "analytics", "metrics"),
    }
    SENSITIVE_KEYWORDS = ("secret", "token", "credential", "private key", "pii", "security")

    def __init__(self, registry: AgentRegistry, learning_store: RetrospectiveLearningStore | None = None):
        self.registry = registry
        self.learning_store = learning_store or RetrospectiveLearningStore()

    def classify_issue(self, issue: GitHubIssue) -> IssueType:
        text = issue.text
        if any(word in text for word in ("cve", "vulnerability", "secret", "security")):
            return IssueType.SECURITY
        if any(word in text for word in ("dependency", "upgrade", "bump", "package")):
            return IssueType.DEPENDENCY
        if any(word in text for word in ("docs", "readme", "documentation")):
            return IssueType.DOCUMENTATION
        if any(word in text for word in ("bug", "error", "exception", "broken", "fix")):
            return IssueType.BUG
        return IssueType.FEATURE

    def detect_language(self, issue: GitHubIssue) -> str:
        return self._detect(issue.text, self.LANGUAGE_KEYWORDS, "general")

    def detect_domain(self, issue: GitHubIssue) -> str:
        return self._detect(issue.text, self.DOMAIN_KEYWORDS, "general")

    def is_sensitive(self, issue: GitHubIssue) -> bool:
        return any(keyword in issue.text for keyword in self.SENSITIVE_KEYWORDS)

    def route(self, issue: GitHubIssue) -> RouteDecision:
        issue_type = self.classify_issue(issue)
        language = self.detect_language(issue)
        domain = self.detect_domain(issue)
        sensitive = self.is_sensitive(issue)
        candidates = [
            agent
            for agent in self.registry.available_agents()
            if (not sensitive or agent.local_only) and agent.can_handle(issue_type, language, domain)
        ]
        if not candidates:
            raise ValueError("No available agent satisfies routing and security policy")

        def score(agent: Agent) -> float:
            learning = self.learning_store.quality_weight(agent.name, issue_type)
            local_bonus = 0.02 if agent.local_only else 0.0
            return (agent.quality_score * learning) + local_bonus - (agent.cost_per_task * 0.01) - (agent.latency_ms / 100000)

        best_score, selected = max(((score(agent), agent) for agent in candidates), key=lambda x: x[0])
        return RouteDecision(selected, issue_type, language, domain, sensitive, best_score)

    @staticmethod
    def _detect(text: str, keyword_map: Mapping[str, Iterable[str]], default: str) -> str:
        for name, keywords in keyword_map.items():
            if any(keyword in text for keyword in keywords):
                return name
        return default


@dataclass(frozen=True)
class AgentTask:
    stage: PipelineStage
    issue: GitHubIssue
    route: RouteDecision
    input_artifact: str


class StageWorker(Protocol):
    def __call__(self, task: AgentTask) -> str: ...


@dataclass
class MultiAgentPipeline:
    """Chains implementation, review, test generation, and documentation stages."""

    router: RoutingEngine
    workers: Mapping[PipelineStage, StageWorker]
    stages: tuple[PipelineStage, ...] = (
        PipelineStage.IMPLEMENTATION,
        PipelineStage.REVIEW,
        PipelineStage.TEST_GENERATION,
        PipelineStage.DOCUMENTATION,
    )

    def run(self, issue: GitHubIssue, route: RouteDecision | None = None) -> dict[str, str]:
        if route is None:
            route = self.router.route(issue)
        artifact = issue.body
        outputs: dict[str, str] = {}
        for stage in self.stages:
            task = AgentTask(stage=stage, issue=issue, route=route, input_artifact=artifact)
            artifact = self.workers[stage](task)
            outputs[stage.value] = artifact
        return outputs


@dataclass
class Orchestrator:
    """Receives GitHub issues, coordinates repositories, and invokes pipelines."""

    router: RoutingEngine
    pipeline: MultiAgentPipeline

    def parse_issue(self, payload: Mapping[str, object]) -> GitHubIssue:
        issue = payload.get("issue", {}) if isinstance(payload.get("issue", {}), Mapping) else {}
        repo = payload.get("repository", {}) if isinstance(payload.get("repository", {}), Mapping) else {}
        labels = issue.get("labels", []) if isinstance(issue, Mapping) else []
        label_names = tuple(label.get("name", "") for label in labels if isinstance(label, Mapping))
        return GitHubIssue(
            number=int(issue.get("number", 0)),
            title=str(issue.get("title", "")),
            body=str(issue.get("body", "")),
            labels=label_names,
            repository=str(repo.get("full_name", "default")),
        )

    def handle_github_issue(self, payload: Mapping[str, object]) -> dict[str, object]:
        issue = self.parse_issue(payload)
        route = self.router.route(issue)
        outputs = self.pipeline.run(issue, route=route)
        return {
            "issue": issue.number,
            "repository": issue.repository,
            "agent": route.agent.name,
            "classification": route.issue_type.value,
            "language": route.language,
            "domain": route.domain,
            "sensitive": route.sensitive,
            "outputs": outputs,
        }


@dataclass
class BenchmarkHarness:
    """Sends identical issues to policy-eligible agents and scores responses."""

    registry: AgentRegistry
    scoring: Callable[[Agent, GitHubIssue, str, float], dict[str, float]]
    router: RoutingEngine | None = None

    def run(self, issues: Iterable[GitHubIssue], worker: Callable[[Agent, GitHubIssue], str]) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        policy = self.router or RoutingEngine(self.registry)
        issue_to_agents = []
        for issue in issues:
            sensitive = policy.is_sensitive(issue)
            agents = [agent for agent in self.registry.available_agents() if not sensitive or agent.local_only]
            if not agents:
                raise ValueError(f"No available agent satisfies benchmarking security policy for issue {issue.number}")
            issue_to_agents.append((issue, agents))
        for issue, agents in issue_to_agents:
            for agent in agents:
                start = perf_counter()
                output = worker(agent, issue)
                elapsed = perf_counter() - start
                results.append(
                    {
                        "issue": issue.number,
                        "agent": agent.name,
                        "output": output,
                        "scores": self.scoring(agent, issue, output, elapsed),
                    }
                )
        return results


def default_registry() -> AgentRegistry:
    """Register Gemini CLI, Kiro CLI, Ollama Local, and Codex defaults."""
    registry = AgentRegistry()
    registry.register(Agent("ollama-local", frozenset({"general", "security", "python", "documentation"}), 0.0, 900, True, True, 0.86))
    registry.register(Agent("codex", frozenset({"general", "python", "javascript", "bug", "feature", "documentation"}), 1.5, 700, False, True, 0.94))
    registry.register(Agent("gemini-cli", frozenset({"general", "documentation", "data", "sql"}), 1.0, 650, False, True, 0.9))
    registry.register(Agent("kiro-cli", frozenset({"general", "ci", "dependency", "javascript"}), 1.2, 750, False, True, 0.88))
    return registry
