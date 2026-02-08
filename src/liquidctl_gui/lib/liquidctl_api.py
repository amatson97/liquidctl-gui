"""Wrapper for liquidctl Python API - dynamic device, mode, and channel discovery."""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

_LOGGER = logging.getLogger(__name__)

# Try to import liquidctl
try:
    from liquidctl.driver import find_liquidctl_devices
    LIQUIDCTL_AVAILABLE = True
except ImportError:
    LIQUIDCTL_AVAILABLE = False
    find_liquidctl_devices = None

# Simulation mode - set LIQUIDCTL_SIMULATE=1 to use mock devices
SIMULATION_MODE = os.environ.get('LIQUIDCTL_SIMULATE', '').lower() in ('1', 'true', 'yes')


@dataclass
class DeviceCapabilities:
    """Capabilities discovered from a liquidctl driver."""
    name: str
    description: str
    driver_class: str
    color_channels: list = field(default_factory=list)
    speed_channels: list = field(default_factory=list)
    color_modes: list = field(default_factory=list)
    supports_lighting: bool = False
    supports_cooling: bool = False


def _extract_driver_constants(driver_class, device_instance=None):
    """Extract channels and modes from driver class constants."""
    color_channels = []
    speed_channels = []
    color_modes = []

    import sys
    module_name = driver_class.__module__
    module = sys.modules.get(module_name)

    if not module:
        return color_channels, speed_channels, color_modes

    # Look for _COLOR_CHANNELS or device-specific variants
    for attr_name in dir(module):
        attr = getattr(module, attr_name, None)
        if not isinstance(attr, dict):
            continue

        if attr_name == '_COLOR_CHANNELS' or attr_name.startswith('_COLOR_CHANNELS_'):
            color_channels.extend(k for k in attr.keys() if k not in color_channels)

        if attr_name == '_SPEED_CHANNELS' or attr_name.startswith('_SPEED_CHANNELS_'):
            speed_channels.extend(k for k in attr.keys() if k not in speed_channels)

        if attr_name == '_COLOR_MODES':
            color_modes = list(attr.keys())

    # Also check device instance for color_channels property (some drivers expose it)
    if device_instance is not None:
        if hasattr(device_instance, 'color_channels'):
            try:
                channels = device_instance.color_channels
                if isinstance(channels, dict):
                    color_channels = list(channels.keys())
            except Exception:
                pass
        if hasattr(device_instance, 'speed_channels'):
            try:
                channels = device_instance.speed_channels
                if isinstance(channels, dict):
                    speed_channels = list(channels.keys())
            except Exception:
                pass

    # Deduplicate while preserving order
    color_channels = list(dict.fromkeys(color_channels))
    speed_channels = list(dict.fromkeys(speed_channels))

    # Add 'sync' as a pseudo-channel if not present but other channels exist
    if color_channels and 'sync' not in color_channels:
        color_channels = ['sync'] + color_channels

    return color_channels, speed_channels, color_modes


class LiquidctlAPI:
    """Wrapper for liquidctl Python API with dynamic capability discovery."""

    def __init__(self, simulated_devices: list = None):
        """Initialize the API.

        Args:
            simulated_devices: Optional list of mock device instances for testing.
                             If provided, these devices will be used instead of
                             real hardware.
        """
        self._devices = []
        self._device_map = {}  # description -> device instance
        self._simulated_devices = simulated_devices
        self._simulation_mode = simulated_devices is not None or SIMULATION_MODE

    @property
    def is_available(self):
        """Check if liquidctl library is available (or simulation mode is active)."""
        return LIQUIDCTL_AVAILABLE or self._simulation_mode

    @property
    def is_simulated(self):
        """Check if we're using simulated devices."""
        return self._simulation_mode

    def _get_device_iterator(self):
        """Get the device iterator - either simulated or real devices."""
        if self._simulated_devices is not None:
            return iter(self._simulated_devices)

        if SIMULATION_MODE:
            try:
                from tests.mock_devices import get_mock_devices
                _LOGGER.info("[API] Simulation mode enabled - using mock devices")
                return iter(get_mock_devices())
            except ImportError:
                _LOGGER.warning("[API] Simulation mode enabled but mock_devices not found")
                return iter([])

        if not LIQUIDCTL_AVAILABLE:
            return iter([])

        return find_liquidctl_devices()

    def find_devices(self):
        """Find all liquidctl-compatible devices and extract their capabilities."""
        if not self.is_available:
            _LOGGER.error("liquidctl library not available and simulation mode not enabled")
            return []

        sim_label = " (SIMULATED)" if self._simulation_mode else ""
        _LOGGER.info("[API] Scanning for devices%s...", sim_label)
        self._devices = []
        self._device_map = {}

        try:
            for device in self._get_device_iterator():
                driver_class = type(device)
                _LOGGER.debug("[API] Inspecting driver: %s (module: %s)", driver_class.__name__, driver_class.__module__)
                color_channels, speed_channels, color_modes = _extract_driver_constants(driver_class, device)

                # Check device-level capability flags
                supports_lighting = getattr(device, 'supports_lighting', bool(color_channels))
                supports_cooling = getattr(device, 'supports_cooling', bool(speed_channels))

                caps = DeviceCapabilities(
                    name=device.description,
                    description=device.description,
                    driver_class=driver_class.__name__,
                    color_channels=color_channels,
                    speed_channels=speed_channels,
                    color_modes=color_modes,
                    supports_lighting=supports_lighting,
                    supports_cooling=supports_cooling,
                )
                self._devices.append(caps)
                self._device_map[device.description] = device
                _LOGGER.info("[API] Found device: %s", caps.name)
                _LOGGER.info("[API]   Driver: %s", caps.driver_class)
                _LOGGER.info("[API]   Color channels: %s", caps.color_channels)
                _LOGGER.info("[API]   Speed channels: %s", caps.speed_channels)
                _LOGGER.info("[API]   Color modes (%d): %s", len(caps.color_modes), caps.color_modes[:6])

        except Exception as e:
            _LOGGER.exception("Failed to enumerate devices: %s", e)

        return self._devices

    def get_device(self, description: str):
        """Get a device instance by its description."""
        return self._device_map.get(description)

    def get_capabilities(self, description: str) -> DeviceCapabilities | None:
        """Get capabilities for a device by description."""
        for caps in self._devices:
            if caps.description == description:
                return caps
        return None

    def initialize(self, description: str) -> tuple[list, str]:
        """Initialize a device and return (status_list, error_string)."""
        _LOGGER.info("[API] Initializing device: %s", description)
        device = self.get_device(description)
        if not device:
            return [], f"Device not found: {description}"

        try:
            device.connect()
            result = device.initialize() or []
            device.disconnect()
            _LOGGER.info("[API] Initialize complete, returned %d properties", len(result))
            return result, ""
        except Exception as e:
            _LOGGER.exception("[API] Initialize failed for %s", description)
            return [], str(e)

    def get_status(self, description: str) -> tuple[list, str]:
        """Get device status and return (status_list, error_string)."""
        _LOGGER.debug("[API] Getting status for: %s", description)
        device = self.get_device(description)
        if not device:
            return [], f"Device not found: {description}"

        try:
            device.connect()
            result = device.get_status() or []
            device.disconnect()
            _LOGGER.debug("[API] Status returned %d properties", len(result))
            return result, ""
        except Exception as e:
            _LOGGER.exception("get_status failed for %s", description)
            return [], str(e)

    def set_color(self, description: str, channel: str, mode: str, colors: list, speed: str = 'normal') -> tuple[bool, str]:
        """Set LED color/mode and return (success, error_string)."""
        _LOGGER.info("[API] set_color: device=%s channel=%s mode=%s colors=%s", description, channel, mode, colors)
        device = self.get_device(description)
        if not device:
            return False, f"Device not found: {description}"

        try:
            # If mode requires a color (e.g. 'fixed') but no colors were supplied,
            # return a clear error instead of calling into the driver which will
            # raise an exception.
            if (not colors) and (mode != 'off'):
                _LOGGER.warning("[API] set_color: no colors provided for mode=%s device=%s channel=%s", mode, description, channel)
                return False, "No colors provided for mode"

            device.connect()
            device.set_color(channel=channel, mode=mode, colors=colors, speed=speed)
            device.disconnect()
            _LOGGER.info("[API] set_color succeeded")
            return True, ""
        except Exception as e:
            _LOGGER.exception("[API] set_color failed for %s", description)
            return False, str(e)

    def set_speed(self, description: str, channel: str, speed) -> tuple[bool, str]:
        """Set fan/pump speed and return (success, error_string).

        Accepts numeric or numeric-string `speed` values and coerces to int.
        Returns (False, error_message) if conversion fails.
        """
        try:
            speed_int = int(speed)
        except (TypeError, ValueError):
            _LOGGER.warning("[API] set_speed: invalid speed value %r for device=%s channel=%s", speed, description, channel)
            return False, f"Invalid speed value: {speed}"

        _LOGGER.info("[API] set_speed: device=%s channel=%s speed=%d%%", description, channel, speed_int)
        device = self.get_device(description)
        if not device:
            return False, f"Device not found: {description}"

        try:
            device.connect()
            device.set_fixed_speed(channel=channel, duty=speed_int)
            device.disconnect()
            _LOGGER.info("[API] set_speed succeeded")
            return True, ""
        except PermissionError as e:
            # Permission errors writing to /sys (hwmon pwm) are common when
            # the user has not configured udev rules or is not running with
            # sufficient privileges. Return a friendly, actionable message
            # (do not log a stacktrace for security/noise reasons).
            _LOGGER.warning("[API] set_speed permission denied for %s: %s", description, e)
            return False, f"Permission denied writing to system hwmon node: {e}"
        except Exception as e:
            _LOGGER.exception("[API] set_speed failed for %s", description)
            return False, str(e)

    def format_status(self, status_list: list) -> str:
        """Format status tuples into a readable string."""
        if not status_list:
            return "No status available"
        lines = []
        for item in status_list:
            if len(item) >= 3:
                prop, value, unit = item[0], item[1], item[2]
                lines.append(f"{prop}: {value} {unit}".strip())
            elif len(item) == 2:
                lines.append(f"{item[0]}: {item[1]}")
        return "\n".join(lines) if lines else "No status available"
