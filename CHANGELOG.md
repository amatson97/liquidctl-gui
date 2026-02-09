# Changelog

All notable changes to liquidctl-gui will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Backend plugin architecture**: Extensible system for supporting multiple hardware control APIs
- **Priority-based discovery**: Backends are queried by priority (liquidctl=90, hwmon=50) with automatic deduplication
- **Sysfs path deduplication**: Higher-priority backends claim device paths to prevent duplicate control
- **Decorator-based registration**: New backends auto-register using `@register_backend`
- **Backend documentation**: Comprehensive guide for adding new backends in `src/liquidctl_gui/lib/backends/README.md`

### Changed
- Refactored device discovery to use backend plugin system (liquidctl and hwmon backends)
- `detect_devices()` and `load_devices_from_config()` now use unified `discover_devices()` API
- Dynamic sysfs path matching replaces hardcoded device name filtering
- Backend system automatically handles multiple device types without special cases in main app

### Technical
- Created `src/liquidctl_gui/lib/backends/` module with abstract base class
- Implemented `DeviceBackend` ABC with `BackendCapabilities` dataclass
- Created `BackendRegistry` for managing backend registration and discovery
- Implemented `LiquidctlBackend` (priority 90) for USB/PCIe devices
- Implemented `HwmonBackend` (priority 50) for motherboard PWM fans
- Sysfs path resolution via PyUSB bus/address lookup for deduplication
- All unit tests passing (19/19)

## [0.2.0] - 2026-02-08

### Added
- **Auto-initialization on startup**: Devices are automatically initialized 500ms after app launch (configurable)
- **Settings dialog**: New UI for configuring auto-initialization and refresh intervals
- **Device capability persistence**: Full device capabilities (color channels, speed channels, modes) are saved to config
- **Enhanced device loading**: Devices load from config with capabilities refreshed from live discovery on each startup
- **Version display**: App window title now shows version number

### Changed
- `load_devices_from_config()` now performs device discovery to populate/refresh capabilities
- Device configurations in `config.json` now include full capability information
- UI controls load immediately on startup without requiring "Detect Devices" button click
- Improved config management with automatic device capability updates

### Fixed
- Devices no longer require manual detection and initialization on every app launch
- UI now shows all device controls immediately after startup
- Config file at `~/.liquidctl-gui/config.json` properly saves and loads device capabilities

### Technical
- Added `__version__` to `__init__.py`
- Added `auto_initialize_on_startup` config option (default: true)
- Added `_auto_initialize_devices()` method with GLib timeout
- Added `show_settings()` dialog method
- Enhanced `update_config_devices()` to save full device capabilities
- Improved `load_devices_from_config()` to merge config with live discovery

## [0.1.0] - 2026-02-07

### Added
- Initial release
- Dynamic device detection with automatic capability discovery
- LED color control with mode selection
- Pump and fan speed control (0-100%)
- Live status monitoring with auto-refresh
- Device initialization support
- Profile save/load functionality
- GTK3 user interface
- Python API integration with CLI fallback
- Unit tests with mock device support
- Launcher script (`launch.sh`) for easy setup
- Documentation (README, SETUP, CONTRIBUTING)
- udev rules helper scripts

### Features
- Support for multiple device types (Kraken X, Gigabyte RGB Fusion, etc.)
- Dynamic plugin system for device-specific controls
- Preset colors and speed buttons
- Status text view with scrollable output
- Configurable auto-refresh intervals
- User configuration persistence

[0.2.0]: https://github.com/amatson97/liquidctl-gui/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/amatson97/liquidctl-gui/releases/tag/v0.1.0
