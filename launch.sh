#!/bin/bash

set -euo pipefail

# Create and activate a recommended virtual environment, install Python prereqs,
# check GTK system bindings and run the app.

WORKDIR=$(cd "$(dirname "$0")" && pwd)
cd "$WORKDIR"

VENV_DIR=.venv
PYTHON=python3
AUTO_YES=0

if [ "${1-}" = "--yes" ] || [ "${1-}" = "-y" ]; then
	AUTO_YES=1
fi

if ! command -v $PYTHON >/dev/null 2>&1; then
	echo "Error: $PYTHON not found. Please install Python 3." >&2
	exit 1
fi

ensure_venv_system_site_packages() {
	if [ ! -f "$VENV_DIR/pyvenv.cfg" ]; then
		return 0
	fi

	if grep -qi '^include-system-site-packages = true$' "$VENV_DIR/pyvenv.cfg"; then
		return 0
	fi

	echo "Recreating $VENV_DIR so the virtualenv can see system GTK bindings."
	rm -rf "$VENV_DIR"
}

ensure_venv_system_site_packages

if [ ! -d "$VENV_DIR" ]; then
	echo "Creating virtual environment in $VENV_DIR (recommended)."
	$PYTHON -m venv --system-site-packages "$VENV_DIR"
fi

# Use venv's python directly; some venv layouts do not include an activation script.
PYTHON="$VENV_DIR/bin/python"
if [ ! -x "$PYTHON" ]; then
	echo "Error: expected virtualenv interpreter at $PYTHON but it was not found." >&2
	echo "Remove $VENV_DIR and rerun this script to recreate the environment." >&2
	exit 1
fi

ensure_pip() {
	if "$PYTHON" -m pip --version >/dev/null 2>&1; then
		return 0
	fi

	echo "Bootstrapping pip inside the virtualenv..."
	if "$PYTHON" -m ensurepip --upgrade >/dev/null 2>&1; then
		return 0
	fi

	if command -v apt-get >/dev/null 2>&1; then
		echo "Installing python3-pip via apt-get so the virtualenv can use pip..."
		sudo apt-get update
		sudo apt-get install -y python3-pip
		if "$PYTHON" -m pip --version >/dev/null 2>&1; then
			return 0
		fi
	fi

	echo "Error: pip is not available in $VENV_DIR and could not be bootstrapped." >&2
	echo "Install python3-pip or recreate the virtualenv, then rerun this script." >&2
	exit 1
}

ensure_python_headers() {
	if "$PYTHON" - <<'PY' >/dev/null 2>&1
import sysconfig
from pathlib import Path
include_dir = Path(sysconfig.get_path("include") or "")
raise SystemExit(0 if (include_dir / "Python.h").exists() else 1)
PY
	then
		return 0
	fi

	echo "Python development headers are missing; installing them is required to build liquidctl dependencies."
	if command -v apt-get >/dev/null 2>&1; then
		python_version="$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
		for package in "python${python_version}-dev" python3-dev; do
			echo "Trying to install $package..."
			if sudo apt-get install -y "$package"; then
				if "$PYTHON" - <<'PY' >/dev/null 2>&1
import sysconfig
from pathlib import Path
include_dir = Path(sysconfig.get_path("include") or "")
raise SystemExit(0 if (include_dir / "Python.h").exists() else 1)
PY
				then
					return 0
				fi
			fi
		done
	fi

	echo "Error: Python.h is missing for $PYTHON, so liquidctl cannot be built." >&2
	echo "Install the matching Python development package for your distro, then rerun this script." >&2
	exit 1
}

ensure_pip
ensure_python_headers
$PYTHON -m pip install --upgrade pip

# Install liquidctl in the venv (recommended for GUI integration)
if ! $PYTHON -c "import liquidctl" >/dev/null 2>&1; then
	echo "Installing liquidctl into virtualenv..."
	$PYTHON -m pip install liquidctl
fi

# Check for GTK Python bindings (system packages)
if ! $PYTHON -c "import gi" >/dev/null 2>&1; then
	echo "Python GTK bindings (python3-gi / gir1.2-gtk-3.0) not found."
	if command -v apt-get >/dev/null 2>&1; then
		if [ "$AUTO_YES" -eq 1 ]; then
			echo "Auto-installing GTK packages via apt-get..."
			sudo apt-get update
			sudo apt-get install -y python3-gi gir1.2-gtk-3.0
		else
			read -p "Install system GTK packages via apt-get now? [y/N]: " ans
			if [ "${ans,,}" = "y" ]; then
				sudo apt-get update
				sudo apt-get install -y python3-gi gir1.2-gtk-3.0
			else
				echo "You can install them later: sudo apt install python3-gi gir1.2-gtk-3.0"
			fi
		fi
	else
		echo "Please install python3-gi and gir1.2-gtk-3.0 using your distro package manager."
	fi
fi

# Check for lm-sensors (for CPU/motherboard temperature monitoring)
if ! command -v sensors >/dev/null 2>&1; then
	echo "lm-sensors not found (optional: enables CPU/motherboard temperature monitoring)."
	if command -v apt-get >/dev/null 2>&1; then
		if [ "$AUTO_YES" -eq 1 ]; then
			echo "Auto-installing lm-sensors via apt-get..."
			sudo apt-get install -y lm-sensors
			echo "Running sensors-detect to configure hardware sensors..."
			sudo sensors-detect --auto
		else
			read -p "Install lm-sensors for system temperature monitoring? [y/N]: " ans
			if [ "${ans,,}" = "y" ]; then
				sudo apt-get install -y lm-sensors
				echo "Running sensors-detect to configure hardware sensors..."
				sudo sensors-detect --auto
			else
				echo "You can install it later: sudo apt install lm-sensors && sudo sensors-detect"
			fi
		fi
	else
		echo "Please install lm-sensors using your distro package manager."
	fi
fi

# Offer to install udev rules so non-root users can write hwmon pwm nodes
RULE_FILE=/etc/udev/rules.d/99-liquidctl.rules
UDEV_SCRIPT="$WORKDIR/scripts/install_udev_rules.sh"
TARGET_USER="${SUDO_USER:-$USER}"
need_udev_install=0
need_relogin=0
known_hidraw_inaccessible=0

is_known_liquidctl_vendor() {
	case "$1" in
		1e71|1b1c|0b05|3842|1044|048d|2516|0c70)
			return 0
			;;
		*)
			return 1
			;;
	esac
}

check_known_hidraw_access() {
	known_hidraw_inaccessible=0
	for hidraw_dev in /dev/hidraw*; do
		[ -e "$hidraw_dev" ] || continue
		vid=$(udevadm info --query=property --name="$hidraw_dev" 2>/dev/null | awk -F= '/^ID_VENDOR_ID=/{print $2; exit}')
		if [ -n "$vid" ] && is_known_liquidctl_vendor "$vid"; then
			if [ ! -r "$hidraw_dev" ] || [ ! -w "$hidraw_dev" ]; then
				known_hidraw_inaccessible=1
				return
			fi
		fi
	done
}

# If rule file missing or group not present or user not a member, offer install
if [ ! -f "$RULE_FILE" ]; then
	need_udev_install=1
fi

if ! getent group liquidctl >/dev/null 2>&1; then
	need_udev_install=1
fi

if ! id -nG "$TARGET_USER" | grep -qw liquidctl >/dev/null 2>&1; then
	need_udev_install=1
fi

# If the user is listed in /etc/group but this login session does not have
# liquidctl in its active groups yet, a re-login is needed.
if getent group liquidctl | grep -Eq "(^|:|,)$TARGET_USER(,|$)"; then
	if ! id -nG "$TARGET_USER" | grep -qw liquidctl >/dev/null 2>&1; then
		need_relogin=1
	fi
fi

# Detect when known supported USB devices exist but are still inaccessible.
check_known_hidraw_access
if [ "$known_hidraw_inaccessible" -eq 1 ]; then
	need_udev_install=1
fi

if [ "$need_udev_install" -eq 1 ]; then
	echo "Note: udev rules / group for non-root hwmon access appear missing or incomplete."
	if [ "$AUTO_YES" -eq 1 ]; then
		if [ -f "$UDEV_SCRIPT" ]; then
			echo "Auto-installing udev rules via $UDEV_SCRIPT"
			if [ -x "$UDEV_SCRIPT" ]; then
				"$UDEV_SCRIPT" --yes
			else
				bash "$UDEV_SCRIPT" --yes
			fi
		else
			echo "Installer script not found at $UDEV_SCRIPT. See docs/SETUP.md for manual steps."
		fi
	else
		read -p "Install udev rules and add user to 'liquidctl' group now? [y/N]: " ans
		if [ "${ans,,}" = "y" ]; then
			if [ -f "$UDEV_SCRIPT" ]; then
				if [ -x "$UDEV_SCRIPT" ]; then
					"$UDEV_SCRIPT"
				else
					bash "$UDEV_SCRIPT"
				fi
			else
				echo "Installer script not found at $UDEV_SCRIPT. See docs/SETUP.md for manual steps."
			fi
		else
			echo "Skipping udev install. You can run: $UDEV_SCRIPT"
		fi
	fi
fi

# Re-check access after potential installer run.
check_known_hidraw_access

if [ "$need_relogin" -eq 1 ]; then
	echo "Notice: '$TARGET_USER' was added to the 'liquidctl' group, but this shell session does not have that group yet."
	echo "Please log out and log back in (or reboot), then run ./launch.sh again."
	if [ "$known_hidraw_inaccessible" -eq 1 ]; then
		echo "Known liquidctl USB devices are still not accessible in this session, so launching now may fail with hidraw open errors."
	fi
fi

if [ "$known_hidraw_inaccessible" -eq 1 ] && [ "$need_relogin" -eq 0 ]; then
	echo "Warning: one or more known liquidctl USB devices are still inaccessible (/dev/hidraw*)."
	echo "Try replugging the USB cooler/controller, then run ./launch.sh again."
fi

# Run the GUI; keep sudo only if necessary for device access
PYTHONPATH=src $PYTHON -m liquidctl_gui
