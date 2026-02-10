## What's New in v1.0.0

### Added
- **Backend plugin architecture**: Priority-based discovery and deduplication supporting both liquidctl and hwmon
- **Motherboard PWM fan control**: Via hwmon with safety floor and writeability checks
- **Profile manager**: Named profiles with auto-save/restore and load/delete UI
- **New documentation**: Architecture, error codes, troubleshooting, and profile management guides

### Changed
- App refactored into focused modules (`device_controller.py`, `profile_manager.py`)
- Device discovery now unified through backend registry
- Status panel aggregates system sensors + device status

### Fixed
- Startup dialogs for missing devices (now gracefully skipped)
- LED preset save issues (now persists sync colors/modes correctly)
- amdgpu read-only PWM errors (filtered out on discovery)

---

**Full Changelog**: https://github.com/amatson97/liquidctl-gui/compare/v0.2.0...v1.0.0