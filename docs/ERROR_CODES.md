# Error Codes Reference

## Quick Diagnostic Guide

When you see an error, look for these patterns:

| Error Pattern | Category | Common Cause | Solution |
|--------------|----------|--------------|----------|
| `Device not found` | DEVICE_NOT_FOUND | Device disconnected | Reconnect device, click "Detect Devices" |
| `[Errno 22] Invalid argument` | DEVICE_CONTROL | Read-only PWM (amdgpu) | Device now filtered automatically |
| `Permission denied` | PERMISSION | Missing sudo/udev rules | Run `scripts/install_udev_rules.sh` |
| `Failed to initialize` | DEVICE_INIT | Device in use | Close other apps using device |
| `No module named 'liquidctl'` | CONFIG | liquidctl not installed | Run `./launch.sh` to install |

## Error Categories

### 1. DEVICE_NOT_FOUND

**Symptoms:**
- "Device not found: <device name>"
- Device appears in list but won't respond to controls

**Common Causes:**
- Device was unplugged
- Device is in saved config but not connected
- liquidctl library can't detect device

**Handling:**
- Auto-skipped during profile restoration (no error dialog)
- Shows status message "Device <name> not available"
- Continues with other devices

**Fix:**
```bash
# Reconnect device, then:
Menu → Devices → Detect Devices
```

---

### 2. DEVICE_INIT

**Symptoms:**
- "Failed to initialize device"
- "Initialization failed: <error>"

**Common Causes:**
- Device is busy (used by another app)
- Device doesn't support initialization
- Hardware communication timeout

**Handling:**
- Shows error dialog during manual initialization
- Skipped silently during auto-initialization
- Device still appears in list

**Fix:**
```bash
# Close other apps using the device (OpenRGB, etc.)
# Then try initializing again via right-click menu
```

---

### 3. DEVICE_CONTROL (PWM/LED Control Failures)

**Symptoms:**
- "Failed to set <channel> <operation>"
- "[Errno 22] Invalid argument. Ensure PWM is in manual mode"
- LED/fan speed changes don't apply

**Common Causes:**
- **amdgpu**: GPU fan locked in automatic mode (can't be controlled)
- **Permission issues**: No write access to sysfs
- **Invalid parameters**: Color/speed outside valid range

**Handling:**
- Shows error dialog with detailed message
- Operation is not applied
- Device state unchanged

**Specific Cases:**

#### amdgpu Read-Only PWM
```
Error: Failed to set pwm1 speed: [Errno 22] Invalid argument. 
       Ensure PWM is in manual mode (pwm_enable=1)
```
**Cause**: AMD GPU driver doesn't allow manual fan control  
**Fix**: Device now automatically filtered out during detection (v0.6.0+)

#### Permission Denied
```
Error: Failed to set led1 color: [Errno 13] Permission denied
```
**Fix**:
```bash
# Install udev rules for device access
cd liquidctl-gui/scripts
sudo ./install_udev_rules.sh
# Reboot or re-plug device
```

---

### 4. PERMISSION

**Symptoms:**
- "[Errno 13] Permission denied"
- "Cannot write to /sys/..."

**Common Causes:**
- Missing udev rules for USB devices
- Not in required groups (input, plugdev)
- Hwmon sysfs files not writable

**Fix:**
```bash
# For liquidctl USB devices:
cd liquidctl-gui/scripts
sudo ./install_udev_rules.sh

# For hwmon (motherboard fans):
# Usually already accessible, but if not:
sudo chmod 666 /sys/class/hwmon/hwmon*/pwm*
sudo chmod 666 /sys/class/hwmon/hwmon*/pwm*_enable
```

---

### 5. CONFIG

**Symptoms:**
- "Failed to load config. Using defaults."
- "Error saving profile"

**Common Causes:**
- Corrupted JSON file
- Missing ~/.liquidctl-gui directory
- Disk full

**Handling:**
- App continues with default settings
- Error shown to user
- Auto-saves may fail silently

**Fix:**
```bash
# Check config directory
ls -la ~/.liquidctl-gui/

# If corrupted, backup and reset:
mv ~/.liquidctl-gui ~/.liquidctl-gui.backup
# Restart app - will create fresh config
```

---

### 6. PROFILE

**Symptoms:**
- "Failed to load profile: <name>"
- "Error applying profile settings"

**Causes:**
- Profile references disconnected devices
- Invalid color/mode values
- Corrupted profile JSON

**Handling:**
- Partially applied (successful settings saved)
- Errors logged, not shown to user
- Profile load continues despite errors

**Fix:**
```bash
# Edit profile manually:
nano ~/.liquidctl-gui/profiles/myprofile.json

# Or delete and recreate:
rm ~/.liquidctl-gui/profiles/myprofile.json
```

---

## Error Message Format

### Structured Error Format (v0.6.0+)
```
[CATEGORY] Message (device: <name>, channel: <channel>) [operation: <op>] [context]
```

**Example:**
```
[DEVICE_NOT_FOUND] Cannot find device (device: NZXT Kraken X, channel: ring) 
[operation: set_color] [available=x53,amdgpu]
```

### Legacy Error Format
```
Error: <message>
```

---

## Debugging Tips

### Enable Detailed Logging
```bash
# Run with debug logging
cd liquidctl-gui
./launch.sh 2>&1 | tee liquidctl-gui.log
```

### Check System Logs
```bash
# USB device events
dmesg | grep -i usb | tail -20

# Hwmon devices
ls -la /sys/class/hwmon/
cat /sys/class/hwmon/hwmon*/name
```

### Check liquidctl
```bash
# If liquidctl is installed system-wide
liquidctl list
liquidctl --match "NZXT" initialize
liquidctl --match "NZXT" status
```

### Check Permissions
```bash
# Check udev rules
ls -la /etc/udev/rules.d/*liquidctl*

# Check group membership
groups $USER

# Test hwmon write access
echo 128 | sudo tee /sys/class/hwmon/hwmon0/pwm1
```

---

## Common Error Scenarios

### Scenario 1: Startup Errors Gone (v0.6.0+)

**Old behavior**: Error dialogs for disconnected devices on startup  
**New behavior**: Silently skipped, no dialogs  
**Why**: Graceful handling of "not found" errors in profile restoration

### Scenario 2: LED Controls Not Working

**Check:**
1. Is device actually connected? (Check device list)
2. Does device need initialization? (Right-click → Initialize)
3. Does device appear in `liquidctl list`?
4. Are there permission errors in logs?

### Scenario 3: Fan Speed Won't Change

**Check:**
1. Is it an hwmon device or liquidctl device?
2. For hwmon: Is PWM in manual mode? (`cat /sys/class/hwmon/.../pwm1_enable` should be 1)
3. For amdgpu: Device should be filtered out (can't control GPU fans)
4. For liquidctl: Does device support speed control? (Check capabilities)

### Scenario 4: amdgpu Still Showing in List

**Expected**: amdgpu should NOT appear (v0.6.0+)  
**If it does**: Detection filter failed, check logs for "PWM%d doesn't support manual mode"  
**Workaround**: Just don't click on it - it won't break anything

---

## Error Handling Flow

```
Operation Attempted
    ↓
Error Occurred
    ↓
Check Error Type
    ├─ Contains "not found"?
    │     ├─ During auto-init → Log debug, skip silently
    │     ├─ During profile load → Skip, continue with next
    │     └─ During user action → Show status message (not dialog)
    │
    ├─ Contains "permission denied"?
    │     └─ Show error dialog with udev rules suggestion
    │
    └─ Other error?
          └─ Show error dialog with full message
```

---

## Getting Help

When reporting errors, include:

1. **Error message** (exact text from dialog)
2. **Device type** (NZXT Kraken, motherboard pwm, etc.)
3. **Operation** (setting color, changing speed, etc.)
4. **Logs** (run with `./launch.sh 2>&1 | tee log.txt`)
5. **Device list** (what shows in the app)
6. **System info** (Ubuntu version, kernel version)

Example bug report:
```
Error: Failed to set pwm1 speed: [Errno 22] Invalid argument
Device: amdgpu (Radeon RX 6800)
Operation: Moving speed slider to 50%
Logs: [attached]
App version: 0.6.0
System: Ubuntu 24.04, kernel 6.8
```
