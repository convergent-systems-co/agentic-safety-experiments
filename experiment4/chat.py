"""One addressed turn with a registered agent's host, safe to cancel.

The address step acquires the agent's exclusive lease. From that moment until
a reply is persisted, every exit path releases the lease as failed: a host
error, a validation error, a timeout, a cancellation, a keyboard interrupt.
A killed process cannot release anything, so the host runs as a child that
can be terminated while this process stays alive to clean up.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from . import registry
from .harness import IdentityApprenticeship, starts_with_name
from .repository import IdentityRepositoryError, SQLiteIdentityRepository

CHAT_LEASE_SECONDS = 900
StatusCallback = Callable[[str], None]


class ChatCancelled(RuntimeError):
    pass


def address_text(agent: dict[str, Any], content: str) -> str:
    """Only a leading vocative wakes the agent. When the registry records the
    agent's chosen name as display_name, supply it if the person left it off;
    what was actually sent is returned so it can be shown. Without a
    display_name the text is sent unchanged."""
    stripped = content.strip()
    name = agent.get("display_name")
    if not name or starts_with_name(str(name), stripped):
        return stripped
    return f"{name}, {stripped}"


HostStderrSink = Callable[[str], None]


def _print_stderr(text: str) -> None:
    print(text, file=sys.stderr, end="")


def run_host_process(
    argv: list[str],
    prompt: dict[str, Any],
    timeout_seconds: int,
    cancel: threading.Event | None = None,
    cwd: str | None = None,
    stderr_sink: HostStderrSink = _print_stderr,
) -> dict[str, Any]:
    """Run a host as a child process; kill it on cancel or timeout.

    Host stderr goes to the sink (this process's stderr by default, the screen
    in the TUI), never into the archive, on every path including cancel.
    """
    process = subprocess.Popen(
        argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=cwd,
    )
    payload = json.dumps(prompt, sort_keys=True)
    result: dict[str, Any] = {}

    def communicate() -> None:
        try:
            result["out"], result["err"] = process.communicate(payload, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            result["out"], result["err"] = process.communicate()
            result["timeout"] = True

    worker = threading.Thread(target=communicate, daemon=True)
    worker.start()
    cancelled = False
    while worker.is_alive():
        worker.join(0.2)
        if cancel is not None and cancel.is_set() and process.poll() is None:
            process.kill()
            worker.join()
            cancelled = True
    if result.get("err"):
        stderr_sink(result["err"])
    if cancelled:
        raise ChatCancelled("turn cancelled; the lease is being released")
    if result.get("timeout"):
        raise IdentityRepositoryError(f"model host exceeded its {timeout_seconds}-second bound")
    if process.returncode != 0:
        raise IdentityRepositoryError(f"model host exited with status {process.returncode}")
    try:
        envelope = json.loads(result.get("out") or "")
    except json.JSONDecodeError as error:
        raise IdentityRepositoryError("model host did not print a JSON object") from error
    if not isinstance(envelope, dict):
        raise IdentityRepositoryError("model host must print a JSON object")
    return envelope


def run_turn(
    agent: dict[str, Any],
    content: str,
    profile: str | None = None,
    *,
    status: StatusCallback | None = None,
    cancel: threading.Event | None = None,
    stderr_sink: HostStderrSink = _print_stderr,
) -> dict[str, Any]:
    repository = SQLiteIdentityRepository(Path(agent["db"]))
    harness = IdentityApprenticeship(repository)
    sender = agent["sender"]
    sent = address_text(agent, content)
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
        content=sent,
        lease_seconds=CHAT_LEASE_SECONDS,
    )
    if activation["addressing"]["classification"] != "direct":
        return {
            "addressed": False,
            "sent": sent,
            "message_id": activation["message"]["message_id"],
            "note": (
                "recorded but not addressed; start the line with the agent's "
                "chosen name so it wakes"
            ),
        }
    lease_id = activation["lease"]["lease_id"]
    recorded = False
    try:
        if status:
            status(f"{agent.get('display_name') or agent['name']} is thinking")
        envelope = run_host_process(
            registry.host_command(agent, profile), activation, CHAT_LEASE_SECONDS,
            cancel=cancel, cwd=agent.get("repo_root"), stderr_sink=stderr_sink,
        )
        response = harness.record_addressed_response(agent["experiment_id"], envelope)
        recorded = True
    finally:
        if not recorded:
            repository.release_activation_lease(agent["experiment_id"], lease_id, "failed")
    return {
        "addressed": True,
        "sent": sent,
        "answer": envelope["answer"],
        "addressed_response_id": response["addressed_response_id"],
        "orientation_id": activation["orientation"]["orientation_id"],
        "model_config": envelope["model_config"],
        "conversation_action": envelope["conversation_action"]["action"],
    }
