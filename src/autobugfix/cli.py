from __future__ import annotations

import argparse
import json
from pathlib import Path

from autobugfix.workflow import (
    AutoBugFixWorkflow,
    BugDetector,
    ErrorParser,
    PatchApplier,
    PatchProposer,
    TestRunner,
)
from llm.factory import create_llm_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Automatic bug-fix workflow")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--logs-file", default="")
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()

    logs = ""
    if args.logs_file:
        logs = Path(args.logs_file).read_text(encoding="utf-8")

    llm = create_llm_client()
    workflow = AutoBugFixWorkflow(
        detector=BugDetector(),
        parser=ErrorParser(),
        proposer=PatchProposer(llm),
        applier=PatchApplier(),
        tests=TestRunner(),
        max_attempts=args.max_attempts,
    )
    result = workflow.run(Path(args.repo_root), logs=logs)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
