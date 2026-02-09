# Setup and Hardware Access

This application controls two types of devices:

1. **USB devices** (NZXT Kraken, Corsair Commander, etc.) - via liquidctl
2. **Motherboard PWM fans** - directly via Linux hwmon subsystem

Some operations (writing PWM or hwmon controls) require access to kernel sysfs nodes such as `/sys/class/hidraw/.../hwmon/...` and `/sys/class/hwmon/...` which are owned by root. Running the GUI as root is not recommended. Instead prefer one of these options:

- Install udev rules so your user can access the device nodes without sudo
- Add a dedicated group and assign device nodes to that group
- Use `sudo` to run the GUI if you understand the risks

## Example udev rule
Create `/etc/udev/rules.d/99-liquidctl.rules` with contents similar to:

```
# Grant read/write to hwmon pwm and sensor nodes for users in group 'liquidctl'
SUBSYSTEM=="hwmon", KERNEL=="hwmon*", ACTION=="add", RUN+="/bin/chgrp liquidctl /sys/class/hwmon/%k/*", RUN+="/bin/chmod g+rw /sys/class/hwmon/%k/*"

# Adjust for hidraw nodes created by specific devices if needed
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1e71", ATTRS{idProduct}=="2007", MODE:="0660", GROUP:="liquidctl"
```

Adjust `idVendor`/`idProduct` to match your hardware as needed. After adding the rule, reload udev rules and replug the device:

```bash
sudo groupadd -f liquidctl
sudo usermod -aG liquidctl $USER
sudo udevadm control --reload
sudo udevadm trigger
# unplug/replug device or reboot
```

Note: udev rules are system administration tasks. If you prefer not to edit udev rules, run the GUI with `sudo ./launch.sh` (not recommended for general usage).

## Automated install helper
A convenience script is provided to install the example udev rule and add your user to the `liquidctl` group. Run from the project root:

```bash
./scripts/install_udev_rules.sh
# or non-interactive:
./scripts/install_udev_rules.sh --yes
```

This script will write `/etc/udev/rules.d/99-liquidctl.rules`, create the `liquidctl` group (if missing), add your user to it, and reload udev rules. You will still need to replug devices or re-login to pick up group membership.

## Troubleshooting
- If you see `PermissionError` writing to `/sys/.../pwm*` then install udev rules or run as root.
- For temporary access, you can `sudo chmod a+rw /sys/class/hwmon/<...>/pwm1` (not persistent across reboots).

For more detail see your distro's udev documentation.
