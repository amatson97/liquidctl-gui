"""
Device controller module for managing device operations.

This module extracts device control logic from the main application window,
providing a clean separation of concerns between UI and device operations.
"""

import logging
from typing import Optional, Tuple

from .hwmon_api import HwmonDevice


class DeviceController:
    """
    Controller for device operations - handles LED, speed, and mode control.
    
    This class coordinates device operations between the UI and backend APIs,
    managing state updates and error handling for all device control operations.
    """
    
    def __init__(self, app_window):
        """
        Initialize device controller.
        
        Args:
            app_window: Main application window instance (provides access to core, devices, state)
        """
        self.app = app_window
        self._logger = logging.getLogger(__name__)
    
    # ========================================================================
    # Core Device Control Methods
    # ========================================================================
    
    def set_led_color(self, device_match: str, channel: str, color_hex: str) -> Tuple[Optional[str], str]:
        """
        Set LED to fixed color.
        
        Args:
            device_match: Device identifier
            channel: LED channel name
            color_hex: Color in hex format (e.g., "ff0000")
        
        Returns:
            Tuple of (success_marker, error_message)
            success_marker is "" on success, None on failure
        """
        success, err = self.app.core.set_color(device_match, channel, "fixed", color_hex)
        return (success, err)
    
    def set_led_mode(self, device_match: str, channel: str, mode: str) -> Tuple[Optional[str], str]:
        """
        Set LED mode without color.
        
        Args:
            device_match: Device identifier
            channel: LED channel name
            mode: LED mode (e.g., "rainbow", "spectrum-wave")
        
        Returns:
            Tuple of (success_marker, error_message)
        """
        success, err = self.app.core.set_color(device_match, channel, mode, "")
        return (success, err)
    
    def set_led_mode_with_color(self, device_match: str, channel: str, mode: str, color_hex: str) -> Tuple[Optional[str], str]:
        """
        Set LED mode with color.
        
        Args:
            device_match: Device identifier
            channel: LED channel name
            mode: LED mode (e.g., "breathing", "pulse")
            color_hex: Color in hex format
        
        Returns:
            Tuple of (success_marker, error_message)
        """
        success, err = self.app.core.set_color(device_match, channel, mode, color_hex)
        return (success, err)
    
    def set_speed(self, device_match: str, channel: str, speed: int) -> Tuple[Optional[str], str]:
        """
        Set fan/pump speed.
        
        Args:
            device_match: Device identifier
            channel: Speed channel name
            speed: Speed percentage (0-100)
        
        Returns:
            Tuple of (success_marker, error_message)
        """
        success, err = self.app.core.set_speed(device_match, channel, speed)
        return (success, err)
    
    # ========================================================================
    # User Interaction Methods
    # ========================================================================
    
    def pick_color(self, device_match: str, channel: str) -> None:
        """
        Interactive color picker for LED channel.
        
        Opens color picker dialog and applies selected color.
        Updates state and saves configuration on success.
        
        Args:
            device_match: Device identifier
            channel: LED channel name
        """
        self._logger.debug("[ACTION] Pick Color clicked for %s:%s", device_match, channel)
        hex_color = self.app.choose_color("Pick Color")
        if not hex_color:
            self._logger.debug("[ACTION] Color picker cancelled")
            return
        
        self._logger.info("[ACTION] Setting color %s on %s:%s", hex_color, device_match, channel)
        success, stderr = self.set_led_color(device_match, channel, hex_color)
        
        if not success:
            friendly = self.app.core.friendly_error(stderr)
            # Silently skip unavailable devices
            if friendly and "not found" in friendly.lower():
                self.app.status_label.set_text(f"Device {device_match} not available")
                return
            if friendly:
                self.app.show_error(friendly)
            return
        
        self.app.last_colors[f"{device_match}:{channel}"] = hex_color
        self.app.last_modes[f"{device_match}:{channel}"] = "fixed"
        self.app._auto_save_state()
        self.app.status_label.set_text(f"{channel} set to {hex_color}")
    
    def apply_preset_color(self, device_match: str, channel: str, color_hex: str) -> None:
        """
        Apply preset color to LED channel.
        
        Args:
            device_match: Device identifier
            channel: LED channel name
            color_hex: Preset color in hex format
        """
        self._logger.info("[ACTION] Preset color %s clicked for %s:%s", color_hex, device_match, channel)
        success, stderr = self.set_led_color(device_match, channel, color_hex)
        
        if not success:
            friendly = self.app.core.friendly_error(stderr)
            # Silently skip unavailable devices
            if friendly and "not found" in friendly.lower():
                self.app.status_label.set_text(f"Device {device_match} not available")
                return
            if friendly:
                self.app.show_error(friendly)
            return
        
        self.app.last_colors[f"{device_match}:{channel}"] = color_hex
        self.app.last_modes[f"{device_match}:{channel}"] = "fixed"
        self.app._auto_save_state()
        self.app.status_label.set_text(f"{channel} set to {color_hex}")
    
    def apply_mode_dynamic(self, device_match: str, channel: str, combo) -> None:
        """
        Apply LED mode from dropdown selection.
        
        Handles modes that require colors by prompting user if needed.
        
        Args:
            device_match: Device identifier
            channel: LED channel name
            combo: GTK ComboBox containing mode selection
        """
        mode = combo.get_active_text()
        self._logger.info("[ACTION] Apply Dynamic Mode '%s' for %s:%s", mode, device_match, channel)
        
        color_key = f"{device_match}:{channel}"
        last_color = self.app.last_colors.get(color_key)

        # Modes that typically need a color
        modes_needing_color = {"fixed", "breathing", "pulse", "fading", "flash", "double-flash"}

        if mode in modes_needing_color:
            if not last_color:
                last_color = self.app.choose_color(f"Pick Color for {mode}")
            if not last_color:
                self.app.show_error("Pick a color first for this mode.")
                return

        success, err = self.app.core.set_color(device_match, channel, mode, last_color or "")
        
        if not success:
            # Silently skip unavailable devices
            err_msg = self.app.core.friendly_error(err) or err
            if "not found" in err_msg.lower():
                self.app.status_label.set_text(f"Device {device_match} not available")
                return
            self.app.show_error(err_msg)
            return

        if last_color:
            self.app.last_colors[color_key] = last_color
        self.app.last_modes[color_key] = mode
        self.app._auto_save_state()
        self.app.status_label.set_text(f"{channel} mode set to {mode}")
    
    def apply_speed(self, device_match: str, channel: str, speed: int) -> None:
        """
        Apply fan/pump speed from slider.
        
        Args:
            device_match: Device identifier
            channel: Speed channel name
            speed: Speed percentage (0-100)
        """
        self._logger.info("[ACTION] Apply Speed %d%% for %s:%s", speed, device_match, channel)
        success, stderr = self.set_speed(device_match, channel, speed)
        
        if not success:
            friendly = self.app.core.friendly_error(stderr)
            # Silently skip unavailable devices
            if friendly and "not found" in friendly.lower():
                self.app.status_label.set_text(f"Device {device_match} not available")
                return
            if friendly:
                self.app.show_error(friendly)
            return
        
        self.app.last_speeds[f"{device_match}:{channel}"] = str(speed)
        self.app._auto_save_state()
        self.app.status_label.set_text(f"{channel} set to {speed}%")
    
    def apply_speed_preset(self, device_match: str, channel: str, speed: int, scale) -> None:
        """
        Apply preset speed from button click.
        
        Handles both liquidctl and hwmon devices.
        
        Args:
            device_match: Device identifier
            channel: Speed channel name
            speed: Preset speed percentage
            scale: GTK Scale widget to update
        """
        self._logger.info("[ACTION] Speed preset %d%% clicked for %s:%s", speed, device_match, channel)
        
        # Check if it's an hwmon device and use appropriate method
        is_hwmon = any(isinstance(d, HwmonDevice) and d.match == device_match for d in self.app.devices)
        if is_hwmon:
            self.apply_hwmon_speed(device_match, channel, speed)
            scale.set_value(speed)
            return
        
        success, stderr = self.set_speed(device_match, channel, speed)
        
        if not success:
            friendly = self.app.core.friendly_error(stderr)
            # Silently skip unavailable devices
            if friendly and "not found" in friendly.lower():
                self.app.status_label.set_text(f"Device {device_match} not available")
                return
            if friendly:
                self.app.show_error(friendly)
            return
        
        scale.set_value(speed)
        self.app.last_speeds[f"{device_match}:{channel}"] = str(speed)
        self.app._auto_save_state()
        self.app.status_label.set_text(f"{channel} set to {speed}%")
    
    def apply_hwmon_speed(self, device_match: str, channel: str, speed: int) -> None:
        """
        Apply speed to hwmon (motherboard PWM) device.
        
        Args:
            device_match: Device identifier
            channel: PWM channel name
            speed: Speed percentage (0-100)
        """
        self._logger.info("[ACTION] Apply hwmon speed %d%% for %s:%s", speed, device_match, channel)
        
        # Find the hwmon device
        device = None
        for d in self.app.devices:
            if isinstance(d, HwmonDevice) and d.match == device_match:
                device = d
                break
        
        if not device:
            self.app.show_error(f"Device not found: {device_match}")
            return
        
        try:
            # Set speed using hwmon API (it expects a profile list of [(temp, speed)])
            device.set_speed_profile(channel, [(0, speed)])
            self.app.last_speeds[f"{device_match}:{channel}"] = str(speed)
            self.app._auto_save_state()
            self.app.status_label.set_text(f"{channel} set to {speed}%")
        except Exception as e:
            self._logger.error("Failed to set hwmon speed: %s", e)
            self.app.show_error(f"Failed to set speed: {e}")
