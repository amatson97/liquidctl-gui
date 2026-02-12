"""Device backend plugin system for extensible hardware control."""

from .base_backend import DeviceBackend, BackendCapabilities
from .registry import BackendRegistry, register_backend, get_all_backends, discover_devices

# Import backend implementations to trigger registration
from . import liquidctl_backend
from . import hwmon_backend

__all__ = [
    'DeviceBackend',
    'BackendCapabilities',
    'BackendRegistry',
    'register_backend',
    'get_all_backends',
    'discover_devices',
]
