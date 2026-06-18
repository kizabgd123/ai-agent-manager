from __future__ import annotations

import argparse
import json
from pathlib import Path

from .mechanisms import BackgroundTaskRegistry


def main() -> int:
    parser = argparse.ArgumentParser(prog="tasks")
    parser.add_argument("command", choices=("list", "audit"))
    parser.add_argument("--ledger", default=".agent/tasks-ledger.jsonl")
    args = parser.parse_args()

    registry = BackgroundTaskRegistry(Path(args.ledger))
    if args.command == "list":
        print(json.dumps([task.__dict__ for task in registry.list()], indent=2, sort_keys=True))
    else:
        print(json.dumps(registry.audit(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
