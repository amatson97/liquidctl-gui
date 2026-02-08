# Liquidctl GUI — Project Notes (current)

**Version: 0.2.0**

This document provides a concise, up-to-date context summary for the Liquidctl GUI project used by the repository's automation and assistant workflows.

## Project Overview
Python GTK GUI for controlling liquidctl-supported devices (examples include Gigabyte RGB Fusion 2.0 and NZXT Kraken X). The GUI uses the `liquidctl` Python API when available and falls back to CLI when needed. Devices are automatically detected, initialized on startup, and their capabilities are persisted for instant UI loading.

## Current recommended setup
- Use the provided launcher `./launch.sh` from the project root. It will:
	- Create a `.venv` (Python virtualenv) if missing and activate it.
	- Install `liquidctl` into the venv via `pip`.
	- Check for GTK system bindings (`python3-gi`, `gir1.2-gtk-3.0`) and can prompt to install them on Debian/Ubuntu. Use `./launch.sh --yes` or `./launch.sh -y` to auto-accept the apt install.

- Hardware access: writing PWM / hwmon values requires permissions. See `docs/SETUP.md` for udev rule examples so the GUI can operate without running as root.

## Key code entry points
- `src/liquidctl_gui/app.py` — GTK application and UI glue.
- `src/liquidctl_gui/lib/liquidctl_api.py` — Python-API wrapper with discovery, set_color, set_speed, format_status.
- `src/liquidctl_gui/lib/functions.py` — Core helpers and CLI fallback builders.

## Recent fixes and behaviors you should know (v0.2.0)
- **Auto-initialization on startup**: Devices automatically initialize 500ms after app start (configurable)
- **Device capability persistence**: Full device capabilities (channels, modes) saved to config and loaded on startup
- **Improved device loading**: Config devices are matched with live discovery to refresh capabilities
- **Settings dialog**: Added UI for configuring auto-init and refresh intervals
- **No manual detection needed**: UI loads with all controls ready on every launch
- `launch.sh` automates venv creation and `liquidctl` installation, supports `--yes` for non-interactive installs
- Speed values loaded from saved profiles are coerced to int before passing to drivers
- Loading profiles skips empty color values with clear error messages
- Logging format issues fixed (numeric formatting only receives numbers)
- `docs/SETUP.md` added with udev guidance to avoid running the GUI as root
- Unit tests present (`tests/test_unit.py`) and passing

## Development priorities (current)
1. ✅ Auto-initialization on startup — **COMPLETED in v0.2.0**
2. ✅ Device capability persistence — **COMPLETED in v0.2.0**
3. ✅ Settings dialog for user preferences — **COMPLETED in v0.2.0**
4. Improve user-facing error messages and recovery flows (permission errors, missing deps)
5. Improve profile validation (schema + better recovery for malformed profiles)
6. Add fan-curve editor with custom temperature/speed mappings
7. Add visual effect presets and animations library
8. GUI visual improvements and modern theming

## Known runtime constraints
- Some drivers write to `/sys/class/.../hwmon/.../pwm*` which require root or appropriate udev rules — avoid running GUI as root where possible.
- Device capability discovery is dynamic; the GUI builds controls based on driver-reported channels and modes.

## How to run tests locally
```bash
PYTHONPATH=src python3 -m unittest tests.test_unit
```

## Useful notes for the assistant
- Prefer the venv-based `liquidctl` (installed by `./launch.sh`) so the GUI uses the Python API
- Auto-initialization happens via `GLib.timeout_add` 500ms after device loading completes
- Device capabilities are saved to `~/.liquidctl-gui/config.json` with full channel and mode information
- `load_devices_from_config()` runs device discovery to refresh capabilities on every startup
- Settings are persisted immediately when changed via the Settings dialog
- If you need to change system packages programmatically, use the `--yes` flag and clearly document the sudo steps
- When applying color/mode changes from profiles, validate that colors are present for modes that require them before calling driver APIs

## Config file structure
The config now includes:
- `devices[]` array with full capability info (color_channels, speed_channels, color_modes, supports_lighting, supports_cooling)
- `auto_initialize_on_startup` boolean (default: true)
- `auto_refresh_enabled` and `auto_refresh_seconds` for status polling
- Window size, presets, and UI preferences