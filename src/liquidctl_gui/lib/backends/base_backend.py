"""Base interface for device backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Any


@dataclass
class BackendCapabilities:
    """Capabilities and metadata for a backend."""
    name: str                      # Backend name (e.g., "liquidctl", "hwmon")
    priority: int = 50             # Higher priority = preferred (0-100)
    supports_cooling: bool = False
    supports_lighting: bool = False
    supports_monitoring: bool = False


class DeviceBackend(ABC):
    """
    Abstract base class for hardware device backends.
    
    Each backend (liquidctl, hwmon, fancontrol, etc.) implements this interface
    to provide unified device discovery and control.
    """
    
    @classmethod
    @abstractmethod
    def get_capabilities(cls) -> BackendCapabilities:
        """Return backend capabilities and metadata."""
        pass
    
    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this backend is available on the current system."""
        pass
    
    @classmethod
    @abstractmethod
    def discover_devices(cls, exclude_device_paths: Optional[List[str]] = None) -> List[Any]:
        """
        Discover devices managed by this backend.
        
        Args:
            exclude_device_paths: Optional list of sysfs paths to exclude
                                 (prevents duplicates when multiple backends
                                 can control the same hardware)
        
        Returns:
            List of device objects (backend-specific types)
        """
        pass
    
    @classmethod
    def get_device_sysfs_paths(cls, devices: List[Any]) -> List[str]:
        """
        Get sysfs device paths for discovered devices.
        Used for deduplication across backends.
        
        Args:
            devices: List of device objects from discover_devices()
        
        Returns:
            List of canonical sysfs device paths (can be empty if not applicable)
        """
        return []
