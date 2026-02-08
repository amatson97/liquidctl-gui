# Liquidctl GUI — Project Notes (current)

This document provides a concise, up-to-date context summary for the Liquidctl GUI project used by the repository's automation and assistant workflows.

## Project Overview
Python GTK GUI for controlling liquidctl-supported devices (examples found on this system include Gigabyte RGB Fusion 2.0 8297 and NZXT Kraken X). The GUI prefers the `liquidctl` Python API but falls back to the CLI when needed.

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

## Recent fixes and behaviors you should know
- `launch.sh` now automates venv creation and `liquidctl` installation, and supports `--yes` for non-interactive installs.
- Speed values loaded from saved profiles may be strings; code now coerces them to int before passing to drivers.
- Loading profiles skips empty color values and avoids calling drivers with missing color lists (returns clear errors instead).
- Logging format issues were fixed by ensuring numeric formatting only receives numbers.
- `docs/SETUP.md` added with udev guidance to avoid running the GUI as root.
- Unit tests are present (`tests/test_unit.py`) and currently pass in the workspace.

## Development priorities (current)
1. Improve user-facing error messages and recovery flows (permission errors, missing deps).
2. Add non-interactive install options and CI-friendly setup path.
3. Improve profile validation (schema + better recovery for malformed profiles).
4. Optional: add fan-curve editor and effect presets.

## Known runtime constraints
- Some drivers write to `/sys/class/.../hwmon/.../pwm*` which require root or appropriate udev rules — avoid running GUI as root where possible.
- Device capability discovery is dynamic; the GUI builds controls based on driver-reported channels and modes.

## How to run tests locally
```bash
PYTHONPATH=src python3 -m unittest tests.test_unit
```

## Useful notes for the assistant
- Prefer the venv-based `liquidctl` (installed by `./launch.sh`) so the GUI uses the Python API.
- If you need to change system packages programmatically, use the `--yes` flag and clearly document the sudo steps.
- When applying color/mode changes from profiles, validate that colors are present for modes that require them before calling driver APIs.

If you want, I can further expand this file with templates for profile JSON, example udev rules specific to detected hardware, or CI steps to run tests in a clean environment.