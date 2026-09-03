"""Agent registry: one JSON file per agent under ~/.ai/agents/.

The registry is configuration, never secrets: it names the database, the
experiment, how the human is identified on this channel, and the host command
that voices the agent (with optional named profiles such as ``think-hard``).
A secret reference like ``op://...`` may appear in a host command; the value
is resolved by the host at call time and never stored here.

Keys: ``name`` (lowercase, digits, hyphens), ``db``, ``experiment_id``,
``sender`` {``stable_id``, ``issuer``, ``verifier_version``, ``channel``},
``host`` {``command``: argv list, ``profiles``: {name: argv list}}.
Optional: ``display_name``, the agent's chosen name, which lets chat supply the
vocative when a line omits it; ``repo_root``, an existing directory used as the
host command's working directory, so ``-m experiment4.host`` resolves against
a trusted checkout (prefer absolute script paths in ``command`` regardless).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

AGENT_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
REQUIRED_KEYS = {"name", "db", "experiment_id", "sender", "host"}
SENDER_KEYS = {"stable_id", "issuer", "verifier_version", "channel"}


class RegistryError(RuntimeError):
    pass


def agents_dir() -> Path:
    override = os.environ.get("AI_AGENTS_DIR")
    return Path(override) if override else Path.home() / ".ai" / "agents"


def agent_path(name: str) -> Path:
    if not AGENT_NAME_PATTERN.match(name):
        raise RegistryError("agent name must be lowercase letters, digits, and hyphens")
    return agents_dir() / f"{name}.json"


def validate_agent(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict) or not REQUIRED_KEYS <= set(config):
        raise RegistryError(f"agent config needs keys {sorted(REQUIRED_KEYS)}")
    if not AGENT_NAME_PATTERN.match(str(config["name"])):
        raise RegistryError("agent name must be lowercase letters, digits, and hyphens")
    sender = config["sender"]
    if not isinstance(sender, dict) or not SENDER_KEYS <= set(sender):
        raise RegistryError(f"sender needs keys {sorted(SENDER_KEYS)}")
    host = config["host"]
    if not isinstance(host, dict) or not isinstance(host.get("command"), list) or not host["command"]:
        raise RegistryError("host.command must be a non-empty argv list")
    for profile, command in host.get("profiles", {}).items():
        if not isinstance(command, list) or not command:
            raise RegistryError(f"host profile {profile!r} must be a non-empty argv list")
    if "display_name" in config and not (
        isinstance(config["display_name"], str) and config["display_name"].strip()
    ):
        raise RegistryError("display_name must be a non-empty string when present")
    repo_root = config.get("repo_root")
    if repo_root is not None and not (isinstance(repo_root, str) and Path(repo_root).is_dir()):
        raise RegistryError("repo_root must be an existing directory when present")
    return config


def load_agent(name: str) -> dict[str, Any]:
    path = agent_path(name)
    if not path.exists():
        raise RegistryError(f"no agent named {name!r} under {agents_dir()}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RegistryError(f"agent file unreadable: {path}") from error
    config = validate_agent(config)
    if config["name"] != name:
        raise RegistryError(f"agent file {path} names {config['name']!r}, not {name!r}")
    return config


def save_agent(config: dict[str, Any]) -> Path:
    config = validate_agent(config)
    path = agent_path(str(config["name"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def host_command(config: dict[str, Any], profile: str | None = None) -> list[str]:
    host = config["host"]
    if profile is None:
        return list(host["command"])
    profiles = host.get("profiles", {})
    if profile not in profiles:
        raise RegistryError(f"agent {config['name']!r} has no host profile {profile!r}")
    return list(profiles[profile])


def list_agents() -> list[str]:
    directory = agents_dir()
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))
