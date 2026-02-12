"""Liquidctl backend - USB/PCIe device control."""

import logging
from typing import List, Optional, Any
from ..functions import LiquidctlCore, DeviceInfo
from ..liquidctl_api import LIQUIDCTL_AVAILABLE, SIMULATION_MODE
from .base_backend import DeviceBackend, BackendCapabilities
from .registry import register_backend


logger = logging.getLogger(__name__)


@register_backend
class LiquidctlBackend(DeviceBackend):
    """Backend for liquidctl-compatible USB/PCIe devices."""
    
    @classmethod
    def get_capabilities(cls) -> BackendCapabilities:
        return BackendCapabilities(
            name="liquidctl",
            priority=90,  # High priority - prefer full-featured API over basic hwmon
            supports_cooling=True,
            supports_lighting=True,
            supports_monitoring=True,
        )
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if liquidctl is available."""
        return LIQUIDCTL_AVAILABLE or SIMULATION_MODE
    
    @classmethod
    def discover_devices(cls, exclude_device_paths: Optional[List[str]] = None) -> List[DeviceInfo]:
        """Discover liquidctl-compatible devices."""
        core = LiquidctlCore()
        if not core.is_available:
            logger.debug("Liquidctl not available")
            return []
        
        devices = core.find_devices()
        logger.debug("Liquidctl discovered %d devices", len(devices))
        return devices
    
    @classmethod
    def get_device_sysfs_paths(cls, devices: List[DeviceInfo]) -> List[str]:
        """Get sysfs paths for liquidctl devices to exclude from hwmon."""
        core = LiquidctlCore()
        if not core.is_available:
            return []
        
        paths = core.get_device_sysfs_paths()
        logger.debug("Liquidctl manages %d sysfs device paths", len(paths))
        return paths
