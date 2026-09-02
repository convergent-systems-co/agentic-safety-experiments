from __future__ import annotations

import re
from typing import Any

from .privacy import (
    redact_command,
    sanitize_interaction_text,
    sanitize_metadata_text,
)


class EventPolicyError(ValueError):
    pass


_SCHEMAS = {
    ("shell", "command_start"): {
        "required": {"command"},
        "optional": {"git"},
    },
    ("shell", "command_end"): {
        "required": {"command", "exit_code", "duration_ms"},
        "optional": {"git"},
    },
    ("git", "state"): {
        "required": {"head", "dirty", "changed_files"},
        "optional": set(),
    },
    ("observer_interaction", "user_question"): {
        "required": {"text", "mode"},
        "optional": set(),
    },
    ("observer_interaction", "user_correction"): {
        "required": {"text"},
        "optional": set(),
    },
    ("observer_interaction", "user_preference_statement"): {
        "required": {"preference_digest"},
        "optional": set(),
    },
    ("observer_interaction", "operator_preference"): {
        "required": {"preference_digest"},
        "optional": set(),
    },
    ("observer_interaction", "observer_answer"): {
        "required": {"text", "mode", "context_build_id"},
        "optional": set(),
    },
}


def sanitize_event_payload(
    source: str, event_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    schema = _SCHEMAS.get((source, event_type))
    if schema is None:
        raise EventPolicyError(
            f"unsupported event source/type: {source}.{event_type}"
        )
    fields = set(payload)
    missing = schema["required"] - fields
    unexpected = fields - schema["required"] - schema["optional"]
    if missing:
        raise EventPolicyError(
            "missing event payload fields: " + ", ".join(sorted(missing))
        )
    if unexpected:
        raise EventPolicyError(
            "unsupported event payload fields: "
            + ", ".join(sorted(unexpected))
        )
    safe = dict(payload)
    if source == "shell":
        if not isinstance(safe["command"], str) or not safe["command"].strip():
            raise EventPolicyError("shell command must be a non-empty string")
        safe["command"] = redact_command(safe["command"])
        if event_type == "command_end":
            if not isinstance(safe["exit_code"], int):
                raise EventPolicyError("exit_code must be an integer")
            if (
                not isinstance(safe["duration_ms"], int)
                or safe["duration_ms"] < 0
            ):
                raise EventPolicyError(
                    "duration_ms must be a non-negative integer"
                )
        if "git" in safe:
            _validate_git(safe["git"])
    elif source == "git":
        _validate_git(safe)
    else:
        if event_type in {
            "user_preference_statement",
            "operator_preference",
        }:
            digest = safe["preference_digest"]
            if not isinstance(digest, str) or not re.fullmatch(
                r"[0-9a-f]{64}", digest
            ):
                raise EventPolicyError(
                    "preference_digest must be a SHA-256 hex digest"
                )
            return safe
        if not isinstance(safe["text"], str):
            raise EventPolicyError("interaction text must be a string")
        safe["text"] = sanitize_interaction_text(safe["text"])
        if "mode" in safe and str(safe["mode"]) not in {
            "PERSISTENT",
            "MEMORY_ONLY",
            "Mode.PERSISTENT",
            "Mode.MEMORY_ONLY",
        }:
            raise EventPolicyError("invalid persistence mode")
        if "context_build_id" in safe and not isinstance(
            safe["context_build_id"], str
        ):
            raise EventPolicyError("context_build_id must be a string")
    return safe


def _validate_git(value: Any) -> None:
    if not isinstance(value, dict):
        raise EventPolicyError("git metadata must be an object")
    required = {"head", "dirty", "changed_files"}
    allowed = required | {"repo", "branch"}
    if required - set(value) or set(value) - allowed:
        raise EventPolicyError("git metadata has invalid fields")
    if not isinstance(value["head"], str) or not value["head"]:
        raise EventPolicyError("git head must be a non-empty string")
    if not isinstance(value["dirty"], bool):
        raise EventPolicyError("git dirty must be a boolean")
    if not isinstance(value["changed_files"], list) or not all(
        isinstance(item, str) for item in value["changed_files"]
    ):
        raise EventPolicyError("changed_files must be a string list")
    value["changed_files"] = [
        sanitize_metadata_text(item) for item in value["changed_files"]
    ]
    value["head"] = sanitize_metadata_text(value["head"])
    for optional in ("repo", "branch"):
        if optional in value and not isinstance(value[optional], str):
            raise EventPolicyError(f"git {optional} must be a string")
        if optional in value:
            value[optional] = sanitize_metadata_text(value[optional])
