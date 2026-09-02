from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .domain import Mode
from .experiment import ExperimentRunner
from .observer import Observer
from .privacy import DEFAULT_SOURCES
from .repository import RepositoryError, SQLiteRepository


def default_db_path() -> Path:
    configured = os.environ.get("MNEMOSYNE_DB")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local" / "share" / "olympus" / "mnemosyne.db"


def json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"cannot encode {type(value).__name__}")


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=json_default))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="olympus")
    parser.add_argument("--db", type=Path, default=default_db_path())
    root = parser.add_subparsers(dest="root_command", required=True)
    observer = root.add_parser("observer")
    commands = observer.add_subparsers(dest="observer_command", required=True)

    for name in ("wake", "resume", "status", "reflect", "sleep"):
        commands.add_parser(name)

    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument(
        "--mode",
        choices=("persistent", "memory-only"),
        default="persistent",
    )
    ask.add_argument("--token-budget", type=int, default=2000)

    history = commands.add_parser("history")
    history.add_argument("--since")
    history.add_argument("--limit", type=int)
    history.add_argument("--agent-id")

    for name in (
        "beliefs",
        "commitments",
        "consequences",
        "revisions",
        "incarnations",
        "facts",
        "relationships",
        "runs",
        "privacy",
        "inspect",
    ):
        commands.add_parser(name)

    contexts = commands.add_parser("contexts")
    contexts.add_argument("--run-id")
    contexts.add_argument("--agent-id")
    evaluations = commands.add_parser("evaluations")
    evaluations.add_argument("--run-id")
    evaluations.add_argument("--agent-id")

    forget = commands.add_parser("forget-fact")
    forget.add_argument("user_fact_id")
    forget.add_argument("--confirm", action="store_true")

    correct = commands.add_parser("correct-fact")
    correct.add_argument("user_fact_id")
    correct.add_argument("replacement")
    correct.add_argument("--confirm", action="store_true")

    shell = commands.add_parser("observe-shell")
    shell.add_argument("command")
    shell.add_argument("--event-type", default="command_end")
    shell.add_argument("--cwd", default=os.getcwd())
    shell.add_argument("--exit-code", type=int)
    shell.add_argument("--duration-ms", type=int)
    shell.add_argument("--correlation-id")

    experiment = commands.add_parser("experiment")
    experiment_commands = experiment.add_subparsers(
        dest="experiment_command", required=True
    )
    for name in ("run", "compare"):
        command = experiment_commands.add_parser(name)
        command.add_argument("scenario", type=Path)

    purge = commands.add_parser("purge")
    purge.add_argument("--confirm", action="store_true")
    commands.add_parser("compact")
    return parser


def parse_since(value: str | None) -> str | None:
    if value is None:
        return None
    if value.endswith("h") and value[:-1].isdigit():
        return (
            datetime.now(timezone.utc) - timedelta(hours=int(value[:-1]))
        ).isoformat()
    if value.endswith("m") and value[:-1].isdigit():
        return (
            datetime.now(timezone.utc) - timedelta(minutes=int(value[:-1]))
        ).isoformat()
    return value


def execute(args: argparse.Namespace) -> Any:
    repository = SQLiteRepository(args.db)
    observer = Observer(repository)
    command = args.observer_command
    if command == "wake":
        return observer.wake()
    if command == "resume":
        return observer.resume()
    if command == "status":
        return observer.status()
    if command == "reflect":
        return observer.reflect()
    if command == "sleep":
        return observer.sleep()
    if command == "ask":
        return observer.ask(
            args.question,
            mode=Mode.parse(args.mode),
            token_budget=args.token_budget,
        )
    if command == "history":
        return [
            asdict(event)
            for event in repository.get_events(
                agent_id=args.agent_id or observer.agent.agent_id,
                since=parse_since(args.since),
                limit=args.limit,
            )
        ]
    if command == "beliefs":
        return [
            asdict(item)
            for item in repository.get_belief_history(observer.agent.agent_id)
        ]
    if command == "commitments":
        return [
            asdict(item)
            for item in repository.get_commitments(observer.agent.agent_id)
        ]
    if command == "consequences":
        return [
            asdict(item)
            for item in repository.get_consequences(observer.agent.agent_id)
        ]
    if command == "revisions":
        return [
            asdict(item)
            for item in repository.get_revisions(observer.agent.agent_id)
        ]
    if command == "incarnations":
        return [
            asdict(item)
            for item in repository.list_incarnations(observer.agent.agent_id)
        ]
    if command == "facts":
        return [
            asdict(item)
            for item in repository.get_user_fact_history(observer.agent.agent_id)
        ]
    if command == "relationships":
        return [
            asdict(item)
            for item in repository.get_relationships(observer.agent.agent_id)
        ]
    if command == "contexts":
        return [
            asdict(item)
            for item in repository.get_context_builds(
                agent_id=args.agent_id,
                run_id=args.run_id,
            )
        ]
    if command == "evaluations":
        return [
            asdict(item)
            for item in repository.get_evaluations(
                agent_id=args.agent_id,
                run_id=args.run_id,
            )
        ]
    if command == "runs":
        return [asdict(item) for item in repository.get_experiment_runs()]
    if command == "forget-fact":
        if not args.confirm:
            raise ValueError("forget-fact requires --confirm")
        repository.delete_user_fact(
            args.user_fact_id, agent_id=observer.agent.agent_id
        )
        return {"deleted": args.user_fact_id}
    if command == "correct-fact":
        if not args.confirm:
            raise ValueError("correct-fact requires --confirm")
        return asdict(
            observer.record_preference(
                args.replacement,
                supersedes_user_fact_id=args.user_fact_id,
            )
        )
    if command == "privacy":
        return DEFAULT_SOURCES
    if command == "inspect":
        return observer.inspect()
    if command == "observe-shell":
        payload = {"command": args.command}
        if args.exit_code is not None:
            payload["exit_code"] = args.exit_code
        if args.duration_ms is not None:
            payload["duration_ms"] = args.duration_ms
        return asdict(
            observer.ingest_event(
                source="shell",
                event_type=args.event_type,
                payload=payload,
                cwd=args.cwd,
                correlation_id=args.correlation_id,
            )
        )
    if command == "experiment":
        scenario = ExperimentRunner.load(args.scenario)
        modes = (
            (Mode.PERSISTENT, Mode.MEMORY_ONLY)
            if args.experiment_command == "compare"
            else (Mode.PERSISTENT,)
        )
        return ExperimentRunner(repository).run(scenario, modes)
    if command == "purge":
        if not args.confirm:
            raise ValueError("purge requires --confirm")
        repository.purge()
        return {"purged": str(args.db)}
    if command == "compact":
        repository.compact()
        return {"compacted": str(args.db)}
    raise ValueError(f"unsupported command: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        emit(execute(args))
        return 0
    except (RepositoryError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
