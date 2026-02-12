"""
Motherboard PWM fan control via Linux hwmon subsystem.

Provides detection and control of motherboard fan headers through sysfs.
"""

import os
import glob
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple


logger = logging.getLogger(__name__)


class HwmonDevice:
    """Represents a motherboard fan controller accessible via hwmon."""
    
    # Safety: minimum PWM value (0-255 scale) to prevent fans stopping completely
    MIN_PWM_VALUE = 51  # ~20% duty cycle
    
    def __init__(self, hwmon_path: str, name: str, chip_name: str = None):
        self.hwmon_path = Path(hwmon_path)
        self.name = name
        self.chip_name = chip_name or name
        self.description = f"Motherboard: {self.chip_name}"
        self.device_type = "hwmon"  # For config compatibility
        
        # Discover available PWM outputs and fan inputs
        self.pwm_channels = self._discover_pwm_channels()
        self.fan_inputs = self._discover_fan_inputs()
        self.temp_inputs = self._discover_temp_inputs()
        
        # Device capabilities for UI
        self.supports_cooling = len(self.pwm_channels) > 0
        self.supports_lighting = False
        
        # For compatibility with DeviceInfo interface
        self.color_channels = []
        self.color_modes = []
        self.speed_channels = [f"pwm{num}" for num in self.pwm_channels.keys()]
        
        # Match identifier for config persistence
        self.match = f"hwmon:{self.chip_name}"
        
        logger.info(
            "Detected hwmon device: %s with %d PWM outputs, %d fans, %d temp sensors",
            self.chip_name, len(self.pwm_channels), len(self.fan_inputs), len(self.temp_inputs)
        )
    
    def _discover_pwm_channels(self) -> Dict[int, Dict[str, Path]]:
        """Find all PWM outputs (pwm1, pwm2, etc.) and their control files."""
        channels = {}
        for pwm_file in sorted(self.hwmon_path.glob("pwm[0-9]*")):
            if pwm_file.name.endswith("_enable") or "_" in pwm_file.name:
                continue
            
            channel_num = int(pwm_file.name.replace("pwm", ""))
            enable_file = self.hwmon_path / f"pwm{channel_num}_enable"
            
            # Check if we can read the PWM value (permission check)
            try:
                pwm_file.read_text()
                if enable_file.exists():
                    enable_file.read_text()
            except (PermissionError, OSError):
                logger.warning("No read permission for %s, skipping", pwm_file)
                continue
            
            # Check if PWM is writable (some devices like amdgpu may be read-only)
            writable = True
            if enable_file.exists():
                try:
                    current_enable = enable_file.read_text().strip()
                    # Skip if permanently in automatic mode (some GPUs don't support manual)
                    if current_enable == "2":
                        # Try to enable manual mode
                        try:
                            enable_file.write_text("1\n")
                            # Read back to verify it worked
                            verify = enable_file.read_text().strip()
                            if verify == "1":
                                # Success! Switch back to original mode for now
                                enable_file.write_text(f"{current_enable}\n")
                            else:
                                # Write failed or was ignored
                                logger.debug("PWM%d doesn't support manual mode (read-only), skipping", channel_num)
                                writable = False
                        except (PermissionError, OSError):
                            logger.debug("PWM%d is read-only (no write permission), skipping", channel_num)
                            writable = False
                except (PermissionError, OSError):
                    logger.debug("Cannot check PWM%d enable mode, skipping", channel_num)
                    writable = False
            
            if not writable:
                continue
            
            channels[channel_num] = {
                "pwm": pwm_file,
                "enable": enable_file if enable_file.exists() else None,
                "label": self._read_label(f"pwm{channel_num}")
            }
        
        return channels
    
    def _discover_fan_inputs(self) -> Dict[int, Dict[str, Path]]:
        """Find all fan speed inputs (fan1_input, fan2_input, etc.)."""
        inputs = {}
        for fan_file in sorted(self.hwmon_path.glob("fan[0-9]*_input")):
            channel_num = int(fan_file.name.replace("fan", "").replace("_input", ""))
            
            try:
                fan_file.read_text()
            except (PermissionError, OSError):
                continue
            
            inputs[channel_num] = {
                "input": fan_file,
                "label": self._read_label(f"fan{channel_num}")
            }
        
        return inputs
    
    def _discover_temp_inputs(self) -> Dict[int, Dict[str, Path]]:
        """Find all temperature inputs (temp1_input, temp2_input, etc.)."""
        inputs = {}
        for temp_file in sorted(self.hwmon_path.glob("temp[0-9]*_input")):
            channel_num = int(temp_file.name.replace("temp", "").replace("_input", ""))
            
            try:
                temp_file.read_text()
            except (PermissionError, OSError):
                continue
            
            inputs[channel_num] = {
                "input": temp_file,
                "label": self._read_label(f"temp{channel_num}")
            }
        
        return inputs
    
    def _read_label(self, prefix: str) -> Optional[str]:
        """Read human-readable label for a channel if available."""
        label_file = self.hwmon_path / f"{prefix}_label"
        if label_file.exists():
            try:
                return label_file.read_text().strip()
            except (PermissionError, OSError):
                pass
        return None
    
    def initialize(self, **kwargs) -> List[Tuple[str, str, str]]:
        """
        Initialize device by enabling manual PWM control.
        Returns list of (message, value, unit) tuples.
        """
        results = []
        for channel_num, channel_info in self.pwm_channels.items():
            enable_file = channel_info["enable"]
            if enable_file and enable_file.exists():
                try:
                    # Set to manual mode (1 = manual, 2 = automatic/BIOS)
                    enable_file.write_text("1\n")
                    label = channel_info["label"] or f"PWM{channel_num}"
                    results.append((f"{label} mode", "manual", ""))
                    logger.debug("Enabled manual control for %s", label)
                except (PermissionError, OSError) as e:
                    logger.warning("Failed to enable manual control for PWM%d: %s", channel_num, e)
        
        if not results:
            results.append(("Status", "Ready (no PWM enable control)", ""))
        
        return results
    
    def get_status(self) -> List[Tuple[str, str, str]]:
        """
        Get current fan speeds and temperatures.
        Returns list of (metric, value, unit) tuples.
        """
        status = []
        
        # Read fan speeds
        for channel_num, fan_info in self.fan_inputs.items():
            try:
                rpm = int(fan_info["input"].read_text().strip())
                label = fan_info["label"] or f"Fan {channel_num}"
                status.append((label, str(rpm), "rpm"))
            except (ValueError, OSError):
                pass
        
        # Read temperatures
        for channel_num, temp_info in self.temp_inputs.items():
            try:
                # Temperature is in millidegrees Celsius
                temp_millideg = int(temp_info["input"].read_text().strip())
                temp_c = temp_millideg / 1000.0
                label = temp_info["label"] or f"Temp {channel_num}"
                status.append((label, f"{temp_c:.1f}", "°C"))
            except (ValueError, OSError):
                pass
        
        # Read current PWM values
        for channel_num, pwm_info in self.pwm_channels.items():
            try:
                pwm_value = int(pwm_info["pwm"].read_text().strip())
                pwm_percent = int((pwm_value / 255.0) * 100)
                label = pwm_info["label"] or f"PWM {channel_num}"
                status.append((f"{label} duty", str(pwm_percent), "%"))
            except (ValueError, OSError):
                pass
        
        return status
    
    def set_speed_profile(self, channel: str, profile: List[Tuple[int, int]]) -> None:
        """
        Set fan speed. Channel format: "pwm1", "pwm2", etc.
        Profile is a list of [(temperature, speed_percent)] but for now we only use the last speed.
        """
        if not channel.startswith("pwm"):
            raise ValueError(f"Invalid PWM channel: {channel}")
        
        channel_num = int(channel.replace("pwm", ""))
        if channel_num not in self.pwm_channels:
            raise ValueError(f"PWM channel {channel_num} not available")
        
        # Extract the speed from profile (take the last/only entry)
        if not profile:
            raise ValueError("Empty speed profile")
        
        speed_percent = profile[-1][1]  # Get speed from last tuple
        
        # Convert percentage (0-100) to PWM value (0-255)
        pwm_value = int((speed_percent / 100.0) * 255)
        
        # Apply safety minimum
        if pwm_value < self.MIN_PWM_VALUE:
            logger.warning(
                "Requested PWM value %d is below minimum %d, clamping for safety",
                pwm_value, self.MIN_PWM_VALUE
            )
            pwm_value = self.MIN_PWM_VALUE
        
        # Ensure manual mode is enabled first
        enable_file = self.pwm_channels[channel_num]["enable"]
        if enable_file and enable_file.exists():
            try:
                current_mode = enable_file.read_text().strip()
                if current_mode != "1":
                    logger.debug("Enabling manual mode for %s", channel)
                    enable_file.write_text("1\n")
            except (PermissionError, OSError) as e:
                logger.warning("Could not set manual mode for %s: %s", channel, e)
        
        pwm_file = self.pwm_channels[channel_num]["pwm"]
        try:
            pwm_file.write_text(f"{pwm_value}\n")
        except OSError as e:
            # Some drivers (like amdgpu) may have read-only PWM when in automatic mode
            raise OSError(f"{e}. Ensure PWM is in manual mode (pwm_enable=1)") from e
        
        label = self.pwm_channels[channel_num]["label"] or f"PWM{channel_num}"
        logger.info("Set %s to %d%% (PWM=%d)", label, speed_percent, pwm_value)
    
    def disconnect(self, **kwargs):
        """Cleanup on disconnect (placeholder for interface compatibility)."""
        pass
    
    def __str__(self):
        return f"HwmonDevice({self.chip_name})"


def get_device_sysfs_path(hwmon_path: str) -> Optional[str]:
    """
    Get the underlying hardware device path for an hwmon interface.
    Returns canonical device path (e.g., /sys/devices/pci0000:00/.../usb1/1-1)
    """
    try:
        hwmon_dir = Path(hwmon_path)
        # hwmon devices link to their parent device via 'device' symlink
        device_link = hwmon_dir / "device"
        if device_link.exists():
            # Resolve symlink to get actual device path
            real_device = device_link.resolve()
            return str(real_device)
        # Some hwmon devices don't have a device link (virtual sensors)
        return None
    except Exception as e:
        logger.debug("Failed to get device path for %s: %s", hwmon_path, e)
        return None


def find_hwmon_devices(exclude_device_paths: Optional[List[str]] = None) -> List[HwmonDevice]:
    """
    Scan /sys/class/hwmon/ for available fan controllers.
    
    Args:
        exclude_device_paths: List of sysfs device paths to exclude (e.g., devices
                             already controlled by liquidctl). If None, no filtering.
    
    Returns list of HwmonDevice instances.
    """
    devices = []
    hwmon_base = Path("/sys/class/hwmon")
    exclude_device_paths = exclude_device_paths or []
    
    if not hwmon_base.exists():
        logger.debug("hwmon subsystem not available")
        return devices
    
    for hwmon_dir in sorted(hwmon_base.glob("hwmon*")):
        if not hwmon_dir.is_dir():
            continue
        
        # Read device name
        name_file = hwmon_dir / "name"
        if not name_file.exists():
            continue
        
        try:
            name = name_file.read_text().strip()
        except (PermissionError, OSError):
            continue
        
        # Skip temperature-only sensors (not fan controllers)
        skip_names = ["acpitz", "pch_", "nvme", "coretemp", "k10temp", "zenpower"]
        if any(skip in name.lower() for skip in skip_names):
            logger.debug("Skipping non-fan-controller hwmon device: %s", name)
            continue
        
        # Check if this hwmon device is backed by a device we should exclude (e.g., liquidctl device)
        if exclude_device_paths:
            device_path = get_device_sysfs_path(str(hwmon_dir))
            if device_path:
                # Check if device path matches or is a child of any excluded device
                for excluded_path in exclude_device_paths:
                    if device_path.startswith(excluded_path) or excluded_path.startswith(device_path):
                        logger.debug("Skipping hwmon device %s (managed by USB/liquidctl device: %s)", 
                                   name, excluded_path)
                        continue
        
        # Try to get chip name from device/name
        chip_name = name
        device_name_file = hwmon_dir / "device" / "name"
        if device_name_file.exists():
            try:
                chip_name = device_name_file.read_text().strip()
            except (PermissionError, OSError):
                pass
        
        device = HwmonDevice(str(hwmon_dir), name, chip_name)
        
        # Only include devices that actually have PWM outputs
        if device.supports_cooling:
            devices.append(device)
        else:
            logger.debug("Skipping hwmon device %s (no PWM outputs)", name)
    
    return devices


def get_speed_channels(device: HwmonDevice) -> List[str]:
    """Get list of PWM channel names for a hwmon device."""
    channels = []
    for channel_num, channel_info in device.pwm_channels.items():
        label = channel_info["label"] or f"PWM {channel_num}"
        channels.append(f"pwm{channel_num}")
    return channels


def get_speed_channel_labels(device: HwmonDevice) -> Dict[str, str]:
    """Get mapping of PWM channel names to human-readable labels."""
    labels = {}
    for channel_num, channel_info in device.pwm_channels.items():
        channel_name = f"pwm{channel_num}"
        label = channel_info["label"] or f"PWM {channel_num}"
        labels[channel_name] = label
    return labels
