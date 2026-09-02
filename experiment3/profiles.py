from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class AgentProfile:
    code_name: str
    role: str
    position: str
    style: str
    promises: tuple[str, ...]
    text: str
    sha256: str


def load_profile(path: Path) -> AgentProfile:
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        for field in ("Agent-ID", "Role", "Position", "Style"):
            prefix = f"{field}:"
            if line.startswith(prefix):
                fields[field] = line[len(prefix) :].strip()
    missing = [
        field
        for field in ("Agent-ID", "Role", "Position", "Style")
        if not fields.get(field)
    ]
    if missing:
        raise ProfileError(f"{path.name} is missing: {', '.join(missing)}")

    section = text.partition("## Promises")[2].partition("## Persistent Memory")[0]
    promises = tuple(
        line[2:].strip() for line in section.splitlines() if line.startswith("- ")
    )
    if len(promises) != 3:
        raise ProfileError(f"{path.name} must declare exactly three promises")
    return AgentProfile(
        code_name=fields["Agent-ID"],
        role=fields["Role"],
        position=fields["Position"],
        style=fields["Style"],
        promises=promises,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def load_profiles(directory: Path) -> dict[str, AgentProfile]:
    profiles = {
        name: load_profile(directory / f"{name}.md")
        for name in ("jerk", "reliable", "observer")
    }
    for name, profile in profiles.items():
        if profile.code_name != name:
            raise ProfileError(f"{name}.md must declare Agent-ID: {name}")
    if profiles["observer"].role != "moderator":
        raise ProfileError("observer.md must declare Role: moderator")
    if any(profiles[name].role != "debater" for name in ("jerk", "reliable")):
        raise ProfileError("jerk.md and reliable.md must declare Role: debater")
    return profiles
