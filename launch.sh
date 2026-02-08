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

if [ ! -d "$VENV_DIR" ]; then
	echo "Creating virtual environment in $VENV_DIR (recommended)."
	$PYTHON -m venv --system-site-packages "$VENV_DIR"
fi

# Activate venv for this script
source "$VENV_DIR/bin/activate"
# Use venv's python from now on
PYTHON="$VENV_DIR/bin/python"
$PYTHON -m pip install --upgrade pip

# Install liquidctl in the venv (recommended for GUI integration)
if ! $PYTHON -c "import liquidctl" >/dev/null 2>&1; then
	echo "Installing liquidctl into virtualenv..."
	pip install liquidctl
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

# Offer to install udev rules so non-root users can write hwmon pwm nodes
RULE_FILE=/etc/udev/rules.d/99-liquidctl.rules
UDEV_SCRIPT="$WORKDIR/scripts/install_udev_rules.sh"
need_udev_install=0

# If rule file missing or group not present or user not a member, offer install
if [ ! -f "$RULE_FILE" ]; then
	need_udev_install=1
fi

if ! getent group liquidctl >/dev/null 2>&1; then
	need_udev_install=1
fi

if ! id -nG "$USER" | grep -qw liquidctl >/dev/null 2>&1; then
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

# Run the GUI; keep sudo only if necessary for device access
PYTHONPATH=src $PYTHON -m liquidctl_gui
