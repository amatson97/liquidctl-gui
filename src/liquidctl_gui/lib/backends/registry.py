"""Backend registry and discovery system."""

import logging
from typing import List, Type, Tuple, Any
from .base_backend import DeviceBackend, BackendCapabilities


logger = logging.getLogger(__name__)


class BackendRegistry:
    """Manages registration and discovery of device backends."""
    
    _backends: List[Type[DeviceBackend]] = []
    
    @classmethod
    def register(cls, backend_class: Type[DeviceBackend]) -> None:
        """Register a backend class."""
        if backend_class not in cls._backends:
            cls._backends.append(backend_class)
            caps = backend_class.get_capabilities()
            logger.debug("Registered backend: %s (priority: %d)", caps.name, caps.priority)
    
    @classmethod
    def get_all_backends(cls) -> List[Type[DeviceBackend]]:
        """Get all registered backends, sorted by priority (highest first)."""
        available = [b for b in cls._backends if b.is_available()]
        # Sort by priority (descending) - higher priority backends checked first
        return sorted(available, key=lambda b: b.get_capabilities().priority, reverse=True)
    
    @classmethod
    def discover_all_devices(cls) -> List[Tuple[Type[DeviceBackend], List[Any]]]:
        """
        Discover devices from all backends with automatic deduplication.
        
        Higher priority backends are queried first, and their device paths
        are excluded from lower priority backends to prevent duplicates.
        
        Returns:
            List of (backend_class, devices) tuples
        """
        results = []
        excluded_paths = []
        
        for backend_class in cls.get_all_backends():
            caps = backend_class.get_capabilities()
            logger.debug("Discovering devices from backend: %s", caps.name)
            
            try:
                # Discover devices, excluding paths from higher-priority backends
                devices = backend_class.discover_devices(exclude_device_paths=excluded_paths)
                
                if devices:
                    logger.info("Backend %s found %d device(s)", caps.name, len(devices))
                    results.append((backend_class, devices))
                    
                    # Get sysfs paths from these devices to exclude from lower-priority backends
                    device_paths = backend_class.get_device_sysfs_paths(devices)
                    if device_paths:
                        logger.debug("Backend %s claims %d sysfs paths", caps.name, len(device_paths))
                        excluded_paths.extend(device_paths)
                else:
                    logger.debug("Backend %s found no devices", caps.name)
                    
            except Exception as e:
                logger.exception("Error discovering devices from backend %s: %s", caps.name, e)
        
        return results


def register_backend(backend_class: Type[DeviceBackend]) -> Type[DeviceBackend]:
    """Decorator to register a backend class."""
    BackendRegistry.register(backend_class)
    return backend_class


def get_all_backends() -> List[Type[DeviceBackend]]:
    """Get all available backends."""
    return BackendRegistry.get_all_backends()


def discover_devices() -> List[Tuple[Type[DeviceBackend], List[Any]]]:
    """Discover devices from all backends."""
    return BackendRegistry.discover_all_devices()
