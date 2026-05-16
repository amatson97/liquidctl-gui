"""Helpers for resolving the non-root user that should own app state."""

from __future__ import annotations

import os
import pwd
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UserContext:
    username: str | None
    home: Path


def resolve_user_context() -> UserContext:
    """Resolve the user whose home/config should be used.

    When the app is launched with sudo, prefer the original invoking user so
    per-user config and systemd --user integration keep working.
    """

    sudo_user = os.environ.get("SUDO_USER")
    if os.geteuid() == 0 and sudo_user:
        try:
            entry = pwd.getpwnam(sudo_user)
        except KeyError:
            pass
        else:
            return UserContext(username=sudo_user, home=Path(entry.pw_dir))

    try:
        entry = pwd.getpwuid(os.geteuid())
        username = entry.pw_name
    except KeyError:
        username = os.environ.get("USER")
    return UserContext(username=username, home=Path.home())