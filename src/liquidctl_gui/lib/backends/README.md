# Backend Plugin System

This directory contains the backend plugin system for liquidctl-gui, which allows multiple hardware control APIs to coexist and be easily extended.

## Architecture

The backend system uses a priority-based plugin architecture:

1. **Abstract Base Class** (`base_backend.py`): Defines the `DeviceBackend` interface
2. **Registry** (`registry.py`): Manages backend registration and device discovery
3. **Concrete Backends**: Individual implementations (liquidctl, hwmon, etc.)

### Key Concepts

- **Priority System**: Backends have priority values (0-100). Higher priority backends are queried first.
- **Automatic Deduplication**: Higher-priority backends can claim sysfs device paths, preventing lower-priority backends from duplicating the same hardware.
- **Decorator Registration**: Backends auto-register using the `@register_backend` decorator.

## Current Backends

| Backend | Priority | Purpose | Capabilities |
|---------|----------|---------|--------------|
| `liquidctl` | 90 | USB/PCIe devices via liquidctl | Full RGB + cooling + monitoring |
| `hwmon` | 50 | Linux hwmon subsystem | Basic PWM fan control |

## Adding a New Backend

### 1. Create Backend File

Create a new file in this directory (e.g., `mybackend_backend.py`):

```python
"""MyBackend - Description of backend."""

import logging
from typing import List, Optional
from .base_backend import DeviceBackend, BackendCapabilities
from .registry import register_backend

logger = logging.getLogger(__name__)

@register_backend
class MyBackend(DeviceBackend):
    """Backend for controlling XYZ hardware."""
    
    @classmethod
    def get_capabilities(cls) -> BackendCapabilities:
        """Define backend capabilities and priority."""
        return BackendCapabilities(
            name="mybackend",
            priority=70,  # Between liquidctl (90) and hwmon (50)
            supports_cooling=True,
            supports_lighting=False,
            supports_monitoring=True,
        )
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if backend dependencies are available."""
        try:
            import mybackend_lib  # Your library
            return True
        except ImportError:
            return False
    
    @classmethod
    def discover_devices(cls, exclude_device_paths: Optional[List[str]] = None) -> List:
        """Discover devices controlled by this backend.
        
        Args:
            exclude_device_paths: Sysfs paths to exclude (claimed by higher-priority backends)
            
        Returns:
            List of device objects (can be custom types)
        """
        if not cls.is_available():
            return []
        
        # Your discovery logic here
        devices = []
        
        # Example: Filter out devices already claimed
        if exclude_device_paths:
            devices = [d for d in devices 
                      if get_device_path(d) not in exclude_device_paths]
        
        return devices
    
    @classmethod
    def get_device_sysfs_paths(cls, devices: List) -> List[str]:
        """Get sysfs paths for discovered devices (optional).
        
        This is used for deduplication - paths returned here will be
        excluded from lower-priority backends.
        
        Returns:
            List of /sys/devices/... paths
        """
        return []  # Implement if you want to exclude these from lower backends
```

### 2. Import in `__init__.py`

Add import to `/home/adam/liquidctl-gui/src/liquidctl_gui/lib/backends/__init__.py`:

```python
# Import concrete backends (triggers @register_backend)
from . import liquidctl_backend
from . import hwmon_backend
from . import mybackend_backend  # Add this line
```

### 3. Create UI Plugin (if needed)

If your backend returns custom device types, create a UI plugin in the main app:

```python
# In app.py
class MyBackendDevicePlugin:
    def __init__(self, device, core):
        self.device = device
        # Build UI for your device type
```

That's it! Your backend will automatically:
- Register with the system
- Be discovered and queried based on priority
- Participate in automatic deduplication

## Priority Guidelines

Choose priority based on feature completeness:

- **90-100**: Full-featured APIs (RGB, cooling, monitoring, per-device control)
- **60-89**: Specialized or mid-featured APIs
- **30-59**: Basic APIs (simple fan control, basic monitoring)
- **0-29**: Fallback implementations

Higher priority backends are preferred when multiple backends can control the same hardware.

## Device Types

Backends can return any device type. Common patterns:

- Use existing types (`DeviceInfo` from liquidctl API)
- Create custom types (`HwmonDevice` for hwmon backend)
- Main app checks `isinstance()` to determine UI to show

## Sysfs Path Deduplication

To prevent multiple backends from controlling the same hardware:

1. Higher-priority backend discovers devices
2. Calls `get_device_sysfs_paths()` on those devices
3. Returns list of `/sys/devices/pci.../...` paths
4. Lower-priority backends receive these paths via `exclude_device_paths`
5. Lower backends filter out matching hardware

Example: liquidctl claims USB device at `/sys/devices/pci0000:00/.../3-1`, so hwmon won't try to control that same device's hwmon interface.

## Testing

Test your backend:

```python
from src.liquidctl_gui.lib.backends import get_all_backends, discover_devices

# Check registration
backends = get_all_backends()
print([b.get_capabilities().name for b in backends])

# Test discovery
results = discover_devices()
for backend_class, devices in results:
    caps = backend_class.get_capabilities()
    print(f"{caps.name}: {len(devices)} devices")
```

## Design Philosophy

- **Loose Coupling**: Backends are independent, main app doesn't know about specific implementations
- **Fail Gracefully**: If a backend is unavailable, it's skipped without affecting others
- **Transparent**: All backends use the same discovery flow, no special cases
- **Extensible**: Adding backends requires no changes to core application logic
