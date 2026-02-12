"""Hwmon backend - Motherboard PWM fan control."""

import logging
from pathlib import Path
from typing import List, Optional, Any
from ..hwmon_api import find_hwmon_devices, HwmonDevice
from .base_backend import DeviceBackend, BackendCapabilities
from .registry import register_backend


logger = logging.getLogger(__name__)


@register_backend
class HwmonBackend(DeviceBackend):
    """Backend for motherboard PWM fan control via Linux hwmon subsystem."""
    
    @classmethod
    def get_capabilities(cls) -> BackendCapabilities:
        return BackendCapabilities(
            name="hwmon",
            priority=50,  # Lower priority than liquidctl (USB devices use better API)
            supports_cooling=True,
            supports_lighting=False,
            supports_monitoring=True,
        )
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if hwmon subsystem is available."""
        return Path("/sys/class/hwmon").exists()
    
    @classmethod
    def discover_devices(cls, exclude_device_paths: Optional[List[str]] = None) -> List[HwmonDevice]:
        """Discover hwmon PWM fan controllers."""
        devices = find_hwmon_devices(exclude_device_paths=exclude_device_paths)
        logger.debug("Hwmon discovered %d devices", len(devices))
        return devices
    
    @classmethod
    def get_device_sysfs_paths(cls, devices: List[HwmonDevice]) -> List[str]:
        """Hwmon devices don't need to exclude others (they're at the bottom of priority)."""
        return []
