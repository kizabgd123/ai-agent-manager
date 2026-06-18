# GitHub-Centric Multi-Agent Software Factory

This repository now includes a lightweight reference implementation for the
software factory described in issue #11. The implementation keeps provider calls
abstract so it can run in tests, GitHub Actions, webhook services, or local
experiments before real CLI adapters are wired in.

## Architecture

```text
GitHub Issues
  -> Orchestrator
  -> Routing Engine
  -> Agent Registry
  -> Agent Workers
  -> Validation Pipeline
  -> Pull Requests
  -> Retrospective Learning System
```

## Implemented Foundation

- **Orchestrator service:** normalizes GitHub Issue payloads, preserves the
  repository name for multi-repo coordination, classifies issues, and invokes the
  multi-agent pipeline.
- **Agent registry:** stores agent metadata for Gemini CLI, Kiro CLI, Ollama
  Local, and Codex, including capabilities, cost, latency, local-only status,
  availability, and quality score.
- **Routing engine:** detects issue type, language, domain, and sensitivity;
  prefers local/cost-effective agents; and enforces a hard policy that sensitive
  issues route only to local-only agents.
- **Multi-agent pipeline:** chains implementation, review, automated test
  generation, and documentation stages, passing each stage's artifact to the
  next.
- **Benchmarking harness:** sends identical issues to every available agent and
  records scoring dimensions such as speed, correctness, code quality, and test
  coverage.
- **Retrospective learning:** records completed-task outcomes and feeds quality
  weights back into routing decisions.

## Validation and Security Model

Sensitive keywords such as secrets, tokens, credentials, private keys, PII, and
security vulnerabilities activate local-only routing. In the default registry,
`ollama-local` is the only local-only agent, so those issues cannot be routed to
cloud-backed agents.

The validation pipeline should run before PR creation in production. The current
repository CI already executes tests through GitHub Actions; additional linting
and security scanning can be layered into the workflow as adapters mature.

## Next Production Adapters

1. Add a GitHub webhook/API entrypoint that calls `Orchestrator.handle_github_issue`.
2. Replace test workers with CLI adapters for Gemini CLI, Kiro CLI, Ollama, and
   Codex.
3. Persist `RetrospectiveLearningStore` data in a database for the dashboard.
4. Add PR creation and branch management around successful validated artifacts.
5. Publish benchmark and metrics output to GitHub Pages or an internal service.
