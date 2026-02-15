"""User startup integration via systemd --user."""

from __future__ import annotations

import subprocess
from pathlib import Path
import sys

SERVICE_NAME = "liquidctl-gui.service"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / SERVICE_NAME


def _render_unit(exec_path: str, workdir: str) -> str:
    return "\n".join(
        [
            "[Unit]",
            "Description=Liquidctl GUI (Apply Profile)",
            "",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={workdir}",
            "Environment=PYTHONPATH=src",
            f"ExecStart={exec_path} -m liquidctl_gui.headless",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )


def _run_systemctl(args: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return 127, "systemctl not found"
    output = (result.stderr or result.stdout or "").strip()
    return result.returncode, output


def _write_unit() -> tuple[bool, str | None]:
    unit_path = _unit_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    exec_path = sys.executable
    workdir = str(_repo_root())
    unit_path.write_text(_render_unit(exec_path, workdir))
    return True, None


def get_startup_enabled() -> tuple[bool, str | None]:
    code, output = _run_systemctl(["is-enabled", SERVICE_NAME])
    if code == 0:
        return output in {"enabled", "enabled-runtime", "static"}, None
    if output in {"disabled", "static", "indirect", "not-found", "masked"}:
        return False, None
    if not output:
        output = "Unknown systemctl error"
    return False, output


def enable_startup() -> tuple[bool, str | None]:
    ok, err = _write_unit()
    if not ok:
        return False, err
    code, output = _run_systemctl(["daemon-reload"])
    if code != 0:
        return False, output or "Failed to reload user systemd"
    code, output = _run_systemctl(["enable", SERVICE_NAME])
    if code != 0:
        return False, output or "Failed to enable user service"
    return True, None


def disable_startup() -> tuple[bool, str | None]:
    code, output = _run_systemctl(["disable", SERVICE_NAME])
    if code != 0 and output not in {"disabled", "not-found"}:
        return False, output or "Failed to disable user service"
    return True, None
