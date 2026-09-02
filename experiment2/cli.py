from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from .harness import DEFAULT_MODEL_CONFIG, MoralExperiment
from .repository import MoralRepositoryError, SQLiteMoralRepository


DEFAULT_DB = Path("results/experiment-2/controlled-conversation.db")
MAX_INPUT_BYTES = 64 * 1024


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="olympus-experiment2")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    commands = parser.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser("init")
    initialize.add_argument("--run-id")
    initialize.add_argument("--provider", default=DEFAULT_MODEL_CONFIG["provider"])
    initialize.add_argument("--model", default=DEFAULT_MODEL_CONFIG["model"])
    initialize.add_argument("--temperature", type=float, default=0)

    status = commands.add_parser("status")
    status.add_argument("--run-id")

    record = commands.add_parser("record-turn")
    record.add_argument("--run-id")
    record.add_argument(
        "--input",
        type=Path,
        help="JSON turn envelope; omit to read standard input",
    )

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--run-id")
    finalize.add_argument("--output-dir", type=Path)

    export = commands.add_parser("export")
    export.add_argument("--run-id")
    purge = commands.add_parser("purge")
    purge.add_argument("--confirm", action="store_true")
    invalidate = commands.add_parser("invalidate")
    invalidate.add_argument("--run-id")
    invalidate.add_argument("--reason", required=True)
    return parser


def read_envelope(path: Path | None) -> dict[str, Any]:
    if path:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("turn input exceeds 64 KiB")
        text = path.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read(MAX_INPUT_BYTES + 1)
        if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("turn input exceeds 64 KiB")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("turn input must be a JSON object")
    return value


def execute(args: argparse.Namespace) -> dict[str, Any]:
    harness = MoralExperiment(SQLiteMoralRepository(args.db))
    if args.command == "init":
        result = harness.initialize(
            run_id=args.run_id,
            model_config={
                "provider": args.provider,
                "model": args.model,
                "temperature": args.temperature,
                "tools": [],
            },
        )
        result["initialization_command"] = (
            "python3 -m experiment2 --db "
            + shlex.quote(str(args.db))
            + " init"
        )
        return result
    if args.command == "status":
        return harness.status(args.run_id)
    if args.command == "record-turn":
        return harness.record_turn(read_envelope(args.input), args.run_id)
    if args.command == "finalize":
        run = (
            harness.repository.get_run(args.run_id)
            if args.run_id
            else harness.repository.get_active_run()
        )
        output_root = Path("results/experiment-2").resolve()
        output_dir = (
            args.output_dir or Path("results/experiment-2") / run.run_id
        ).resolve()
        try:
            output_dir.relative_to(output_root)
        except ValueError as error:
            raise ValueError(
                "output directory must be under results/experiment-2"
            ) from error
        return harness.finalize(output_dir=output_dir, run_id=run.run_id)
    if args.command == "export":
        return harness.export(args.run_id)
    if args.command == "purge":
        if not args.confirm:
            raise ValueError("purge requires --confirm")
        harness.repository.purge()
        return {"purged": str(args.db)}
    if args.command == "invalidate":
        run = (
            harness.repository.get_run(args.run_id)
            if args.run_id
            else harness.repository.get_active_run()
        )
        invalid = harness.repository.invalidate_run(run.run_id, args.reason)
        return {
            "run_id": invalid.run_id,
            "status": invalid.status.value,
            "invalid_reason": invalid.invalid_reason,
        }
    raise ValueError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        emit(execute(args))
        return 0
    except (MoralRepositoryError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
