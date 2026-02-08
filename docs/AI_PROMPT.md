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

---

## Workflow Summary for AI Assistance

### Branch Management
**Creating a feature branch:**
```bash
git checkout -b feature/your-feature-name
# Work on changes...
git add .
git commit -m "Description of changes"
git push -u origin feature/your-feature-name
```

**Switching between branches:**
```bash
git checkout main           # Switch to main branch
git checkout feature/name   # Switch to existing feature branch
git branch                  # List all local branches
git branch -a               # List all branches (local + remote)
```

**Updating your branch with latest main:**
```bash
git checkout main
git pull
git checkout feature/your-feature-name
git merge main
# Or use rebase: git rebase main
```

### Making Changes
**Standard development workflow:**
1. Create/switch to feature branch
2. Make code changes
3. Run tests: `PYTHONPATH=src python3 -m unittest tests.test_unit`
4. Test the app: `./launch.sh`
5. Commit changes with clear messages
6. Push to your fork or branch

**Commit best practices:**
- Use descriptive commit messages
- Keep commits focused on single changes
- Reference issues if applicable: "Fix #123: Description"

### Pull Requests (PRs)
**For contributors (fork workflow):**
1. Fork the repository on GitHub
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/liquidctl-gui.git`
3. Add upstream: `git remote add upstream https://github.com/amatson97/liquidctl-gui.git`
4. Create feature branch: `git checkout -b feature/name`
5. Make changes, commit, and push to your fork
6. Open PR from your fork to upstream main branch
7. Address review feedback by pushing new commits to the same branch

**For maintainers:**
1. Review PR changes and test locally if needed
2. Merge PR via GitHub UI (squash, merge commit, or rebase)
3. Delete feature branch after merge

### Release Workflow (Maintainers Only)

**Using prepare-release.sh (Recommended):**
```bash
./scripts/prepare-release.sh
```

This interactive wizard will:
1. Prompt for version number (e.g., 0.3.0)
2. Validate version format (semantic versioning)
3. Check for uncommitted changes (requires clean working directory)
4. Run full test suite and abort if tests fail
5. Update version in `src/liquidctl_gui/__init__.py`
6. Create release entry in CHANGELOG.md (opens editor for you)
7. Create git commit with release changes
8. Create annotated git tag (e.g., v0.3.0)
9. Prompt to push changes and tag to GitHub
10. GitHub Actions automatically creates release with CHANGELOG notes

**Manual release steps:**
```bash
# 1. Update version
# Edit src/liquidctl_gui/__init__.py: __version__ = "0.3.0"

# 2. Update CHANGELOG.md with release notes

# 3. Run tests
PYTHONPATH=src python3 -m unittest tests.test_unit

# 4. Commit release
git add src/liquidctl_gui/__init__.py CHANGELOG.md
git commit -m "Release v0.3.0"

# 5. Create and push tag
git tag -a v0.3.0 -m "Release v0.3.0"
git push origin main
git push origin v0.3.0

# 6. GitHub Actions will auto-create the release
```

**Important release notes:**
- Only maintainers with write access can push tags and trigger releases
- Contributors working in forks cannot create releases in the upstream repo
- Always run tests before releasing
- Use semantic versioning: MAJOR.MINOR.PATCH
- GitHub Actions workflow automatically creates releases when tags are pushed
- Release scripts include fork detection to prevent accidental tag creation

**Quick reference commands:**
```bash
# Check current version
grep __version__ src/liquidctl_gui/__init__.py

# View recent tags
git tag -l

# View CHANGELOG
cat CHANGELOG.md

# Pre-release validation
./scripts/pre-release-check.sh
```