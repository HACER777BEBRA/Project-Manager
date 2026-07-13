from __future__ import annotations

import json
import subprocess
from typing import Optional


def resolve_github_token(explicit: str) -> str:
    if explicit and explicit not in {"", "YOUR_GITHUB_TOKEN"}:
        return explicit

    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        token = (result.stdout or "").strip()
        if result.returncode == 0 and token:
            return token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return ""


def run_git(args: list[str], cwd: Optional[str] = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout
