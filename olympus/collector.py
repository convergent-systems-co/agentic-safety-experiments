from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def git_metadata(cwd: str | Path) -> dict[str, Any]:
    path = Path(cwd)

    def git(*args: str) -> str:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "diff.external=",
                "-c",
                "credential.helper=",
                "-C",
                str(path),
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return completed.stdout.strip()

    try:
        root = git("rev-parse", "--show-toplevel")
        status = git("status", "--porcelain")
        return {
            "repo": Path(root).name,
            "branch": git("branch", "--show-current"),
            "head": git("rev-parse", "HEAD"),
            "dirty": bool(status),
            "changed_files": [
                line[3:] for line in status.splitlines() if len(line) >= 4
            ],
        }
    except (OSError, subprocess.SubprocessError):
        return {}
