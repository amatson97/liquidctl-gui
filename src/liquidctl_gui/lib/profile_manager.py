"""
Profile management module for saving, loading, and applying device configurations.

This module extracts profile management logic from the main application window,
handling profile save/load dialogs, profile data application, and state tracking.
"""

import logging
from pathlib import Path
import json

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
except ImportError:
    pass

from .config import (
    save_profile as save_profile_to_disk,
    load_profile as load_profile_from_disk,
    list_profiles,
    delete_profile,
    save_current_state
)


class ProfileManager:
    """
    Manager for profile operations - save, load, apply, and state tracking.
    
    Coordinates profile dialogs, profile data application to devices, and
    maintains profile modification state for the application.
    """
    
    def __init__(self, app_window):
        """
        Initialize profile manager.
        
        Args:
            app_window: Main application window instance
        """
        self.app = app_window
        self._logger = logging.getLogger(__name__)
        
        # Modes that control all LEDs globally (skip individual channel settings)
        self.global_sync_modes = {
            "spectrum-wave", "color-cycle", "rainbow-flow", "super-rainbow",
            "rainbow-pulse", "covering-marquee", "marquee-3", "marquee-4",
            "marquee-5", "marquee-6", "moving-alternating-3", "moving-alternating-4",
            "moving-alternating-5", "alternating-3", "alternating-4", "alternating-5"
        }
        
        # Modes that don't require colors
        self.modes_without_color = {
            "spectrum-wave", "color-cycle", "off", "marquee-3", "marquee-4",
            "marquee-5", "marquee-6", "covering-marquee", "alternating-3",
            "alternating-4", "alternating-5", "moving-alternating-3",
            "moving-alternating-4", "moving-alternating-5", "rainbow-flow",
            "super-rainbow", "rainbow-pulse"
        }
    
    # ========================================================================
    # Profile Saving
    # ========================================================================
    
    def save_profile(self):
        """
        Save current device configuration as a named profile.
        
        Shows dialog to enter profile name and saves current LED/fan/pump
        settings to disk. Handles global sync mode filtering (skips individual
        LEDs when device has global effect active).
        """
        # Find devices with global sync modes
        devices_with_global_sync = set()
        for key, mode in self.app.last_modes.items():
            device, channel = key.split(":", 1)
            if channel == "sync" and mode in self.global_sync_modes:
                devices_with_global_sync.add(device)
        
        # Build profile, filtering out individual LEDs for devices with global sync
        colors = {}
        modes = {}
        
        for key, value in self.app.last_colors.items():
            device, channel = key.split(":", 1)
            # Keep sync channels, or individual LEDs if device doesn't have global sync
            if channel == "sync" or device not in devices_with_global_sync:
                colors[key] = value
        
        for key, value in self.app.last_modes.items():
            device, channel = key.split(":", 1)
            # Keep sync channels, or individual LEDs if device doesn't have global sync
            if channel == "sync" or device not in devices_with_global_sync:
                modes[key] = value
        
        profile = {
            "colors": colors,
            "modes": modes,
            "speeds": self.app.last_speeds  # Speeds don't conflict with sync
        }
        
        # Ask for profile name
        dialog = Gtk.Dialog(
            title="Save Profile",
            parent=self.app,
            flags=0,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        )
        dialog.set_default_size(300, 100)
        
        box = dialog.get_content_area()
        box.set_border_width(10)
        box.set_spacing(10)
        
        box.pack_start(Gtk.Label(label="Profile name:"), False, False, 0)
        entry = Gtk.Entry()
        # Default to active profile name if exists, otherwise "my_profile"
        entry.set_text(self.app.active_profile_name if self.app.active_profile_name else "my_profile")
        entry.set_activates_default(True)
        box.pack_start(entry, False, False, 0)
        
        dialog.set_default_response(Gtk.ResponseType.OK)
        box.show_all()
        
        response = dialog.run()
        profile_name = entry.get_text().strip()
        dialog.destroy()
        
        if response != Gtk.ResponseType.OK or not profile_name:
            return
            
        try:
            # Save to profiles directory
            save_profile_to_disk(profile, profile_name)
            # Also save as current state with profile name
            save_current_state(profile, profile_name)
            # Set as active profile and clear modified flag
            self.app.active_profile_name = profile_name
            self.app.profile_modified = False
            self._update_profile_display()
            self.app.show_info(f"Profile '{profile_name}' saved successfully.")
            self._logger.info("Saved profile '%s'", profile_name)
        except Exception as e:
            self.app.show_error(str(e))
            self._logger.exception("Failed to save profile")
    
    # ========================================================================
    # Profile Loading
    # ========================================================================
    
    def load_profile(self):
        """
        Show profile browser dialog and load selected profile.
        
        Provides profile list with load/delete options. Applied profile
        settings are immediately sent to devices and saved as current state
        for session restore.
        """
        profiles = list_profiles()
        
        if not profiles:
            self.app.show_error("No profiles found. Save a profile first.")
            return
        
        dialog = Gtk.Dialog(
            title="Load Profile",
            parent=self.app,
            flags=0,
            buttons=(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                "Delete", Gtk.ResponseType.REJECT,
                Gtk.STOCK_OPEN, Gtk.ResponseType.OK
            )
        )
        dialog.set_default_size(400, 300)
        
        box = dialog.get_content_area()
        box.set_border_width(10)
        box.set_spacing(10)
        
        box.pack_start(Gtk.Label(label="Select a profile to load:"), False, False, 0)
        
        # Create scrolled window for profile list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(200)
        
        profile_list = Gtk.ListBox()
        profile_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        
        for profile_name in profiles:
            row = Gtk.ListBoxRow()
            row.profile_name = profile_name
            row.add(Gtk.Label(label=profile_name, xalign=0))
            profile_list.add(row)
        
        scroll.add(profile_list)
        box.pack_start(scroll, True, True, 0)
        
        dialog.set_default_response(Gtk.ResponseType.OK)
        box.show_all()
        
        # Select first profile by default
        profile_list.select_row(profile_list.get_row_at_index(0))
        
        while True:
            response = dialog.run()
            
            selected_row = profile_list.get_selected_row()
            if not selected_row:
                dialog.destroy()
                return
                
            profile_name = selected_row.profile_name
            
            if response == Gtk.ResponseType.REJECT:  # Delete
                # Confirm deletion
                confirm = Gtk.MessageDialog(
                    transient_for=dialog,
                    flags=0,
                    message_type=Gtk.MessageType.QUESTION,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text="Delete Profile"
                )
                confirm.format_secondary_text(f"Are you sure you want to delete '{profile_name}'?")
                confirm_response = confirm.run()
                confirm.destroy()
                
                if confirm_response == Gtk.ResponseType.YES:
                    delete_profile(profile_name)
                    self._logger.info("Deleted profile '%s'", profile_name)
                    # Refresh list
                    profile_list.remove(selected_row)
                    profiles.remove(profile_name)
                    if not profiles:
                        self.app.show_info("Profile deleted. No more profiles available.")
                        dialog.destroy()
                        return
                continue  # Stay in dialog
                
            elif response == Gtk.ResponseType.OK:  # Load
                break
            else:  # Cancel
                dialog.destroy()
                return
        
        dialog.destroy()
        
        # Load the selected profile
        try:
            data = load_profile_from_disk(profile_name)
            if not data:
                self.app.show_error(f"Failed to load profile '{profile_name}'.")
                return
            
            self.apply_profile_data(data)
            # Save loaded profile as current state for next session
            save_current_state(data)
            # Set as active profile and clear modified flag
            self.app.active_profile_name = profile_name
            self.app.profile_modified = False
            # Refresh UI to show loaded settings
            self.app._refresh_ui()
            self.app.show_info(f"Profile '{profile_name}' loaded and applied.")
            self._logger.info("Loaded profile '%s'", profile_name)
        except Exception as e:
            self.app.show_error(str(e))
            self._logger.exception("Failed to load profile")
    
    def load_profile_from_path(self, path):
        """
        Load and apply a profile JSON from filesystem path (non-interactive).
        
        Args:
            path: Filesystem path to profile JSON file
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            data = json.loads(Path(path).read_text())
        except Exception as e:
            self._logger.warning("Failed to load profile %s: %s", path, e)
            return False, str(e)

        self.apply_profile_data(data)
        return True, ""
    
    # ========================================================================
    # Profile Application
    # ========================================================================
    
    def apply_profile_data(self, data):
        """
        Apply profile data (colors, modes, speeds) to devices.
        
        4-step application process:
        1. Apply SYNC channels first (set base state for all LEDs)
        2. Apply individual channel modes (skip if device has global sync)
        3. Apply color-only channels (skip if device has global sync)
        4. Apply speeds
        
        Gracefully skips unavailable devices ("not found" errors).
        
        Args:
            data: Profile dictionary with keys: colors, modes, speeds
        """
        # Replace (don't merge) to avoid accumulating old state
        self.app.last_colors = data.get("colors", {}).copy()
        self.app.last_modes = data.get("modes", {}).copy()
        self.app.last_speeds = data.get("speeds", {}).copy()
        
        # Separate sync channels from regular channels and track which devices have global sync
        devices_with_global_sync = set()
        sync_modes = {}
        regular_modes = {}
        
        for key, mode in self.app.last_modes.items():
            device, channel = key.split(":", 1)
            if channel == "sync":
                sync_modes[key] = mode
                # If sync mode is a global effect, mark device to skip individual LEDs
                if mode in self.global_sync_modes:
                    devices_with_global_sync.add(device)
                    self._logger.info("Device %s has global sync mode: %s (will skip individual LEDs)", device, mode)
            else:
                regular_modes[key] = mode
        
        # STEP 1: Apply sync channels FIRST (they set the base state for all LEDs)
        for key, mode in sync_modes.items():
            device, channel = key.split(":", 1)
            color_hex = self.app.last_colors.get(key, "")
            
            try:
                if mode in self.modes_without_color or not color_hex:
                    success, err = self.app.set_led_mode(device, channel, mode)
                    if err and "not found" in err.lower():
                        self._logger.debug("Skipping unavailable device: %s", device)
                        continue
                    self._logger.info("Applied SYNC mode %s to %s", mode, key)
                else:
                    success, err = self.app.set_led_mode_with_color(device, channel, mode, color_hex)
                    if err and "not found" in err.lower():
                        self._logger.debug("Skipping unavailable device: %s", device)
                        continue
                    self._logger.info("Applied SYNC mode %s with color %s to %s", mode, color_hex, key)
            except Exception as e:
                if "not found" in str(e).lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                else:
                    self._logger.warning("Failed to apply sync mode %s for %s: %s", mode, key, e)
        
        # STEP 2: Apply individual channel modes (but skip if device has global sync mode)
        for key, mode in regular_modes.items():
            device, channel = key.split(":", 1)
            
            # Skip individual LEDs if device has a global sync effect active
            if device in devices_with_global_sync:
                self._logger.debug("Skipping individual LED %s (device has global sync effect)", key)
                continue
            
            color_hex = self.app.last_colors.get(key, "")
            
            try:
                if mode in self.modes_without_color or not color_hex:
                    success, err = self.app.set_led_mode(device, channel, mode)
                    if err and "not found" in err.lower():
                        self._logger.debug("Skipping unavailable device: %s", device)
                        continue
                    self._logger.debug("Applied mode %s (no color) to %s", mode, key)
                else:
                    success, err = self.app.set_led_mode_with_color(device, channel, mode, color_hex)
                    if err and "not found" in err.lower():
                        self._logger.debug("Skipping unavailable device: %s", device)
                        continue
                    self._logger.debug("Applied mode %s with color %s to %s", mode, color_hex, key)
            except Exception as e:
                if "not found" in str(e).lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                else:
                    self._logger.warning("Failed to apply mode %s for %s: %s", mode, key, e)

        # STEP 3: Apply colors for channels that have colors but no explicit mode (default to fixed)
        for key, color_hex in self.app.last_colors.items():
            if not color_hex or key in self.app.last_modes:
                continue  # Skip if no color or already processed with mode
            device, channel = key.split(":", 1)
            
            # Skip if device has global sync mode
            if device in devices_with_global_sync:
                self._logger.debug("Skipping color-only LED %s (device has global sync effect)", key)
                continue
            
            try:
                success, err = self.app.set_led_color(device, channel, color_hex)
                if err and "not found" in err.lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                    continue
                self._logger.debug("Applied color %s (fixed mode) to %s", color_hex, key)
            except Exception as e:
                if "not found" in str(e).lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                else:
                    self._logger.warning("Failed to apply color %s for %s: %s", color_hex, key, e)

        # STEP 4: Apply speeds
        for key, speed in self.app.last_speeds.items():
            device, channel = key.split(":", 1)
            try:
                success, err = self.app.set_speed(device, channel, speed)
                if err and "not found" in err.lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                    continue
                self._logger.debug("Applied speed %s to %s", speed, key)
            except Exception as e:
                if "not found" in str(e).lower():
                    self._logger.debug("Skipping unavailable device: %s", device)
                else:
                    self._logger.warning("Failed to apply speed %s for %s: %s", speed, key, e)
    
    # ========================================================================
    # State Management
    # ========================================================================
    
    def auto_save_state(self):
        """
        Automatically save current state for session restore.
        
        Called after every settings change to persist state across sessions.
        Marks profile as modified when changes are detected.
        """
        try:
            profile = {
                "colors": self.app.last_colors,
                "modes": self.app.last_modes,
                "speeds": self.app.last_speeds
            }
            save_current_state(profile, self.app.active_profile_name)
            # Mark profile as modified when settings change
            self.mark_profile_modified()
        except Exception as e:
            self._logger.warning("Failed to auto-save state: %s", e)
    
    def mark_profile_modified(self):
        """Mark the current profile as modified (needs saving)."""
        if not self.app.profile_modified:
            self.app.profile_modified = True
            self._update_profile_display()
    
    def _update_profile_display(self):
        """Update the profile indicator label in UI."""
        if self.app.active_profile_name:
            modified = " *" if self.app.profile_modified else ""
            self.app.profile_label.set_text(f"Profile: {self.app.active_profile_name}{modified}")
        else:
            self.app.profile_label.set_text("No profile loaded")
