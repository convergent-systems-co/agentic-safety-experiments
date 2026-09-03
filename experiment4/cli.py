from __future__ import annotations

import argparse
import json
import shlex
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from . import benchmark_host, registry
from .harness import DEFAULT_MODEL_CONFIG, IdentityApprenticeship
from .repository import (
    KNOWLEDGE_GRAPH_DEFAULT_BYTES,
    IdentityRepositoryError,
    SQLiteIdentityRepository,
)


DEFAULT_DB = Path("results/experiment-4/apprenticeship.db")
MAX_INPUT_BYTES = 128 * 1024


def run_host_command(
    argv: list[str], prompt: dict[str, Any], timeout_seconds: int
) -> dict[str, Any]:
    """Run a model host with a prompt on stdin and read its envelope.

    Host stderr goes to this process's stderr, never into the archive: a
    failure records only that the host failed and how, not what it said.
    """
    if not argv:
        raise ValueError("model command must not be empty")
    try:
        completed = subprocess.run(
            argv,
            input=json.dumps(prompt, sort_keys=True),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise IdentityRepositoryError(
            f"model command exceeded its {timeout_seconds}-second runtime bound"
        ) from error
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    if completed.returncode != 0:
        raise IdentityRepositoryError(
            f"model command exited with status {completed.returncode}"
        )
    try:
        outcome = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise IdentityRepositoryError(
            "model command did not print a JSON object"
        ) from error
    if not isinstance(outcome, dict):
        raise IdentityRepositoryError("model command must print a JSON object")
    return outcome


def subprocess_model_runner(command: str):
    """Wake-executor runner: the host is bounded by the same clipped runtime
    as the execution lease, so a hung host cannot outlive its fence."""
    argv = shlex.split(command)
    if not argv:
        raise ValueError("model command must not be empty")

    def run(prompt: dict[str, Any]) -> dict[str, Any]:
        return run_host_command(
            argv, prompt, SQLiteIdentityRepository.wake_runtime_seconds(prompt["wake_intent"])
        )

    return run


CHAT_LEASE_SECONDS = 900


def chat_turn(
    agent: dict[str, Any], content: str, profile: str | None = None
) -> dict[str, Any]:
    """One addressed turn through the agent's registered host.

    Any failure after activation releases the lease as failed, so a broken
    host never leaves the agent unreachable.
    """
    repository = SQLiteIdentityRepository(Path(agent["db"]))
    harness = IdentityApprenticeship(repository)
    sender = agent["sender"]
    activation = harness.address_chat_message(
        agent["experiment_id"],
        sender_stable_id=sender["stable_id"],
        sender_assertion={
            "issuer": sender["issuer"],
            "authenticated": True,
            "external_event_id": f"agent-chat-{uuid.uuid4()}",
            "verifier_version": sender["verifier_version"],
        },
        channel=sender["channel"],
        content=content,
        lease_seconds=CHAT_LEASE_SECONDS,
    )
    if activation["addressing"]["classification"] != "direct":
        return {
            "addressed": False,
            "message_id": activation["message"]["message_id"],
            "note": f"recorded but not addressed; start with the agent's name, {agent['name']}",
        }
    try:
        envelope = run_host_command(
            registry.host_command(agent, profile), activation, CHAT_LEASE_SECONDS
        )
        response = harness.record_addressed_response(agent["experiment_id"], envelope)
    except Exception:
        repository.release_activation_lease(
            agent["experiment_id"], activation["lease"]["lease_id"], "failed"
        )
        raise
    return {
        "addressed": True,
        "answer": envelope["answer"],
        "addressed_response_id": response["addressed_response_id"],
        "orientation_id": activation["orientation"]["orientation_id"],
        "model_config": envelope["model_config"],
        "conversation_action": envelope["conversation_action"]["action"],
    }


def read_object(path: Path | None) -> dict[str, Any]:
    if path:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("input exceeds 128 KiB")
        text = path.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read(MAX_INPUT_BYTES + 1)
        if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("input exceeds 128 KiB")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="olympus-experiment4")
    root.add_argument("--db", type=Path, default=DEFAULT_DB)
    commands = root.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser("init")
    initialize.add_argument("--experiment-id")
    initialize.add_argument("--provider", default=DEFAULT_MODEL_CONFIG["provider"])
    initialize.add_argument("--model", default=DEFAULT_MODEL_CONFIG["model"])

    for name in ("genesis-prompt", "wake", "inspect", "invitation-prompt"):
        command = commands.add_parser(name)
        command.add_argument("--experiment-id")

    for name in (
        "adopt-identity",
        "revise-identity",
        "record-experience",
        "record-relationship-event",
        "record-relationship-assessment",
        "record-principle",
        "revise-principle",
        "resolve-commitment",
        "propose-decision",
        "resolve-decision",
        "reflect",
        "record-answer",
        "record-invitation-response",
        "record-commitment",
        "record-decision-outcome",
        "record-wake-intent",
        "record-addressed-response",
    ):
        command = commands.add_parser(name)
        command.add_argument("--experiment-id")
        command.add_argument("--input", type=Path)
    commands.choices["revise-principle"].add_argument("--parent-id", required=True)
    commands.choices["record-answer"].add_argument("--question", required=True)

    relationship = commands.add_parser("add-relationship")
    relationship.add_argument("--experiment-id")
    relationship.add_argument("--other-stable-id", required=True)
    relationship.add_argument("--label", required=True)

    interrogation = commands.add_parser("interrogation-prompt")
    interrogation.add_argument("--experiment-id")
    interrogation.add_argument("--question", required=True)

    export = commands.add_parser("export")
    export.add_argument("--experiment-id")
    export.add_argument("--confirm-sensitive", action="store_true")

    retrieve = commands.add_parser("retrieve-knowledge")
    retrieve.add_argument("--experiment-id")
    retrieve.add_argument("--query", required=True)
    retrieve.add_argument("--max-nodes", type=int, default=20)
    retrieve.add_argument("--max-edges", type=int, default=40)
    retrieve.add_argument("--max-hops", type=int, default=2)
    retrieve.add_argument(
        "--max-bytes", type=int, default=KNOWLEDGE_GRAPH_DEFAULT_BYTES
    )
    retrieve.add_argument("--confirm-sensitive", action="store_true")

    benchmark = commands.add_parser("benchmark-retrieval")
    benchmark.add_argument("--experiment-id")
    benchmark.add_argument("--input", type=Path)
    benchmark.add_argument("--confirm-sensitive", action="store_true")

    rebuild = commands.add_parser("rebuild-knowledge-graph")
    rebuild.add_argument("--experiment-id")

    cancel_wake = commands.add_parser("cancel-wake-intent")
    cancel_wake.add_argument("--experiment-id")
    cancel_wake.add_argument("--wake-intent-id", required=True)
    cancel_wake.add_argument("--reason", required=True)
    cancel_wake.add_argument(
        "--author-type",
        choices=("operator", "system"),
        default="operator",
    )
    cancel_wake.add_argument(
        "--epistemic-status",
        choices=("observed", "reported", "authored"),
        default="authored",
    )
    cancel_wake.add_argument(
        "--input",
        type=Path,
        help="authorship JSON; required for a model cancelling its own intent",
    )

    due_wake = commands.add_parser("due-wake-intents")
    due_wake.add_argument("--experiment-id")

    wake_prompt = commands.add_parser("wake-intent-prompt")
    wake_prompt.add_argument("--experiment-id")
    wake_prompt.add_argument("--wake-intent-id", required=True)

    wake_outcome = commands.add_parser("record-wake-outcome")
    wake_outcome.add_argument("--experiment-id")
    wake_outcome.add_argument("--input", type=Path)

    execute_wake = commands.add_parser("execute-wake-intents")
    execute_wake.add_argument("--experiment-id")
    execute_wake.add_argument(
        "--model-command",
        help="command that reads the wake prompt on stdin and prints an outcome",
    )

    chat = commands.add_parser("chat", help="talk to a registered agent by name")
    chat.add_argument("--agent", required=True)
    chat.add_argument("--message", help="one message; omit to read lines from stdin")
    chat.add_argument("--profile", help="named host profile from the registry, e.g. think-hard")
    chat.add_argument("--plain", action="store_true", help="print only the agent's answer")

    agents = commands.add_parser("agents", help="list registered agents")

    benchmark_hosts = commands.add_parser("benchmark-host")
    benchmark_hosts.add_argument("--experiment-id")
    benchmark_hosts.add_argument("--host-command", required=True)
    benchmark_hosts.add_argument("--limit", type=int, default=10)
    benchmark_hosts.add_argument("--output", type=Path, help="write the JSON report here")
    benchmark_hosts.add_argument("--markdown", type=Path, help="write a side-by-side Markdown report here")

    address = commands.add_parser("address-message")
    address.add_argument("--experiment-id")
    address.add_argument("--sender-stable-id", required=True)
    address.add_argument("--assertion-issuer", required=True)
    address.add_argument("--external-event-id", required=True)
    address.add_argument("--verifier-version", required=True)
    address.add_argument("--sender-authenticated", action="store_true")
    address.add_argument("--channel", required=True)
    address.add_argument("--content", required=True)
    address.add_argument("--lease-seconds", type=int, default=300)

    release_activation = commands.add_parser("release-activation")
    release_activation.add_argument("--experiment-id")
    release_activation.add_argument("--lease-id", required=True)
    release_activation.add_argument(
        "--reason", required=True, choices=("cancelled", "failed")
    )

    purge = commands.add_parser("purge")
    purge.add_argument("--confirm", action="store_true")
    return root


def execute(args: argparse.Namespace) -> dict[str, Any]:
    # Registry-driven commands name their own database and must not touch
    # the default one.
    if args.command == "agents":
        return {"agents": registry.list_agents()}
    if args.command == "chat":
        agent = registry.load_agent(args.agent)
        if args.message is not None:
            return chat_turn(agent, args.message, args.profile)
        turns = []
        for line in sys.stdin:
            content = line.strip()
            if not content:
                continue
            result = chat_turn(agent, content, args.profile)
            turns.append(result)
            print(result.get("answer") or result.get("note"), flush=True)
        return {"turns": turns}
    repository = SQLiteIdentityRepository(args.db)
    harness = IdentityApprenticeship(repository)
    if args.command == "init":
        return harness.initialize(
            experiment_id=args.experiment_id,
            model_config={
                "provider": args.provider,
                "model": args.model,
                "tools": [],
            },
        )
    experiment = repository.experiment(getattr(args, "experiment_id", None))
    experiment_id = experiment["experiment_id"]
    if args.command == "genesis-prompt":
        return harness.genesis_prompt(experiment_id)
    if args.command == "adopt-identity":
        return harness.adopt_identity(experiment_id, read_object(args.input))
    if args.command == "revise-identity":
        return repository.revise_identity(experiment_id, read_object(args.input))
    if args.command == "wake":
        return harness.wake(experiment_id)
    if args.command == "record-experience":
        return repository.append_experience(experiment_id, read_object(args.input))
    if args.command == "add-relationship":
        return repository.add_relationship(
            experiment_id, args.other_stable_id, args.label
        )
    if args.command == "record-relationship-event":
        return repository.append_relationship_event(
            experiment_id, read_object(args.input)
        )
    if args.command == "record-relationship-assessment":
        return repository.append_relationship_assessment(
            experiment_id, read_object(args.input)
        )
    if args.command == "record-principle":
        return repository.append_principle(
            experiment_id, read_object(args.input)
        )
    if args.command == "revise-principle":
        return repository.append_principle(
            experiment_id, read_object(args.input), args.parent_id
        )
    if args.command == "record-commitment":
        return repository.append_commitment(
            experiment_id, read_object(args.input)
        )
    if args.command == "resolve-commitment":
        return repository.resolve_commitment(
            experiment_id, read_object(args.input)
        )
    if args.command == "propose-decision":
        return repository.propose_decision(
            experiment_id, read_object(args.input)
        )
    if args.command == "resolve-decision":
        return repository.resolve_decision(
            experiment_id, read_object(args.input)
        )
    if args.command == "record-decision-outcome":
        return repository.record_decision_outcome(
            experiment_id, read_object(args.input)
        )
    if args.command == "record-wake-intent":
        return repository.append_wake_intent(
            experiment_id, read_object(args.input)
        )
    if args.command == "cancel-wake-intent":
        authorship = (
            read_object(args.input)
            if args.input is not None
            else {
                "author_type": args.author_type,
                "epistemic_status": args.epistemic_status,
            }
        )
        return repository.cancel_wake_intent(
            experiment_id, args.wake_intent_id, args.reason, authorship
        )
    if args.command == "due-wake-intents":
        return {"due": repository.due_wake_intents(experiment_id)}
    if args.command == "wake-intent-prompt":
        return harness.wake_intent_prompt(experiment_id, args.wake_intent_id)
    if args.command == "record-wake-outcome":
        return harness.record_wake_outcome(experiment_id, read_object(args.input))
    if args.command == "benchmark-host":
        argv = shlex.split(args.host_command)
        report = benchmark_host.run_benchmark(
            args.db,
            experiment_id,
            lambda prompt: run_host_command(argv, prompt, CHAT_LEASE_SECONDS),
            limit=args.limit,
        )
        if args.output:
            args.output.write_text(json.dumps(report, indent=2, sort_keys=True))
        if args.markdown:
            args.markdown.write_text(benchmark_host.render_markdown(report))
        return {key: value for key, value in report.items() if key != "results"} | {
            "results": [
                {k: item[k] for k in ("addressed_response_id", "valid", "problems", "seconds", "candidate_chars", "recorded_chars")}
                for item in report["results"]
            ]
        }
    if args.command == "execute-wake-intents":
        runner = (
            subprocess_model_runner(args.model_command)
            if args.model_command
            else None
        )
        return {
            "executions": harness.run_due_wake_intents(
                experiment_id, model_runner=runner
            )
        }
    if args.command == "address-message":
        return harness.address_chat_message(
            experiment_id,
            sender_stable_id=args.sender_stable_id,
            sender_assertion={
                "issuer": args.assertion_issuer,
                "authenticated": args.sender_authenticated,
                "external_event_id": args.external_event_id,
                "verifier_version": args.verifier_version,
            },
            channel=args.channel,
            content=args.content,
            lease_seconds=args.lease_seconds,
        )
    if args.command == "record-addressed-response":
        return harness.record_addressed_response(
            experiment_id, read_object(args.input)
        )
    if args.command == "release-activation":
        return repository.release_activation_lease(
            experiment_id, args.lease_id, args.reason
        )
    if args.command == "reflect":
        return repository.append_reflection(
            experiment_id, read_object(args.input)
        )
    if args.command == "interrogation-prompt":
        return harness.interrogation_prompt(experiment_id, args.question)
    if args.command == "invitation-prompt":
        return harness.invitation_prompt(experiment_id)
    if args.command == "record-answer":
        return harness.record_answer(
            experiment_id, args.question, read_object(args.input)
        )
    if args.command == "record-invitation-response":
        return repository.record_invitation_response(
            experiment_id, read_object(args.input)
        )
    if args.command == "inspect":
        return harness.inspect(experiment_id)
    if args.command == "export":
        if not args.confirm_sensitive:
            raise ValueError("export requires --confirm-sensitive")
        return repository.export(experiment_id)
    if args.command == "retrieve-knowledge":
        if not args.confirm_sensitive:
            raise ValueError(
                "retrieve-knowledge requires --confirm-sensitive"
            )
        return repository.retrieve_knowledge(
            experiment_id,
            args.query,
            max_nodes=args.max_nodes,
            max_edges=args.max_edges,
            max_hops=args.max_hops,
            max_bytes=args.max_bytes,
        )
    if args.command == "benchmark-retrieval":
        if not args.confirm_sensitive:
            raise ValueError(
                "benchmark-retrieval requires --confirm-sensitive"
            )
        payload = read_object(args.input)
        if set(payload) != {"cases"}:
            raise ValueError("benchmark-retrieval input fields are invalid")
        return repository.evaluate_retrieval(
            experiment_id, payload["cases"]
        )
    if args.command == "rebuild-knowledge-graph":
        return repository.rebuild_knowledge_graph(experiment_id)
    if args.command == "purge":
        if not args.confirm:
            raise ValueError("purge requires --confirm")
        repository.purge()
        return {"purged": str(args.db)}
    raise ValueError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = execute(args)
        if args.command == "chat" and getattr(args, "plain", False) and args.message is not None:
            print(result.get("answer") or result.get("note"))
        elif args.command == "chat" and args.message is None:
            pass  # answers were printed as each line was answered
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        IdentityRepositoryError,
        registry.RegistryError,
        ValueError,
        OSError,
        json.JSONDecodeError,
        sqlite3.IntegrityError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
