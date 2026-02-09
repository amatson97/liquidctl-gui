# Liquidctl GUI - AI Context Prompt

Version: 0.2.0

Purpose: Provide a concise, high-signal summary of the liquidctl-gui codebase, runtime behavior, and workflows for AI assistance.

## Project Overview
- Python GTK GUI for controlling liquidctl-supported USB devices and motherboard PWM fans via Linux hwmon.
- Uses liquidctl Python API when available, falls back to CLI when needed.
- Devices are auto-detected, auto-initialized (500ms delay), and their capabilities are persisted for instant UI loading.

## Quick Start
- Setup: `./launch.sh` (creates `.venv`, installs `liquidctl`, checks GTK deps; `--yes` for non-interactive).
- Run: `PYTHONPATH=src python3 -m liquidctl_gui`
- Tests: `PYTHONPATH=src python3 -m unittest tests.test_unit`

## Key Code Entry Points
- `src/liquidctl_gui/app.py`: GTK app and UI glue (now thinner, delegates logic)
- `src/liquidctl_gui/lib/device_controller.py`: Device control operations (LEDs, modes, speeds, hwmon)
- `src/liquidctl_gui/lib/profile_manager.py`: Profile save/load/apply, state tracking
- `src/liquidctl_gui/lib/liquidctl_api.py`: Python API wrapper for liquidctl
- `src/liquidctl_gui/lib/hwmon_api.py`: Linux hwmon PWM control
- `src/liquidctl_gui/lib/functions.py`: LiquidctlCore with API/CLI bridge
- `src/liquidctl_gui/lib/backends/`: Backend plugin system (priority-based discovery)
- `src/liquidctl_gui/lib/error_handler.py`: Centralized error handling (created, not fully integrated)

## Recent Refactor Status
- Phase 2 (Code Organization) complete:
  - Device operations moved to `device_controller.py`.
  - Profile management moved to `profile_manager.py`.
  - app.py reduced from 1709 lines to 1268 lines.
- Remaining: Integrate `error_handler.py` across codebase, add UI builders split, and expand tests.

## Runtime Behavior and Constraints
- Device discovery is dynamic; UI is built from driver-reported capabilities.
- Hwmon PWM access requires udev rules or sudo; avoid running GUI as root when possible.
- PWM safety: minimum 20% enforced; read-only PWM (amdgpu) filtered out during discovery.
- Profile restoration skips unavailable devices without error dialogs.

## Profiles and State
- Profiles stored at `~/.liquidctl-gui/profiles/`.
- Current session state auto-saved to `~/.liquidctl-gui/current_profile.json`.
- `apply_profile_data()` applies sync modes first, then regular modes, then color-only, then speeds.

## Config and Persistence
- Config: `~/.liquidctl-gui/config.json`
- Stored: window size, auto-init, refresh interval, preset colors/speeds, device capabilities.
- `load_devices_from_config()` refreshes capabilities via live discovery on startup.

## Error Handling Patterns
- Control methods return `(success, error)`; check `if not success` then parse error.
- Silently skip "not found" errors during auto-init and profile load.
- Permission errors should recommend udev rules (`docs/SETUP.md`).

## Logging and Debugging
- Use `./launch.sh 2>&1 | tee liquidctl-gui.log` for logs.
- `scripts/debug.sh` runs with verbose logging to `app_debug.log`.

## Common Issues and Fixes
- "Device not found" on startup: now skipped (no dialogs).
- amdgpu PWM `[Errno 22]`: device filtered out automatically.
- Permission denied: run `scripts/install_udev_rules.sh`.

## Release Workflow (Maintainers)
- Use `./scripts/pre-release-check.sh` then `./scripts/prepare-release.sh`.
- Update `CHANGELOG.md`, bump `__version__`, create tag `vX.Y.Z`.

## AI Editing Guidelines
- Prefer modular edits in `device_controller.py` and `profile_manager.py`.
- Avoid changing hardware control defaults without explicit user request.
- Keep device operations resilient: check `success` and handle "not found" gracefully.

References:
- Architecture: docs/ARCHITECTURE.md
- Error reference: docs/ERROR_CODES.md
- Troubleshooting: docs/TROUBLESHOOTING.md
- Setup and permissions: docs/SETUP.md
- Refactor plan: docs/REFACTORING_PLAN.md