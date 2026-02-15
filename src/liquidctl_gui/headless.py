"""Headless profile apply entrypoint for startup service."""

from __future__ import annotations

import logging
import os
from typing import Dict, Tuple

from .lib.config import load_config, load_current_state
from .lib.functions import LiquidctlCore


DEFAULT_CONFIG = {
    "auto_initialize_on_startup": True,
    "log_level": "INFO",
}


def _resolve_log_level(config: Dict) -> int:
    env_level = os.environ.get("LIQUIDCTL_GUI_LOG_LEVEL", "").strip()
    configured_level = str(config.get("log_level", "INFO")).strip()
    level_name = (env_level or configured_level).upper()
    return logging._nameToLevel.get(level_name, logging.INFO)


class HeadlessApplier:
    def __init__(self, core: LiquidctlCore):
        self.core = core
        self._logger = logging.getLogger(__name__)
        self.last_colors: Dict[str, str] = {}
        self.last_modes: Dict[str, str] = {}
        self.last_speeds: Dict[str, str] = {}
        self.global_sync_modes = {
            "spectrum-wave", "color-cycle", "rainbow-flow", "super-rainbow",
            "rainbow-pulse", "covering-marquee", "marquee-3", "marquee-4",
            "marquee-5", "marquee-6", "moving-alternating-3", "moving-alternating-4",
            "moving-alternating-5", "alternating-3", "alternating-4", "alternating-5",
        }
        self.modes_without_color = {
            "spectrum-wave", "color-cycle", "off", "marquee-3", "marquee-4",
            "marquee-5", "marquee-6", "covering-marquee", "alternating-3",
            "alternating-4", "alternating-5", "moving-alternating-3",
            "moving-alternating-4", "moving-alternating-5", "rainbow-flow",
            "super-rainbow", "rainbow-pulse",
        }

    def _set_led_color(self, device_match: str, channel: str, color_hex: str) -> Tuple[bool, str]:
        success, err = self.core.set_color(device_match, channel, "fixed", color_hex)
        return bool(success), err

    def _set_led_mode(self, device_match: str, channel: str, mode: str) -> Tuple[bool, str]:
        success, err = self.core.set_color(device_match, channel, mode, "")
        return bool(success), err

    def _set_led_mode_with_color(self, device_match: str, channel: str, mode: str, color_hex: str) -> Tuple[bool, str]:
        success, err = self.core.set_color(device_match, channel, mode, color_hex)
        return bool(success), err

    def _set_speed(self, device_match: str, channel: str, speed) -> Tuple[bool, str]:
        success, err = self.core.set_speed(device_match, channel, speed)
        return bool(success), err

    def apply_profile_data(self, data: Dict) -> None:
        self.last_colors = data.get("colors", {}).copy()
        self.last_modes = data.get("modes", {}).copy()
        self.last_speeds = data.get("speeds", {}).copy()

        devices_with_global_sync = set()
        sync_modes = {}
        regular_modes = {}

        for key, mode in self.last_modes.items():
            device, channel = key.split(":", 1)
            if channel == "sync":
                sync_modes[key] = mode
                if mode in self.global_sync_modes:
                    devices_with_global_sync.add(device)
                    self._logger.info(
                        "Device %s has global sync mode: %s (will skip individual LEDs)",
                        device,
                        mode,
                    )
            else:
                regular_modes[key] = mode

        for key, mode in sync_modes.items():
            device, channel = key.split(":", 1)
            color_hex = self.last_colors.get(key, "")

            try:
                if mode in self.modes_without_color or not color_hex:
                    success, err = self._set_led_mode(device, channel, mode)
                else:
                    success, err = self._set_led_mode_with_color(device, channel, mode, color_hex)
                if err and "not found" in err.lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                    continue
                if not success:
                    self._logger.warning("Failed to apply sync mode %s for %s: %s", mode, key, err)
            except Exception as exc:
                if "not found" in str(exc).lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                else:
                    self._logger.warning("Failed to apply sync mode %s for %s: %s", mode, key, exc)

        for key, mode in regular_modes.items():
            device, channel = key.split(":", 1)
            if device in devices_with_global_sync:
                self._logger.debug("Skipping individual LED %s (device has global sync effect)", key)
                continue
            color_hex = self.last_colors.get(key, "")

            try:
                if mode in self.modes_without_color or not color_hex:
                    success, err = self._set_led_mode(device, channel, mode)
                else:
                    success, err = self._set_led_mode_with_color(device, channel, mode, color_hex)
                if err and "not found" in err.lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                    continue
                if not success:
                    self._logger.warning("Failed to apply mode %s for %s: %s", mode, key, err)
            except Exception as exc:
                if "not found" in str(exc).lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                else:
                    self._logger.warning("Failed to apply mode %s for %s: %s", mode, key, exc)

        for key, color_hex in self.last_colors.items():
            if not color_hex or key in self.last_modes:
                continue
            device, channel = key.split(":", 1)
            if device in devices_with_global_sync:
                self._logger.debug("Skipping color-only LED %s (device has global sync effect)", key)
                continue
            try:
                success, err = self._set_led_color(device, channel, color_hex)
                if err and "not found" in err.lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                    continue
                if not success:
                    self._logger.warning("Failed to apply color %s for %s: %s", color_hex, key, err)
            except Exception as exc:
                if "not found" in str(exc).lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                else:
                    self._logger.warning("Failed to apply color %s for %s: %s", color_hex, key, exc)

        for key, speed in self.last_speeds.items():
            device, channel = key.split(":", 1)
            try:
                success, err = self._set_speed(device, channel, speed)
                if err and "not found" in err.lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                    continue
                if not success:
                    self._logger.warning("Failed to apply speed %s for %s: %s", speed, key, err)
            except Exception as exc:
                if "not found" in str(exc).lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                else:
                    self._logger.warning("Failed to apply speed %s for %s: %s", speed, key, exc)


def _collect_device_matches(state: Dict) -> list[str]:
    matches = set()
    for key in state.get("colors", {}):
        matches.add(key.split(":", 1)[0])
    for key in state.get("modes", {}):
        matches.add(key.split(":", 1)[0])
    for key in state.get("speeds", {}):
        matches.add(key.split(":", 1)[0])
    return sorted(matches)


def main() -> int:
    config, _, _ = load_config(DEFAULT_CONFIG)
    logging.basicConfig(
        level=_resolve_log_level(config),
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    state, _profile_name = load_current_state()
    if not state:
        logger.info("No saved profile state found; nothing to apply.")
        return 0

    core = LiquidctlCore()
    if not core.is_available:
        logger.error("liquidctl not available; cannot apply profile.")
        return 1

    matches = _collect_device_matches(state)
    if config.get("auto_initialize_on_startup", True) and matches:
        for match in matches:
            result, err = core.initialize(match)
            if err and "not found" in err.lower():
                logger.debug("Skipping initialization of unavailable device: %s", match)
                continue
            if err:
                logger.warning("Initialization failed for %s: %s", match, err)
            elif result:
                logger.debug("Initialized %s: %s", match, result)

    applier = HeadlessApplier(core)
    applier.apply_profile_data(state)
    logger.info("Profile state applied; exiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
