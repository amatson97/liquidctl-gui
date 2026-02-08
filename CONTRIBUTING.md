# Contributing

Thanks for contributing! This is a small GTK app and feedback is welcome.

## Development Setup

The project includes a launcher script that automates the recommended setup:

```bash
./launch.sh
```

This will create a `.venv`, install `liquidctl` into it, and can prompt to install\
GTK system packages on Debian/Ubuntu. If you prefer manual setup, you can create\
a virtual environment and install `liquidctl` yourself.

## Run
```
PYTHONPATH=src python3 -m liquidctl_gui
```

## Tests
```
PYTHONPATH=src python3 -m unittest tests.test_unit
```

## Issues and PRs
- Please describe your hardware setup and OS version.
- Include logs or error output when relevant.
- Keep PRs small and focused when possible.
