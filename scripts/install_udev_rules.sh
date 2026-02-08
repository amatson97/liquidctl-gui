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
TMPFILE=$(mktemp)

cat > "$TMPFILE" <<'EOF'
# Grant read/write to hwmon pwm and sensor nodes for users in group 'liquidctl'
SUBSYSTEM=="hwmon", KERNEL=="hwmon*", ACTION=="add", RUN+="/bin/chgrp liquidctl /sys/class/hwmon/%k/*", RUN+="/bin/chmod g+rw /sys/class/hwmon/%k/*"

# Adjust for hidraw nodes created by specific devices if needed
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1e71", ATTRS{idProduct}=="2007", MODE:="0660", GROUP:="liquidctl"
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

echo "Writing udev rule as root..."
sudo install -m 644 "$TMPFILE" "$RULE_FILE"
rm -f "$TMPFILE"

echo "Ensuring group 'liquidctl' exists..."
sudo groupadd -f liquidctl

echo "Adding current user ($USER) to 'liquidctl' group..."
sudo usermod -aG liquidctl "$USER"

echo "Reloading udev rules and triggering..."
sudo udevadm control --reload
sudo udevadm trigger

echo "Done. You may need to replug affected USB devices and re-login for group membership to take effect."
echo "If you prefer not to add your user to the group, you can run the GUI with sudo (not recommended)."

exit 0
