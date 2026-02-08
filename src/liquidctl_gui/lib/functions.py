"""Core helpers for liquidctl-gui."""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

from .liquidctl_api import LiquidctlAPI, LIQUIDCTL_AVAILABLE, SIMULATION_MODE


@dataclass
class DeviceInfo:
    name: str
    match: str
    device_type: str = "generic"
    color_channels: List[str] = field(default_factory=list)
    speed_channels: List[str] = field(default_factory=list)
    color_modes: List[str] = field(default_factory=list)
    supports_lighting: bool = False
    supports_cooling: bool = False


class LiquidctlCore:
    """Core interface for liquidctl - uses Python API when available, CLI as fallback."""

    def __init__(self, liquidctl_path=None, prefer_api=True):
        self.liquidctl_path = liquidctl_path or self._resolve_liquidctl_path()
        # Use API if liquidctl is available OR if simulation mode is enabled
        self.prefer_api = prefer_api and (LIQUIDCTL_AVAILABLE or SIMULATION_MODE)
        self._api = LiquidctlAPI() if self.prefer_api else None
        self._logger = logging.getLogger(__name__)

    @property
    def is_available(self):
        """Check if liquidctl is available (API, simulation, or CLI)."""
        return self.prefer_api or self.liquidctl_path is not None

    @property
    def using_api(self):
        """Check if using Python API (vs CLI)."""
        return self.prefer_api and self._api is not None

    def _resolve_liquidctl_path(self):
        env_path = os.environ.get("LIQUIDCTL_BIN")
        if env_path and Path(env_path).is_file():
            return env_path

        which_path = shutil.which("liquidctl")
        if which_path:
            return which_path

        candidates = [
            Path.home() / ".local/bin/liquidctl",
            Path.home() / ".local/pipx/venvs/liquidctl/bin/liquidctl",
            Path("/usr/local/bin/liquidctl"),
            Path("/usr/bin/liquidctl"),
        ]
        for path in candidates:
            if path.is_file():
                return str(path)

        return None

    def _liquidctl_cmd(self):
        return self.liquidctl_path or "liquidctl"

    # -------------------------------------------------------------------------
    # Device discovery
    # -------------------------------------------------------------------------

    def find_devices(self) -> List[DeviceInfo]:
        """Find all devices and return DeviceInfo list with capabilities."""
        if self.using_api:
            return self._find_devices_api()
        return self._find_devices_cli()

    def _find_devices_api(self) -> List[DeviceInfo]:
        """Find devices using Python API."""
        devices = []
        for caps in self._api.find_devices():
            device = DeviceInfo(
                name=caps.name,
                match=caps.description,
                device_type=caps.driver_class.lower(),
                color_channels=caps.color_channels,
                speed_channels=caps.speed_channels,
                color_modes=caps.color_modes,
                supports_lighting=caps.supports_lighting,
                supports_cooling=caps.supports_cooling,
            )
            devices.append(device)
        return devices

    def _find_devices_cli(self) -> List[DeviceInfo]:
        """Find devices using CLI (limited capability info)."""
        stdout, stderr = self.run_command(self.build_list_cmd())
        if stderr:
            self._logger.warning("CLI list error: %s", stderr)
        device_names = self.parse_list_output(stdout)
        return [DeviceInfo(name=name, match=name) for name in device_names]

    # -------------------------------------------------------------------------
    # Device operations
    # -------------------------------------------------------------------------

    def initialize(self, device_match: str) -> tuple:
        """Initialize device. Returns (result_text, error_string)."""
        if self.using_api:
            result, err = self._api.initialize(device_match)
            return self._api.format_status(result), err
        stdout, stderr = self.run_command(self.build_init_cmd(device_match))
        return stdout, stderr

    def get_status(self, device_match: str) -> tuple:
        """Get device status. Returns (status_text, error_string)."""
        if self.using_api:
            result, err = self._api.get_status(device_match)
            return self._api.format_status(result), err
        stdout, stderr = self.run_command(self.build_status_cmd(device_match))
        return stdout, stderr

    def set_color(self, device_match: str, channel: str, mode: str, color_hex: str, speed: str = 'normal') -> tuple:
        """Set LED color/mode. Returns (success, error_string)."""
        if self.using_api:
            # Convert hex color to RGB tuple
            colors = [self._hex_to_rgb(color_hex)] if color_hex else []
            success, err = self._api.set_color(device_match, channel, mode, colors, speed)
            return success, err
        # CLI fallback
        if mode == "fixed":
            cmd = self.build_set_color_cmd(device_match, channel, color_hex)
        elif color_hex:
            cmd = self.build_set_mode_cmd(device_match, channel, mode, color_hex)
        else:
            cmd = self.build_set_mode_cmd(device_match, channel, mode)
        stdout, stderr = self.run_command(cmd)
        return not stderr, stderr

    def set_speed(self, device_match: str, channel: str, speed) -> tuple:
        """Set fan/pump speed. `speed` may be int or numeric string. Returns (success, error_string)."""
        try:
            speed_int = int(speed)
        except (TypeError, ValueError):
            self._logger.warning("Invalid speed value passed: %r", speed)
            return False, f"Invalid speed value: {speed}"

        if self.using_api:
            return self._api.set_speed(device_match, channel, speed_int)
        stdout, stderr = self.run_command(self.build_set_speed_cmd(device_match, channel, speed_int))
        return not stderr, stderr

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        """Convert '#rrggbb' to (r, g, b) tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    # -------------------------------------------------------------------------
    # CLI command builders (kept for fallback)
    # -------------------------------------------------------------------------

    def build_list_cmd(self):
        return [self._liquidctl_cmd(), "list"]

    def build_init_cmd(self, device_match):
        return ["sudo", self._liquidctl_cmd(), "--match", device_match, "initialize"]

    def build_status_cmd(self, device_match):
        return ["sudo", self._liquidctl_cmd(), "--match", device_match, "status"]

    def build_set_color_cmd(self, device_match, channel, color_hex):
        return ["sudo", self._liquidctl_cmd(), "--match", device_match, "set", channel, "color", "fixed", color_hex]

    def build_set_mode_cmd(self, device_match, channel, mode, color_hex=None):
        cmd = ["sudo", self._liquidctl_cmd(), "--match", device_match, "set", channel, "color", mode]
        if color_hex:
            cmd.append(color_hex)
        return cmd

    def build_set_speed_cmd(self, device_match, channel, speed):
        return ["sudo", self._liquidctl_cmd(), "--match", device_match, "set", channel, "speed", str(speed)]

    @staticmethod
    def parse_list_output(output):
        devices = []
        for line in output.splitlines():
            match = re.match(r"Device #\d+:\s+(.+)", line.strip())
            if match:
                devices.append(match.group(1).strip())
        return devices

    @staticmethod
    def friendly_error(stderr):
        if not stderr:
            return ""
        lowered = stderr.lower()
        if "sudo" in lowered and "password" in lowered:
            return "Sudo password required. Please run again or pre-authenticate with sudo in a terminal."
        if "permission denied" in lowered:
            return "Permission denied. Try running the app with sufficient privileges."
        return stderr.strip()

    @staticmethod
    def run_command(cmd):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.stdout.strip(), result.stderr.strip()
        except Exception as e:
            logging.exception("Command failed: %s", cmd)
            return "", str(e)
