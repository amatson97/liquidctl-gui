# liquidctl-gui

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A small GTK GUI for controlling liquidctl-compatible devices. Dynamically detects and configures supported hardware.

Credit: built on top of https://github.com/liquidctl/liquidctl

## Features
- Dynamic device detection with automatic capability discovery
- LED color control with mode selection (fixed, breathing, pulse, etc.)
- Pump and fan speed control (0-100%)
- Live status monitoring for supported devices
- Device initialization
- Profile save/load for settings persistence

## Requirements
- Python 3
- GTK 3 bindings (python3-gi, gir1.2-gtk-3.0) — installable via your distro package manager

## Setup (recommended)
Run the provided launcher script which will create a virtual environment, install the Python-only prerequisite (`liquidctl`) into it, and check for the GTK system bindings:

```bash
./launch.sh
```

Notes:
- The launcher will create a `.venv` in the repo root and `pip install liquidctl` into it.
- GTK system bindings (`python3-gi` / `gir1.2-gtk-3.0`) are installed via your distro package manager; the launcher can prompt and run `sudo apt-get install` on Debian/Ubuntu systems.
- If you prefer manual setup, create a venv and `pip install liquidctl` as before.

Hardware access notes:

- Some operations require access to kernel hwmon/sysfs nodes. See [docs/SETUP.md](docs/SETUP.md) for udev rules and options to avoid running the GUI as root.

## Run
```
PYTHONPATH=src python -m liquidctl_gui
```

## Tests
```bash
PYTHONPATH=src python -m unittest tests.test_unit
```

### Testing with Simulated Devices
For development and testing without physical hardware, you can use simulated devices:

```bash
LIQUIDCTL_SIMULATE=1 PYTHONPATH=src python -m liquidctl_gui
```

This will use mock devices defined in `tests/mock_devices.py` instead of scanning for real hardware.

## Why GTK
- Native look on Linux desktops without bundling a web stack.
- Solid widgets for a small, responsive hardware control panel.

Notes:
- Some devices require sudo access. If you see permission errors, run with sudo or set up udev rules for your hardware.
- Close NZXT CAM if it is running to avoid device conflicts.

## Configuration
User configuration is stored at ~/.liquidctl-gui/config.json.
- First run builds this file from detected devices.
- Subsequent launches reuse the saved devices and settings.

If present, default.json provides initial values for colors, modes, and speeds.

## How It Works
When liquidctl is installed via pip, the GUI uses the Python API directly to:
- Discover connected devices
- Extract supported color channels, speed channels, and LED modes from drivers
- Build dynamic UI controls for each device's capabilities

This means the GUI automatically supports any device that liquidctl supports, without needing manual configuration.

## Device Notes
- Some devices only support lighting (no status reporting)
- Devices with cooling support report pump/fan RPM and temperatures
- See [liquidctl docs](https://github.com/liquidctl/liquidctl/tree/main/docs) for device-specific details

## Contributing
Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Roadmap
- Additional effect modes per device
- System tray integration
- Startup on boot configuration

## License
MIT License - see [LICENSE](LICENSE) for details
