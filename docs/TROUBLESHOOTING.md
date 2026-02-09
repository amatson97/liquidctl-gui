# Troubleshooting Guide

## Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| Error dialogs on startup | Fixed in v0.6.0+ (auto-skips unavailable devices) |
| LED controls don't work | Device might not be initialized - right-click → Initialize |
| amdgpu fan control error | Fixed in v0.6.0+ (amdgpu auto-filtered) |
| "Device not found" | Click Menu → Devices → Detect Devices |
| Permission denied | Run `scripts/install_udev_rules.sh` |
| App won't start | Run `./launch.sh` (creates venv, installs deps) |

---

## Detailed Troubleshooting

### 1. App Won't Start

**Symptoms:**
- Nothing happens when running `./launch.sh`
- Python import errors
- GTK errors

**Diagnostics:**
```bash
# Check Python version (need 3.8+)
python3 --version

# Check GTK bindings
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk"

# Check if virtual environment exists
ls -la .venv/
```

**Solutions:**

#### Missing GTK Bindings
```bash
# Ubuntu/Debian
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0

# Fedora
sudo dnf install python3-gobject gtk3

# Arch
sudo pacman -S python-gobject gtk3
```

#### Virtual Environment Issues
```bash
# Remove and recreate
rm -rf .venv
./launch.sh --yes
```

---

### 2. No Devices Detected

**Symptoms:**
- "No devices found" message
- Empty device list

**Diagnostics:**
```bash
# Check if liquidctl library is installed
cd liquidctl-gui
source .venv/bin/activate
python3 -c "from liquidctl.driver import find_liquidctl_devices; print(list(find_liquidctl_devices()))"

# Check hwmon devices
ls -la /sys/class/hwmon/
for dev in /sys/class/hwmon/hwmon*; do 
    echo "$dev: $(cat $dev/name 2>/dev/null)"; 
done

# Check USB devices
lsusb | grep -iE "nzxt|corsair|gigabyte|asus"
```

**Solutions:**

#### liquidctl Devices Not Found
```bash
# Ensure device is connected
lsusb

# Try manual liquidctl detection
liquidctl list
# If "command not found", liquidctl isn't installed
# If lists devices, library should work too

# Check for permission issues
sudo liquidctl list
# If works with sudo, you need udev rules
```

#### Hwmon Devices Not Found
```bash
# Check what's available
find /sys/class/hwmon -name "pwm*" ! -name "*_*"

# Check if writable
for pwm in /sys/class/hwmon/hwmon*/pwm1; do
    if [ -f "$pwm" ]; then
        echo -n "$pwm: "
        [ -w "$pwm" ] && echo "writable" || echo "read-only"
    fi
done
```

---

### 3. Device Detected But Controls Don't Work

**Symptoms:**
- Device appears in list
- Clicking buttons does nothing OR shows errors
- Status says "Device not available"

**Diagnostics:**
```bash
# Enable debug logging
cd liquidctl-gui
./launch.sh 2>&1 | grep -E "ERROR|WARNING|set_color|set_speed"
# Now try the control and watch the output
```

**Common Causes:**

#### Device Not Initialized
**Symptom**: First control attempt after app start fails  
**Fix**: Right-click device → Initialize

#### Device Disconnected
**Symptom**: Was working, now "Device not available"  
**Fix**: Unplug and replug device, then Menu → Devices → Detect Devices

#### Wrong Device Selected
**Symptom**: Clicking controls for different device  
**Fix**: Click the device name in left panel first

---

### 4. Permission Errors

**Symptoms:**
- "Permission denied" errors
- Works with `sudo ./launch.sh` but not without

**Diagnostics:**
```bash
# Check which files need access
ls -la /dev/bus/usb/*/*  # USB devices
ls -la /sys/class/hwmon/*/pwm*  # Hwmon devices

# Check udev rules
ls -la /etc/udev/rules.d/ | grep liquidctl

# Check group membership
groups $USER
```

**Solutions:**

#### Install Udev Rules (Recommended)
```bash
cd liquidctl-gui/scripts
sudo ./install_udev_rules.sh
# Replug devices or reboot
```

#### Manual Fix (Temporary)
```bash
# For USB devices (temporary, lost on reboot)
sudo chmod 666 /dev/bus/usb/*/*

# For hwmon (temporary)
sudo chmod 666 /sys/class/hwmon/hwmon*/pwm*
sudo chmod 666 /sys/class/hwmon/hwmon*/pwm*_enable
```

#### Add User to Groups
```bash
sudo usermod -aG input,plugdev $USER
# Log out and back in
```

---

### 5. Profile Issues

**Symptoms:**
- Profile won't load
- Settings not saved
- "Error saving profile"

**Diagnostics:**
```bash
# Check profile directory
ls -la ~/.liquidctl-gui/profiles/

# Check current profile
cat ~/.liquidctl-gui/current_profile.json

# Check main config
cat ~/.liquidctl-gui/config.json

# Validate JSON
python3 -m json.tool ~/.liquidctl-gui/current_profile.json
```

**Solutions:**

#### Corrupted Profile
```bash
# Backup current config
cp -r ~/.liquidctl-gui ~/.liquidctl-gui.backup

# Remove problematic profile
rm ~/.liquidctl-gui/profiles/broken_profile.json

# Or reset everything
rm -rf ~/.liquidctl-gui
# App will create fresh config on next start
```

#### Profile References Missing Devices
This is normal! The app now handles this gracefully:
- Old behavior: Error dialogs
- New behavior (v0.6.0+): Silently skips missing devices

---

### 6. High CPU Usage / Freezing

**Symptoms:**
- App becomes unresponsive
- High CPU usage
- Long delays when clicking

**Diagnostics:**
```bash
# Monitor app
top -p $(pgrep -f liquidctl-gui)

# Check for device communication issues
./launch.sh 2>&1 | grep -E "timeout|Timeout"
```

**Common Causes:**

#### Status Refresh Loop
**Symptom**: CPU usage spikes every 3 seconds  
**Cause**: Device status query hangs  
**Fix**: Disable problematic device or increase refresh interval

#### Too Many Devices
**Symptom**: Slow when many devices connected  
**Fix**: Normal - each device queried sequentially

---

### 7.amdgpu Fan Control Error (FIXED in v0.6.0+)

**Old Issue:**
```
Error: Failed to set pwm1 speed: [Errno 22] Invalid argument. 
       Ensure PWM is in manual mode (pwm_enable=1)
```

**Cause:** AMD GPU drivers don't allow manual fan control (read-only PWM)

**Fix:** amdgpu devices are now automatically filtered out during detection. You should **not** see amdgpu in your device list anymore.

**If amdgpu still appears:**
```bash
# Check version
python3 -c "from liquidctl_gui import __version__; print(__version__)"
# Should be 0.6.0 or higher

# Update if needed
cd liquidctl-gui
git pull
./launch.sh
```

---

### 8. Startup Error Dialogs (FIXED in v0.6.0+)

**Old Issue:**
- Error dialogs for "Device not found" at startup
- Had to click "OK" multiple times

**Fix:** Graceful error handling now implemented:
- Missing devices silently skipped
- No error dialogs during profile restoration
- Status message shown instead: "Device <name> not available"

---

## Advanced Diagnostics

### Enable Full Debug Logging

Create `~/.liquidctl-gui/debug_mode.flag`:
```bash
touch ~/.liquidctl-gui/debug_mode.flag
```

Then run:
```bash
cd liquidctl-gui
./launch.sh 2>&1 | tee debug.log
```

### Check Backend Discovery

```bash
# Test liquidctl backend
python3 << 'EOF'
from liquidctl_gui.lib.functions import LiquidctlCore
core = LiquidctlCore()
devices = core.find_devices()
print(f"Found {len(devices)} liquidctl devices:")
for d in devices:
    print(f"  - {d.name}")
EOF

# Test hwmon backend
python3 << 'EOF'
from liquidctl_gui.lib.hwmon_api import find_hwmon_devices
devices = find_hwmon_devices()
print(f"Found {len(devices)} hwmon devices:")
for d in devices:
    print(f"  - {d.chip_name} ({len(d.pwm_channels)} PWM channels)")
EOF
```

### Test Device Control Directly

```bash
# Test liquidctl device
python3 << 'EOF'
from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI
api = LiquidctlAPI()
api.find_devices()
print("Devices:", list(api._device_map.keys()))

# Try to initialize
result, err = api.initialize("NZXT Kraken X (X53, X63 or X73)")
print(f"Result: {result}")
print(f"Error: {err}")
EOF

# Test hwmon device
echo "Writing 128 (50%) to PWM1..."
echo 128 | sudo tee /sys/class/hwmon/hwmon0/pwm1
```

---

## Getting Help

### Before Asking for Help

1. **Update to latest version**
   ```bash
   cd liquidctl-gui
   git pull
   ./launch.sh
   ```

2. **Collect logs**
   ```bash
   ./launch.sh 2>&1 | tee error.log
   # Reproduce the issue
   # Then press Ctrl+C
   ```

3. **Check system info**
   ```bash
   uname -a                    # Kernel version
   lsb_release -a             # OS version
   python3 --version          # Python version
   ```

### Information to Include in Bug Reports

1. Error message (exact text)
2. Steps to reproduce
3. Logs (from `./launch.sh 2>&1 | tee error.log`)
4. Device list (what appears in the app)
5. System info (OS, kernel, Python version)
6. Output of `liquidctl list` (if liquidctl installed)

### Where to Ask

- GitHub Issues: https://github.com/liquidctl/liquidctl-gui/issues
- Include logs and system info

---

## Known Issues

### amdgpu PWM Control
**Status**: Fixed in v0.6.0  
**Issue**: AMD GPU fans can't be controlled (driver limitation)  
**Fix**: amdgpu automatically filtered out

### Error Dialogs on Startup
**Status**: Fixed in v0.6.0  
**Issue**: Showed errors for unavailable devices  
**Fix**: Graceful error handling implemented

### Window Size Creep
**Status**: Fixed in v0.5.0  
**Issue**: Window slowly grew larger each startup  
**Fix**: Added initialization flag and 5px threshold

---

## Prevention Tips

1. **Don't run multiple tools simultaneously**
   - Close OpenRGB, iCUE, etc. before using liquidctl-gui
   - Devices can only be controlled by one app at a time

2. **Use udev rules instead of sudo**
   - Proper: `./install_udev_rules.sh`
   - Not recommended: `sudo ./launch.sh`

3. **Back up profiles before major changes**
   ```bash
   cp -r ~/.liquidctl-gui ~/.liquidctl-gui.backup
   ```

4. **Keep app updated**
   ```bash
   cd liquidctl-gui && git pull && ./launch.sh
   ```

5. **Monitor logs during issues**
   ```bash
   ./launch.sh 2>&1 | tee liquidctl-gui.log
   ```
