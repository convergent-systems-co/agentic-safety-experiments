from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .harness import PersistentDebate
from .profiles import ProfileError
from .repository import DebateRepositoryError, SQLiteDebateRepository


DEFAULT_DB = Path("results/experiment-3/persistent-debate.db")
DEFAULT_PROFILES = Path("agents")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="olympus-experiment3")
    root.add_argument("--db", type=Path, default=DEFAULT_DB)
    root.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    commands = root.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init")
    initialize.add_argument("--run-id")
    run = commands.add_parser("run")
    run.add_argument("--run-id")
    status = commands.add_parser("status")
    status.add_argument("--run-id")
    report = commands.add_parser("report")
    report.add_argument("--run-id")
    report.add_argument("--output-dir", type=Path)
    export = commands.add_parser("export")
    export.add_argument("--run-id")
    purge = commands.add_parser("purge")
    purge.add_argument("--confirm", action="store_true")
    return root


def execute(args: argparse.Namespace) -> dict[str, Any]:
    repository = SQLiteDebateRepository(args.db)
    debate = PersistentDebate(repository, args.profiles)
    if args.command == "init":
        return debate.initialize(args.run_id)
    run = repository.get_run(getattr(args, "run_id", None))
    if args.command == "run":
        return debate.run(run["run_id"])
    if args.command == "status":
        return run
    if args.command == "export":
        return repository.export(run["run_id"])
    if args.command == "report":
        output = (
            args.output_dir
            or Path("results/experiment-3") / run["run_id"]
        ).resolve()
        root = Path("results/experiment-3").resolve()
        try:
            output.relative_to(root)
        except ValueError as error:
            raise ValueError(
                "output directory must be under results/experiment-3"
            ) from error
        return debate.write_report(run["run_id"], output)
    if args.command == "purge":
        if not args.confirm:
            raise ValueError("purge requires --confirm")
        repository.purge()
        return {"purged": str(args.db)}
    raise ValueError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        print(json.dumps(execute(args), indent=2, sort_keys=True))
        return 0
    except (
        DebateRepositoryError,
        ProfileError,
        ValueError,
        OSError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
