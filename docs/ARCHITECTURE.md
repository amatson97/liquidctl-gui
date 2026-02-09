# Liquidctl GUI Architecture

## System Overview

Liquidctl GUI is a GTK-based application for controlling RGB lighting and fan speeds on compatible hardware through liquidctl and hwmon backends.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Liquidctl GUI (GTK)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────┐         ┌──────────────────┐            │
│  │   app.py       │────────▶│  UI Components   │            │
│  │  (Main Window) │         │  - Device List   │            │
│  └────────┬───────┘         │  - Controls      │            │
│           │                 │  - Status Panel  │            │ 
│           │                 └──────────────────┘            │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────────────────────────────┐                │
│  │        Plugin System                    │                │
│  │  ┌──────────────┐  ┌─────────────────┐  │                │
│  │  │ Dynamic      │  │ Hwmon           │  │                │
│  │  │ Plugin       │  │ Plugin          │  │                │
│  │  │ (liquidctl)  │  │ (motherboard)   │  │                │
│  │  └──────┬───────┘  └────────┬────────┘  │                │
│  └─────────┼───────────────────┼───────────┘                │
│            │                   │                            │
├────────────┼───────────────────┼────────────────────────────┤
│            ▼                   ▼                            │
│  ┌─────────────────┐  ┌──────────────────┐                  │
│  │ Backend System  │  │ Profile Manager  │                  │
│  │                 │  │                  │                  │
│  │ ┌────────────┐  │  │ - Save/Load      │                  │
│  │ │ Liquidctl  │  │  │ - Apply State    │                  │
│  │ │ Backend    │  │  │ - Auto-save      │                  │
│  │ │ (priority  │  │  └──────────────────┘                  │
│  │ │  90)       │  │                                        │
│  │ └────────────┘  │                                        │
│  │                 │                                        │
│  │ ┌────────────┐  │                                        │
│  │ │ Hwmon      │  │                                        │
│  │ │ Backend    │  │                                        │
│  │ │ (priority  │  │                                        │
│  │ │  50)       │  │                                        │
│  │ └────────────┘  │                                        │
│  └─────────┬───────┘                                        │
│            │                                                │
├────────────┼────────────────────────────────────────────────┤
│            ▼                                                │
│  ┌─────────────────────────────────────────────┐            │
│  │          Hardware Abstraction Layer         │            │
│  │                                             │            │
│  │  ┌───────────────┐        ┌───────────────┐ │            │
│  │  │ liquidctl_api │        │  hwmon_api    │ │            │
│  │  │               │        │               │ │            │
│  │  │ - USB/PCIe    │        │ - sysfs       │ │            │
│  │  │ - Dynamic     │        │ - PWM control │ │            │
│  │  │   discovery   │        │ - Fan/temp    │ │            │
│  │  └───────┬───────┘        └───────┬───────┘ │            │
│  └──────────┼────────────────────────┼─────────┘            │
│             │                        │                      │
├─────────────┼────────────────────────┼──────────────────────┤
│             ▼                        ▼                      │
│  ┌──────────────────┐    ┌──────────────────────┐           │
│  │ liquidctl library│    │ Linux hwmon subsystem│           │
│  │ (Python API)     │    │ (/sys/class/hwmon)   │           │
│  └──────────────────┘    └──────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Main Application (`app.py`)
- **GTK Window Management**: Create and manage main window
- **Device List UI**: Display available devices
- **Event Handling**: User interactions (clicks, selections)
- **Plugin Coordination**: Delegate to device-specific plugins
- **Profile Management**: Save/load/apply user settings
- **Auto-initialization**: Start devices on app launch
- **Status Display**: Show device status and errors

### Backend System (`lib/backends/`)
- **Plugin Architecture**: Extensible backend registration
- **Priority-based Discovery**: Higher priority backends discovered first
- **Deduplication**: Prevent same device appearing twice
- **Device Abstraction**: Uniform interface for different hardware types

#### Liquidctl Backend (`liquidctl_backend.py`)
- Priority: 90 (high)
- Devices: USB/PCIe devices (Kraken, RGB Fusion, etc.)
- Features: Full RGB control, fan/pump control, monitoring
- Detection: Uses liquidctl Python API

#### Hwmon Backend (`hwmon_backend.py`)
- Priority: 50 (medium)
- Devices: Motherboard fan controllers, some coolers
- Features: PWM fan control, temperature/speed reading
- Detection: Scans `/sys/class/hwmon/`
- Safety: Enforces minimum 20% PWM to prevent fan stall

### Plugin System
Plugins provide device-specific UI and control logic.

#### GenericStatusPlugin
- For devices with only monitoring (no controls)
- Shows status text view

#### DynamicDevicePlugin
- For liquidctl devices with lighting/speed control
- Dynamically builds UI based on device capabilities
- Handles color/mode/speed controls

#### HwmonDevicePlugin
- For motherboard PWM fan controllers
- Simple speed slider interface
- PWM enable mode management

### Hardware APIs (`lib/`)

#### `liquidctl_api.py`
- Wrapper for liquidctl Python library
- Dynamic capability discovery
- Device initialization and control
- Sysfs path tracking for deduplication

#### `hwmon_api.py`
- Linux hwmon subsystem interface
- PWM output discovery and control
- Fan speed and temperature reading
- Safety checks (minimum PWM, writable testing)

#### `sensors_api.py`
- lm-sensors integration
- CPU/GPU temperature reading
- Supplements hwmon data

### Support Modules

#### `functions.py` (LiquidctlCore)
- Bridge between API and CLI modes
- Device discovery wrapper
- Error handling and formatting

#### `config.py`
- Configuration file management (`~/.liquidctl-gui/`)
- Profile save/load
- Device persistence
- Window state saving

#### `error_handler.py` ⭐ NEW
- Centralized error handling
- Structured logging with context
- Operation tracing
- Error categorization

## Data Flow

### Device Discovery
```
User starts app
    ↓
load_devices_from_config() OR detect_devices()
    ↓
discover_devices() (from backend system)
    ↓
├─ LiquidctlBackend.discover_devices()
│     ├─ Scan USB/PCIe devices
│     ├─ Extract capabilities (channels, modes)
│     └─ Return DeviceInfo list
│
└─ HwmonBackend.discover_devices()
      ├─ Scan /sys/class/hwmon/
      ├─ Filter excluded devices (from liquidctl)
      ├─ Test PWM writability
      └─ Return HwmonDevice list
    ↓
Create UI for each device
    ↓
Auto-initialize (if enabled)
```

### LED Color Change
```
User clicks color button
    ↓
apply_preset_color(device, channel, color)
    ↓
set_led_color(device, channel, color)
    ↓
core.set_color(device, channel, mode, color)
    ↓
├─ If using API (default):
│     ├─ api.get_device(device)
│     ├─ device.connect()
│     ├─ device.set_color(channel, mode, [RGB])
│     └─ device.disconnect()
│
└─ If using CLI:
      ├─ Build command string
      └─ Run subprocess
    ↓
Check for errors
    ├─ If "not found": Show status message
    └─ If other error: Show error dialog
    ↓
Save to last_colors{} for profile
```

### Profile Application
```
Load profile from disk
    ↓
apply_profile_data(profile)
    ↓
For each setting:
    ├─ Try to apply
    ├─ If "device not found": Skip silently
    └─ If other error: Log warning
    ↓
Profile applied (partial or full)
```

## Error Handling Strategy

### Error Categories
1. **DEVICE_NOT_FOUND**: Device disconnected/unavailable
2. **DEVICE_INIT**: Initialization failure
3. **DEVICE_CONTROL**: Control operation failed
4. **PERMISSION**: Permission denied
5. **CONFIG**: Configuration file error
6. **PROFILE**: Profile load/save error

### Error Flow
```
Operation fails
    ↓
Check error type
    ├─ "not found" → Log, show status message, continue
    ├─ Permission error → Show error dialog with fix suggestion
    └─ Other → Log with context, show error dialog
```

## Configuration Files

Located in `~/.liquidctl-gui/`:

- **`config.json`**: App settings, window state, device list
- **`current_profile.json`**: Last session state (auto-saved)
- **`profiles/<name>.json`**: Named user profiles

## Key Design Decisions

1. **Backend Priority System**: Liquidctl preferred over hwmon for same device
2. **Dynamic UI Generation**: UI built from device capabilities, not hardcoded
3. **Graceful Degradation**: Missing devices don't break the app
4. **Auto-save Session**: Current state saved automatically
5. **Safety Minimums**: PWM never below 20% to prevent fan stall
6. **Permission Testing**: PWM writability tested before showing device
7. **Deduplication**: Sysfs paths prevent duplicate device entries

## Threading Model

- **Main Thread**: GTK event loop, UI updates
- **GLib Timers**: Status refresh (3s), device initialization
- **No Background Threads**: All operations blocking in main thread
- **Future**: Consider threading for long operations

## Extension Points

To add a new backend:
1. Create `lib/backends/your_backend.py`
2. Inherit from `DeviceBackend`
3. Implement required methods
4. Decorate with `@register_backend`
5. Set appropriate priority

To add a new device plugin:
1. Inherit from `DevicePlugin`
2. Implement `build_ui()`, `refresh_status()`, `initialize()`
3. Add detection logic in `plugin_for_device()`

## Future Improvements

See `REFACTORING_PLAN.md` for planned architectural improvements:
- Extract device operations to `device_controller.py`
- Extract profile management to `profile_manager.py`
- Split UI builders from `app.py`
- Add comprehensive type hints
- Expand error handling system
