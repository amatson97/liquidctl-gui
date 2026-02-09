#!/usr/bin/env bash
set -euo pipefail

# Install udev rules and create a 'liquidctl' group so non-root users
# can access hwmon/pwm nodes used by some drivers. This script must be
# run on the target machine and will use sudo for privileged operations.

AUTO_YES=0
if [ "${1-}" = "--yes" ] || [ "${1-}" = "-y" ]; then
  AUTO_YES=1
fi

RULE_FILE=/etc/udev/rules.d/99-liquidctl.rules
HELPER_SCRIPT=/usr/local/bin/fix-hwmon-permissions
TMPFILE=$(mktemp)

# Create udev rules for liquidctl-supported vendors
echo "Preparing udev rules for liquidctl devices..."
cat > "$TMPFILE" <<'EOF'
# Grant access to hidraw nodes for liquidctl-supported devices
# NZXT
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1e71", MODE:="0660", GROUP:="liquidctl"
# Corsair
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1b1c", MODE:="0660", GROUP:="liquidctl"
# ASUS
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0b05", MODE:="0660", GROUP:="liquidctl"
# EVGA
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="3842", MODE:="0660", GROUP:="liquidctl"
# Gigabyte
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1044", MODE:="0660", GROUP:="liquidctl"
# Cooler Master
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2516", MODE:="0660", GROUP:="liquidctl"
# Aquacomputer
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0c70", MODE:="0660", GROUP:="liquidctl"

# Fix hwmon permissions when devices are added (works for ALL devices)
SUBSYSTEM=="hwmon", ACTION=="add", RUN+="/usr/local/bin/fix-hwmon-permissions /sys%p"
EOF

echo "This will write the udev rule to: $RULE_FILE"
if [ "$AUTO_YES" -eq 0 ]; then
  read -p "Continue and require sudo to write rules and modify groups? [y/N]: " ans
  if [ "${ans,,}" != "y" ]; then
    echo "Aborting. No changes made."
    rm -f "$TMPFILE"
    exit 1
  fi
fi

echo "Creating helper script at $HELPER_SCRIPT..."
sudo tee "$HELPER_SCRIPT" > /dev/null <<'HELPER_EOF'
#!/bin/bash
# Helper script called by udev to fix hwmon permissions
# Sets group ownership and permissions on pwm control files

HWMON_PATH="$1"

if [ -z "$HWMON_PATH" ]; then
    exit 1
fi

# Fix permissions on pwm files (fan/pump control)
for file in "$HWMON_PATH"/pwm[0-9]* ; do
    if [ -e "$file" ]; then
        chgrp liquidctl "$file" 2>/dev/null
        chmod 0660 "$file" 2>/dev/null
    fi
done

# Fix permissions on sensor files (optional - read-only)
for file in "$HWMON_PATH"/temp[0-9]*_input "$HWMON_PATH"/fan[0-9]*_input ; do
    if [ -e "$file" ]; then
        chgrp liquidctl "$file" 2>/dev/null
        chmod 0440 "$file" 2>/dev/null
    fi
done

exit 0
HELPER_EOF

sudo chmod 755 "$HELPER_SCRIPT"

echo "Writing udev rule as root..."
sudo install -m 644 "$TMPFILE" "$RULE_FILE"
rm -f "$TMPFILE"

echo "Ensuring group 'liquidctl' exists..."
sudo groupadd -f liquidctl

echo "Adding current user ($USER) to 'liquidctl' group..."
sudo usermod -aG liquidctl "$USER"

echo "Reloading udev rules and triggering..."
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hwmon

echo "Fixing permissions on existing hwmon devices..."
for hwmon_dev in /sys/class/hwmon/hwmon*; do
  if [ -d "$hwmon_dev" ]; then
    sudo "$HELPER_SCRIPT" "$hwmon_dev" || true
  fi
done

echo "Fixing permissions on existing hidraw devices..."
# Apply permissions to already-connected devices
for hidraw_dev in /dev/hidraw*; do
  if [ -e "$hidraw_dev" ]; then
    # Get vendor ID from device
    vid=$(udevadm info -a "$hidraw_dev" 2>/dev/null | grep -m1 'ATTRS{idVendor}' | cut -d'"' -f2)
    # Check if this vendor is in our rules file
    if [ -n "$vid" ] && grep -q "\"$vid\"" "$RULE_FILE" 2>/dev/null; then
      echo "  Updating $hidraw_dev (vendor: $vid)"
      sudo chgrp liquidctl "$hidraw_dev" 2>/dev/null || true
      sudo chmod 0660 "$hidraw_dev" 2>/dev/null || true
    fi
  fi
done

echo ""
echo "Done! Permissions have been applied."
echo "Verify: ls -la /dev/hidraw* | grep liquidctl"
echo "        ls -la /sys/class/hwmon/hwmon*/pwm*"

exit 0
