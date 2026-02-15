#!/usr/bin/env python3
"""
Liquidctl GUI Controller for supported devices (GTK)
Controls: LED colors, pump speed, fan speed
Recommended: run ./launch.sh to create a virtualenv and install `liquidctl`.
Ensure system GTK bindings (python3-gi, gir1.2-gtk-3.0) are provided by your distro.
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import __version__
from .lib.config import (
    load_config, save_config, save_profile as save_profile_to_disk,
    load_profile as load_profile_from_disk, list_profiles,
    delete_profile, save_current_state, load_current_state
)
from .lib.config_helpers import ConfigHelpers
from .lib.functions import DeviceInfo, LiquidctlCore
from .lib.ui_helpers import UiHelpers
from .lib.hwmon_api import HwmonDevice
from .lib import sensors_api
from .lib.backends import discover_devices, get_all_backends
from .lib.device_controller import DeviceController
from .lib.profile_manager import ProfileManager
from .lib.startup import disable_startup, enable_startup, get_startup_enabled


APP_TITLE = f"Liquidctl Controller v{__version__}"
APP_ID = "com.liquidctl.gui"
WINDOW_WIDTH = 820
WINDOW_HEIGHT = 1010
STATUS_TEXT_HEIGHT = 220
PANED_POSITION = 569  # Default split position between controls and status panel
AUTO_REFRESH_SECONDS = 3  # Status monitoring interval (temps/speeds)
DEFAULT_SPEED = 60
PROFILE_DEFAULT_NAME = "profile.json"

# User-configurable defaults (fully dynamic, no device-specific hardcoding)
DEFAULT_CONFIG = {
    "window": {
        "width": WINDOW_WIDTH,
        "height": WINDOW_HEIGHT,
        "paned_position": PANED_POSITION
    },
    "status_text_height": STATUS_TEXT_HEIGHT,
    "auto_initialize_on_startup": True,
    "launch_on_boot": False,
    "default_speed": DEFAULT_SPEED,
    "speed_presets": [40, 60, 80, 100],
    "log_level": "INFO",
    "preset_colors": [
        {"label": "White", "value": "#f0f8ff"},
        {"label": "Ice Blue", "value": "#4682b4"},
        {"label": "Cyan", "value": "#00ced1"},
        {"label": "Red", "value": "#dc143c"},
        {"label": "Purple", "value": "#8a2be2"}
    ],
    "devices": []  # Populated by dynamic device discovery
}


def _resolve_log_level(config):
    env_level = os.environ.get("LIQUIDCTL_GUI_LOG_LEVEL", "").strip()
    configured_level = str(config.get("log_level", "INFO")).strip()
    level_name = (env_level or configured_level).upper()
    return logging._nameToLevel.get(level_name, logging.INFO)


try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk, GLib
    GTK_AVAILABLE = True
except Exception:
    GTK_AVAILABLE = False


class DevicePlugin:
    def __init__(self, app, device_info):
        self.app = app
        self.device = device_info
        self.status_buffer = getattr(app, "status_buffer", None)

    def build_ui(self, container):
        raise NotImplementedError

    def refresh_status(self):
        # Safety check: don't access buffer if it's None or window is destroyed
        if not self.status_buffer:
            return
        try:
            status, _ = self.app.core.get_status(self.device.match)
            if status:
                # Format numbers to 1 decimal place
                status = re.sub(r'(\d+\.\d{2,})', lambda m: f"{float(m.group(1)):.1f}", status)
            self.status_buffer.set_text(status or "No status available")
        except Exception:
            # Silently ignore errors (window may be closing)
            pass

    def initialize(self):
        result, err = self.app.core.initialize(self.device.match)
        if err:
            # Gracefully skip unavailable devices during auto-init
            if "not found" in err.lower():
                self.app._logger.debug("Skipping initialization of unavailable device: %s", self.device.name)
                self.app.status_label.set_text(f"Device {self.device.name} not available")
            else:
                self.app.show_error(err)
        else:
            self.app.status_label.set_text(f"Initialized {self.device.name}")


class DynamicDevicePlugin(DevicePlugin):
    """Plugin that dynamically builds UI from device capabilities."""

    def build_ui(self, container):
        device = self.device

        # Build color controls for each channel
        if device.supports_lighting and device.color_channels:
            for channel in device.color_channels:
                self.app.add_section_label(container, f"{channel.title()} LED:")
                self.app.add_button(container, "Pick Color", lambda ch=channel: self.app.pick_color(device.match, ch))

                # Preset colors
                preset_row = self.app.add_row(container)
                for label, color_hex in self.app.get_preset_colors():
                    self.app.add_button(preset_row, label, lambda c=color_hex, ch=channel: self.app.apply_preset_color(device.match, ch, c))

                # Mode dropdown (use device's discovered modes)
                if device.color_modes:
                    mode_row = self.app.add_row(container)
                    self.app.add_label(mode_row, f"Mode ({channel}):")
                    default_mode = device.color_modes[0] if device.color_modes else ""
                    mode_combo = self.app.add_combo(mode_row, device.color_modes, default_mode)
                    self.app.add_button(mode_row, "Apply Mode", lambda ch=channel, combo=mode_combo: self.app.apply_mode_dynamic(device.match, ch, combo))

        # Build speed controls for each speed channel
        if device.supports_cooling and device.speed_channels:
            speed_frame = self.app.add_frame(container, "Speed Control (%)")
            scale = self.app.add_scale(speed_frame, 0, 100, self.app.get_saved_speed(device.match, device.speed_channels[0]))

            for channel in device.speed_channels:
                row = self.app.add_row(speed_frame)
                self.app.add_label(row, f"{channel.title()} presets:")
                for preset in self.app.get_speed_presets():
                    self.app.add_button(row, f"{preset}%", lambda p=preset, ch=channel: self.app.apply_speed_preset(device.match, ch, p, scale))

            action_row = self.app.add_row(speed_frame)
            for channel in device.speed_channels:
                self.app.add_button(action_row, f"Apply {channel.title()} Speed", lambda ch=channel: self.app.apply_speed(device.match, ch, int(scale.get_value())))

        self.app.add_separator(container)

    def refresh_status(self):
        # Safety check: don't access buffer if it's None or window is destroyed
        if not self.status_buffer:
            return
        try:
            status, _ = self.app.core.get_status(self.device.match)
            if status:
                # Format numbers to 1 decimal place
                status = re.sub(r'(\d+\.\d{2,})', lambda m: f"{float(m.group(1)):.1f}", status)
                self.status_buffer.set_text(status)
            elif self.device.supports_lighting and not self.device.supports_cooling:
                self.status_buffer.set_text("Lighting only (no status reported by device)")
            else:
                self.status_buffer.set_text("No status available")
        except Exception:
            # Silently ignore errors (window may be closing)
            pass


class HwmonDevicePlugin(DevicePlugin):
    """Plugin for motherboard PWM fan control via hwmon."""
    
    def build_ui(self, container):
        device = self.device
        
        # Import here to avoid circular dependency
        from .lib.hwmon_api import get_speed_channels, get_speed_channel_labels
        
        # Add warning about motherboard fan control
        warning_label = self.app.add_section_label(
            container,
            "⚠️ Motherboard PWM Control - Minimum 20% enforced for safety"
        )
        warning_label.set_markup(
            '<span foreground="#ff6600" weight="bold">⚠️ Motherboard PWM Control</span>\n'
            '<span foreground="#666666" size="small">Minimum 20% duty cycle enforced for safety</span>'
        )
        
        # Get PWM channels from the hwmon device
        channels = get_speed_channels(device)
        channel_labels = get_speed_channel_labels(device)
        
        if not channels:
            self.app.add_section_label(container, "No PWM outputs detected")
            self.app.add_separator(container)
            return
        
        # Create a speed frame for each PWM channel
        for channel in channels:
            label = channel_labels.get(channel, channel)
            speed_frame = self.app.add_frame(container, f"{label} Speed (%)")
            
            # Get saved speed or default to 60%
            saved_speed = self.app.get_saved_speed(device.match, channel)
            scale = self.app.add_scale(speed_frame, 0, 100, saved_speed)
            
            # Preset buttons
            preset_row = self.app.add_row(speed_frame)
            self.app.add_label(preset_row, "Presets:")
            for preset in self.app.get_speed_presets():
                self.app.add_button(
                    preset_row,
                    f"{preset}%",
                    lambda p=preset, ch=channel, s=scale: self.app.apply_speed_preset(device.match, ch, p, s)
                )
            
            # Apply button
            action_row = self.app.add_row(speed_frame)
            self.app.add_button(
                action_row,
                f"Apply {label}",
                lambda ch=channel, s=scale: self.app.apply_hwmon_speed(device.match, ch, int(s.get_value()))
            )
        
        self.app.add_separator(container)
    
    def refresh_status(self):
        """Refresh fan speeds and temperatures from hwmon."""
        if not self.status_buffer:
            return
        try:
            # Get status directly from hwmon device
            status_lines = []
            status_data = self.device.get_status()
            
            for metric, value, unit in status_data:
                status_lines.append(f"{metric:20s} {value:>6s} {unit}")
            
            if status_lines:
                self.status_buffer.set_text("\n".join(status_lines))
            else:
                self.status_buffer.set_text("No status available")
        except Exception as e:
            # Log but don't crash
            logger = logging.getLogger(__name__)
            logger.debug("Error refreshing hwmon status: %s", e)
    
    def initialize(self):
        """Initialize hwmon device by enabling manual PWM control."""
        try:
            results = self.device.initialize()
            if results:
                status_lines = [f"{msg}: {val} {unit}" for msg, val, unit in results]
                self.app.status_label.set_text("; ".join(status_lines))
            else:
                self.app.status_label.set_text(f"Initialized {self.device.name}")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Failed to initialize hwmon device")
            self.app.show_error(f"Failed to initialize {self.device.name}: {str(e)}")


class GenericStatusPlugin(DevicePlugin):
    """Fallback plugin for devices without discoverable capabilities."""
    def build_ui(self, container):
        self.app.add_section_label(container, self.device.name)
        self.app.add_section_label(container, "No controls available for this device type.")
        self.app.add_separator(container)


if GTK_AVAILABLE:
    class LiquidctlWindow(UiHelpers, ConfigHelpers, Gtk.ApplicationWindow):
        def __init__(self, app):
            self.config, self.config_exists, self.config_error = load_config(DEFAULT_CONFIG)

            super().__init__(application=app, title=APP_TITLE)
            window_cfg = self.config.get("window", {})
            width = window_cfg.get("width", WINDOW_WIDTH)
            height = window_cfg.get("height", WINDOW_HEIGHT)
            self.set_default_size(width, height)
            self.set_resizable(True)
            self._last_saved_window = (width, height)
            self._last_saved_paned = window_cfg.get("paned_position", PANED_POSITION)
            self._pending_window_state = None
            self._window_state_save_id = None
            self._window_initialized = False

            logging.basicConfig(
                level=_resolve_log_level(self.config),
                format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S"
            )
            self._logger = logging.getLogger(__name__)
            self._logger.info("=" * 50)
            self._logger.info("Liquidctl GUI starting...")
            self._logger.info("=" * 50)

            self.core = LiquidctlCore()
            if self.core.using_api:
                self._logger.info("Backend: Using liquidctl Python API (direct library access)")
            elif self.core.liquidctl_path:
                self._logger.info("Backend: Using liquidctl CLI at %s", self.core.liquidctl_path)
            else:
                self._logger.warning("Backend: liquidctl not found!")
            self.devices = []
            self.plugins = {}
            self.selected_device = None
            self.refresh_id = None

            self.last_colors = {}
            self.last_modes = {}
            self.last_speeds = {}
            
            # Profile state tracking
            self.active_profile_name = None
            self.profile_modified = False
            
            # Initialize device controller and profile manager
            self.device_controller = DeviceController(self)
            self.profile_manager = ProfileManager(self)

            self._build_ui()
            # Connect cleanup handler
            self.connect("destroy", self._on_window_destroy)
            self.connect("configure-event", self._on_window_configure)
            # Start refresh cycle only after window is realized
            self.connect("realize", self._on_window_realize)
            # Mark window as initialized after it's shown
            self.connect("map-event", self._on_window_mapped)
            self.check_dependencies()
            if self.config_error:
                self.show_error(f"Failed to load config. Using defaults. Details: {self.config_error}")
            # Prefer configured devices if present; otherwise detect.
            if self.config_exists and self.config.get("devices"):
                self.load_devices_from_config()
            else:
                self.detect_devices()

            # Auto-load profile: restore previous session state
            current_state, profile_name = load_current_state()
            if current_state:
                self.profile_manager.apply_profile_data(current_state)
                # Restore the active profile name
                self.active_profile_name = profile_name
                self.profile_modified = False
                if profile_name:
                    self._logger.info("✓ Restored profile: %s", profile_name)
                else:
                    self._logger.info("✓ Restored previous session state")
                # Update display now that UI is built
                GLib.idle_add(self.profile_manager._update_profile_display)

            # Refresh UI to show loaded profile settings
            self._refresh_ui()
            # Note: refresh_status() is called in _on_window_realize() after window is shown

        def _on_window_realize(self, widget):
            """Called when window is realized and ready for display updates."""
            self._logger.debug("Window realized, starting auto-refresh cycle")
            # Now it's safe to start the refresh timer
            self.refresh_status()

        def _build_ui(self):
            root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            root_box.set_border_width(8)
            self.add(root_box)

            # Menu bar
            menubar = Gtk.MenuBar()
            root_box.pack_start(menubar, False, False, 0)

            # File menu
            file_menu = Gtk.Menu()
            file_item = Gtk.MenuItem(label="File")
            file_item.set_submenu(file_menu)
            menubar.append(file_item)

            save_item = Gtk.MenuItem(label="Save Profile...")
            save_item.connect("activate", lambda *_: self.save_profile())
            file_menu.append(save_item)

            load_item = Gtk.MenuItem(label="Load Profile...")
            load_item.connect("activate", lambda *_: self.load_profile())
            file_menu.append(load_item)

            # Devices menu
            devices_menu = Gtk.Menu()
            devices_item = Gtk.MenuItem(label="Devices")
            devices_item.set_submenu(devices_menu)
            menubar.append(devices_item)

            detect_item = Gtk.MenuItem(label="Detect Devices")
            detect_item.connect("activate", lambda *_: self.detect_devices())
            devices_menu.append(detect_item)

            init_all_item = Gtk.MenuItem(label="Initialize All")
            init_all_item.connect("activate", lambda *_: self.initialize_all())
            devices_menu.append(init_all_item)

            # Settings menu
            settings_menu = Gtk.Menu()
            settings_item = Gtk.MenuItem(label="Settings")
            settings_item.set_submenu(settings_menu)
            menubar.append(settings_item)

            prefs_item = Gtk.MenuItem(label="Preferences...")
            prefs_item.connect("activate", lambda *_: self.show_settings())
            settings_menu.append(prefs_item)

            # Help menu
            help_menu = Gtk.Menu()
            help_item = Gtk.MenuItem(label="Help")
            help_item.set_submenu(help_menu)
            menubar.append(help_item)

            about_item = Gtk.MenuItem(label="About")
            about_item.connect("activate", lambda *_: self.show_about())
            help_menu.append(about_item)

            # Status row (no controls bar needed anymore)

            status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            status_row.set_border_width(2)
            root_box.pack_start(status_row, False, False, 0)

            self.status_label = Gtk.Label(label="Ready")
            self.status_label.set_xalign(0.0)
            status_row.pack_start(self.status_label, True, True, 0)
            
            # Profile indicator
            self.profile_label = Gtk.Label(label="No profile loaded")
            self.profile_label.set_xalign(1.0)
            self.profile_label.set_margin_start(10)
            status_row.pack_start(self.profile_label, False, False, 0)

            main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            main_box.set_hexpand(True)
            main_box.set_vexpand(True)
            root_box.pack_start(main_box, True, True, 0)

            device_frame = Gtk.Frame(label="Devices")
            device_frame.set_vexpand(True)
            device_frame.set_size_request(200, -1)  # Fixed width of 200px, auto height
            main_box.pack_start(device_frame, False, False, 0)

            # Add scrolling for device list in case of many devices
            device_scroll = Gtk.ScrolledWindow()
            device_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            device_scroll.set_vexpand(True)
            device_frame.add(device_scroll)

            self.device_list = Gtk.ListBox()
            self.device_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.device_list.connect("row-selected", self.on_device_selected)
            self.device_list.connect("button-press-event", self.on_device_list_button_press)
            device_scroll.add(self.device_list)

            detail_scroll = Gtk.ScrolledWindow()
            detail_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            detail_scroll.set_hexpand(True)
            detail_scroll.set_vexpand(True)
            detail_paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
            detail_paned.set_hexpand(True)
            detail_paned.set_vexpand(True)
            main_box.pack_start(detail_paned, True, True, 0)
            self.detail_paned = detail_paned
            detail_paned.connect("notify::position", self._on_paned_position_changed)

            self.detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.detail_box.set_border_width(6)
            self.detail_box.set_vexpand(True)
            detail_scroll.add(self.detail_box)
            detail_paned.pack1(detail_scroll, resize=True, shrink=True)

            status_frame = Gtk.Frame(label="Status")
            status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            status_box.set_border_width(6)
            status_frame.add(status_box)

            # Remove fixed height restriction - let it be fully responsive
            status_min_height = self.get_config_int("status_text_height", STATUS_TEXT_HEIGHT)
            self.status_text_view, self.status_buffer, self.status_scroller = self.add_status_text(
                status_box,
                height=status_min_height
            )
            detail_paned.pack2(status_frame, resize=True, shrink=True)  # Allow resizing
            
            # Set default paned position to match screenshot layout
            paned_position = self.config.get("window", {}).get("paned_position", PANED_POSITION)
            detail_paned.set_position(int(paned_position))

        def _resize_status_panel_to_content(self):
            if not getattr(self, "status_text_view", None):
                return False
            if not getattr(self, "status_scroller", None):
                return False
            if not getattr(self, "detail_paned", None):
                return False
            if not self.get_window():
                return False

            buffer = self.status_text_view.get_buffer()
            start, end = buffer.get_bounds()
            min_height = self.get_config_int("status_text_height", STATUS_TEXT_HEIGHT)

            if start.equal(end):
                self.status_scroller.set_min_content_height(min_height)
                return False

            rect = self.status_text_view.get_iter_location(end)
            total_height = rect.y + rect.height
            target_height = max(min_height, total_height + 24)

            allocation = self.detail_paned.get_allocation()
            if allocation.height <= 0:
                return False

            max_height = max(100, allocation.height - 100)
            target_height = min(target_height, max_height)
            self.status_scroller.set_min_content_height(int(target_height))
            self.detail_paned.set_position(max(100, allocation.height - int(target_height)))
            return False

        def _save_window_state(self, width=None, height=None, paned_position=None):
            window_cfg = self.config.setdefault("window", {})
            if width is not None:
                window_cfg["width"] = int(width)
            if height is not None:
                window_cfg["height"] = int(height)
            if paned_position is not None:
                window_cfg["paned_position"] = int(paned_position)
            save_config(self.config)

        def _schedule_window_state_save(self, width=None, height=None, paned_position=None):
            if self._pending_window_state is None:
                self._pending_window_state = {}
            if width is not None:
                self._pending_window_state["width"] = int(width)
            if height is not None:
                self._pending_window_state["height"] = int(height)
            if paned_position is not None:
                self._pending_window_state["paned_position"] = int(paned_position)

            if self._window_state_save_id is not None:
                GLib.source_remove(self._window_state_save_id)

            self._window_state_save_id = GLib.timeout_add(200, self._flush_window_state_save)

        def _flush_window_state_save(self):
            if not self._pending_window_state:
                self._window_state_save_id = None
                return False
            self._save_window_state(**self._pending_window_state)
            self._pending_window_state = None
            self._window_state_save_id = None
            return False

        def _on_window_configure(self, widget, event):
            # Ignore configure events until window is fully initialized
            if not self._window_initialized:
                return False
            
            # Use get_size() instead of event dimensions for accuracy
            width, height = self.get_size()
            
            # Only save if change is significant (>5px threshold to avoid window manager drift)
            last_w, last_h = self._last_saved_window
            if abs(width - last_w) <= 5 and abs(height - last_h) <= 5:
                return False
            
            self._last_saved_window = (width, height)
            self._schedule_window_state_save(width=width, height=height)
            return False

        def _on_paned_position_changed(self, paned, _param):
            if not self._window_initialized:
                return
            position = paned.get_position()
            if position == self._last_saved_paned:
                return
            self._last_saved_paned = position
            self._schedule_window_state_save(paned_position=position)
        
        def _on_window_mapped(self, widget, event):
            # Window is now fully shown and positioned, safe to track changes
            self._window_initialized = True
            return False

        def load_devices_from_config(self):
            """Load devices from config and populate with fresh capabilities from discovery."""
            self.devices = []
            self.plugins.clear()

            for child in self.device_list.get_children():
                self.device_list.remove(child)

            devices_cfg = self.config.get("devices", [])
            if not devices_cfg:
                self._logger.info("No devices in config, running detection")
                self.detect_devices()
                return

            # Discover actual devices to get current capabilities
            self._logger.info("Loading %d device(s) from config and refreshing capabilities", len(devices_cfg))
            
            # Use backend system for discovery (automatic deduplication)
            backend_results = discover_devices()
            discovered_map = {}
            
            # Build map of all discovered devices by their match identifier
            for backend_class, devices in backend_results:
                for device in devices:
                    match_key = getattr(device, 'match', getattr(device, 'name', None))
                    if match_key:
                        discovered_map[match_key] = device

            # Match config entries with discovered devices and merge capabilities
            for entry in devices_cfg:
                name = entry.get("name")
                if not name:
                    continue
                match = entry.get("match", name)
                device_type = entry.get("type", "generic")
                
                # Try to find device in discovered map
                device = discovered_map.get(match)
                
                # For hwmon devices, also try matching by chip_name if exact match fails
                if not device and device_type == "hwmon":
                    chip_name = entry.get("chip_name")
                    if chip_name:
                        # Try to find by chip name
                        for dev_match, dev in discovered_map.items():
                            if isinstance(dev, HwmonDevice) and dev.chip_name == chip_name:
                                device = dev
                                self._logger.debug("Matched hwmon device %s by chip_name=%s", name, chip_name)
                                break
                
                if device:
                    self._logger.debug("Loaded device %s from backend", name)
                    # Preserve configured type if set
                    if device_type != "generic" and hasattr(device, 'device_type'):
                        device.device_type = device_type
                else:
                    # Device not found, skip it (don't create ghost devices)
                    self._logger.info("Device %s not discovered, skipping", name)
                    continue
                
                self.devices.append(device)
                row = Gtk.ListBoxRow()
                row.device = device
                # Use description for hwmon devices, name for others
                display_name = device.description if isinstance(device, HwmonDevice) else device.name
                row.add(Gtk.Label(label=display_name, xalign=0))
                self.device_list.add(row)
                self.plugins[device.name] = self.plugin_for_device(device)

            self.device_list.show_all()
            if self.devices:
                self.device_list.select_row(self.device_list.get_row_at_index(0))
                # Save discovered capabilities to config
                self.update_config_devices()
                # Auto-initialize if enabled
                if self.config.get("auto_initialize_on_startup", True):
                    self._logger.info("Auto-initialize scheduled")
                    # Delay initialization significantly to ensure window is fully stable (2 seconds)
                    GLib.timeout_add(2000, self._auto_initialize_devices)

        def update_config_devices(self):
            """Save devices to config with full capabilities."""
            self.config["devices"] = []
            for device in self.devices:
                if isinstance(device, HwmonDevice):
                    # Save hwmon device info (will be re-detected on load)
                    self.config["devices"].append({
                        "name": device.name,
                        "match": device.match,
                        "type": "hwmon",
                        "chip_name": device.chip_name,
                        "supports_cooling": True,
                        "supports_lighting": False,
                    })
                else:
                    # Save liquidctl device info
                    self.config["devices"].append({
                        "name": device.name,
                        "match": device.match,
                        "type": device.device_type,
                        "color_channels": device.color_channels,
                        "speed_channels": device.speed_channels,
                        "color_modes": device.color_modes,
                        "supports_lighting": device.supports_lighting,
                        "supports_cooling": device.supports_cooling,
                    })
            save_config(self.config)

        def run_command(self, cmd):
            return self.core.run_command(cmd)

        def detect_devices(self):
            self._logger.info("[ACTION] Detect Devices clicked")
            
            # Discover devices from all backends (automatic deduplication by priority)
            backend_results = discover_devices()
            
            # Log discovered backends
            for backend_class in get_all_backends():
                caps = backend_class.get_capabilities()
                self._logger.info("Backend available: %s (priority: %d)", caps.name, caps.priority)
            
            # Flatten devices from all backends
            self.devices = []
            for backend_class, devices in backend_results:
                caps = backend_class.get_capabilities()
                self._logger.info("Backend %s found %d device(s)", caps.name, len(devices))
                for device in devices:
                    if isinstance(device, HwmonDevice):
                        self._logger.info("  Hwmon: %s", device.description)
                        self._logger.debug("    PWM channels: %s", list(device.pwm_channels.keys()))
                    else:
                        self._logger.info("  Device: %s", device.name)
                        self._logger.debug("    Color channels: %s", device.color_channels)
                        self._logger.debug("    Speed channels: %s", device.speed_channels)
                        self._logger.debug("    Color modes: %s", device.color_modes[:5] if len(device.color_modes) > 5 else device.color_modes)
                self.devices.extend(devices)
            
            self._logger.info("Total devices: %d", len(self.devices))
            
            self.plugins.clear()

            for child in self.device_list.get_children():
                self.device_list.remove(child)

            if not self.devices:
                row = Gtk.ListBoxRow()
                row.add(Gtk.Label(label="No devices found"))
                self.device_list.add(row)
                self.device_list.show_all()
                self.show_empty_state()
                self.status_label.set_text("No devices detected")
                return

            for device in self.devices:
                row = Gtk.ListBoxRow()
                row.device = device
                # Use description for hwmon devices, name for others
                display_name = device.description if isinstance(device, HwmonDevice) else device.name
                row.add(Gtk.Label(label=display_name, xalign=0))
                self.device_list.add(row)
                self.plugins[device.name] = self.plugin_for_device(device)

            self.device_list.show_all()
            self.device_list.select_row(self.device_list.get_row_at_index(0))
            self.update_config_devices()

        def plugin_for_device(self, device):
            """Select plugin based on discovered device capabilities (fully dynamic)."""
            # Check if this is a hwmon device
            if isinstance(device, HwmonDevice):
                self._logger.debug("Using HwmonDevicePlugin for %s", device.name)
                return HwmonDevicePlugin(self, device)
            elif device.color_channels or device.speed_channels:
                self._logger.debug("Using DynamicDevicePlugin for %s", device.name)
                return DynamicDevicePlugin(self, device)
            # Fallback for devices without discoverable capabilities
            self._logger.debug("Using GenericStatusPlugin for %s (no capabilities discovered)", device.name)
            return GenericStatusPlugin(self, device)

        def show_empty_state(self):
            for child in self.detail_box.get_children():
                self.detail_box.remove(child)
            self.add_section_label(self.detail_box, "No devices detected.")
            self.add_section_label(self.detail_box, "Connect a supported device and click 'Detect Devices'.")
            self.detail_box.show_all()

        def on_device_selected(self, listbox, row):
            if not row or not hasattr(row, "device"):
                return
            device = row.device
            self._logger.debug("[UI] Device selected: %s", device.name)
            self.selected_device = device
            plugin = self.plugins.get(device.name)
            if not plugin:
                return

            for child in self.detail_box.get_children():
                self.detail_box.remove(child)

            plugin.build_ui(self.detail_box)
            self.detail_box.show_all()
            # Status panel now shows all devices, no need to refresh individual device

        def on_device_list_button_press(self, widget, event):
            """Handle right-click on device list to show context menu."""
            if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:  # Right-click
                # Get the row at the click position
                row = self.device_list.get_row_at_y(int(event.y))
                if row and hasattr(row, "device"):
                    # Select the row
                    self.device_list.select_row(row)
                    # Show context menu
                    self.show_device_context_menu(row.device, event)
                return True
            return False

        def show_device_context_menu(self, device, event):
            """Show context menu for device."""
            menu = Gtk.Menu()
            
            init_item = Gtk.MenuItem(label=f"Initialize {device.name}")
            init_item.connect("activate", lambda *_: self.initialize_device(device))
            menu.append(init_item)
            
            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)

        def initialize_device(self, device):
            """Initialize a specific device."""
            self._logger.info("[ACTION] Initialize device: %s", device.name)
            plugin = self.plugins.get(device.name)
            if plugin:
                plugin.initialize()
                self.status_label.set_text(f"Initialized {device.name}")

        def initialize_selected(self):
            if not self.selected_device:
                return
            self._logger.info("[ACTION] Initialize Selected clicked for %s", self.selected_device.name)
            plugin = self.plugins.get(self.selected_device.name)
            if plugin:
                plugin.initialize()
                self.status_label.set_text(f"Initialized {self.selected_device.name}")

        def initialize_all(self):
            self._logger.info("[ACTION] Initialize All clicked (%d devices)", len(self.plugins))
            for plugin in self.plugins.values():
                plugin.initialize()
            self.status_label.set_text("Devices initialized")

        def get_status(self, device_match):
            # `LiquidctlCore.get_status` returns a formatted status string when
            # using the Python API, and (stdout, stderr) when using CLI fallback.
            status, err = self.core.get_status(device_match)
            # If we received a formatted status string, return it; otherwise
            # prefer the error text or an empty string.
            if status:
                return status
            if err:
                return err
            return ""

        def set_led_color(self, device_match, channel, color_hex):
            return self.device_controller.set_led_color(device_match, channel, color_hex)

        def set_led_mode(self, device_match, channel, mode):
            return self.device_controller.set_led_mode(device_match, channel, mode)

        def set_led_mode_with_color(self, device_match, channel, mode, color_hex):
            return self.device_controller.set_led_mode_with_color(device_match, channel, mode, color_hex)

        def set_speed(self, device_match, channel, speed):
            return self.device_controller.set_speed(device_match, channel, speed)

        def refresh_status(self):
            # Safety check: don't refresh if window is destroyed
            if not self.get_window():
                return
            
            # Collect status from all devices with thermal/fan data
            # Order: CPU → Coolers → GPU
            all_status = []
            
            # 1. CPU/System sensors first (lm-sensors)
            sensors_data = sensors_api.get_lm_sensors()
            if sensors_data:
                all_status.append(f"┌─ System Sensors (lm-sensors) ─\n{sensors_data}\n")
            
            # 2. Liquidctl cooling devices (Kraken, etc.)
            for device in self.devices:
                # Only show devices that support cooling (have thermal/fan data)
                if device.supports_cooling:
                    try:
                        # Handle hwmon devices differently
                        if isinstance(device, HwmonDevice):
                            status_data = device.get_status()
                            if status_data:
                                status_lines = [f"{metric:20s} {value:>6s} {unit}" for metric, value, unit in status_data]
                                status = "\n".join(status_lines)
                                all_status.append(f"┌─ {device.description} ─\n{status}\n")
                        else:
                            # Regular liquidctl device
                            status, _ = self.core.get_status(device.match)
                            if status:
                                # Format numbers to 1 decimal place
                                status = re.sub(r'(\d+\.\d{2,})', lambda m: f"{float(m.group(1)):.1f}", status)
                                all_status.append(f"┌─ {device.name} ─\n{status}\n")
                    except Exception:
                        logging.exception("Refresh failed for %s", device.name)
            
            # 3. GPU sensors last (NVIDIA/AMD)
            gpu_data = sensors_api.get_gpu_info()
            if gpu_data:
                all_status.append(f"┌─ GPU Sensors ─\n{gpu_data}\n")
            
            # Update status buffer with all device info (join with blank line separator)
            if all_status and self.status_buffer:
                self.status_buffer.set_text("\n".join(all_status).rstrip())
            elif self.status_buffer:
                self.status_buffer.set_text("No devices with thermal/fan monitoring available")

            if self.status_buffer:
                GLib.idle_add(self._resize_status_panel_to_content)

            # Schedule next refresh for continuous monitoring (cancel any existing timer first)
            if self.refresh_id:
                GLib.source_remove(self.refresh_id)
                self.refresh_id = None
            self.refresh_id = GLib.timeout_add_seconds(AUTO_REFRESH_SECONDS, self._refresh_status_timeout)
            self._logger.debug("Status refreshed, next refresh in %d seconds", AUTO_REFRESH_SECONDS)



        def _refresh_status_timeout(self):
            # Safety check: don't refresh if window is destroyed
            if not self.get_window():
                return False
            self.refresh_status()
            return False

        def pick_color(self, device_match, channel):
            self.device_controller.pick_color(device_match, channel)

        def apply_preset_color(self, device_match, channel, color_hex):
            self.device_controller.apply_preset_color(device_match, channel, color_hex)

        def apply_mode_dynamic(self, device_match, channel, combo):
            """Apply mode using the new core API (for dynamic plugin)."""
            self.device_controller.apply_mode_dynamic(device_match, channel, combo)

        def apply_speed(self, device_match, channel, speed):
            self.device_controller.apply_speed(device_match, channel, speed)

        def apply_speed_preset(self, device_match, channel, speed, scale):
            self.device_controller.apply_speed_preset(device_match, channel, speed, scale)
        
        def apply_hwmon_speed(self, device_match, channel, speed):
            """Apply speed to hwmon (motherboard PWM) device."""
            self.device_controller.apply_hwmon_speed(device_match, channel, speed)

        def save_profile(self):
            self.profile_manager.save_profile()

        def load_profile(self):
            """Show profile browser and load selected profile."""
            self.profile_manager.load_profile()

        def load_profile_from_path(self, path):
            """Load and apply a profile JSON from a given filesystem path (non-interactive)."""
            return self.profile_manager.load_profile_from_path(path)

        def apply_profile_data(self, data):
            """Apply profile data (colors, modes, speeds) to devices."""
            self.profile_manager.apply_profile_data(data)


        def _refresh_ui(self):
            """Refresh the UI to reflect current state (after loading a profile)."""
            # Safety check: don't refresh if window is destroyed
            if not self.get_window():
                return
            
            # Trigger UI rebuild by re-selecting the current device
            if self.selected_device:
                # Get the currently selected row
                selected_row = self.device_list.get_selected_row()
                if selected_row:
                    # Re-trigger selection to rebuild UI
                    self.on_device_selected(self.device_list, selected_row)
            # Also refresh status
            self.refresh_status()
            # Update profile indicator
            self._update_profile_display()

        def _update_profile_display(self):
            """Update the profile indicator label."""
            self.profile_manager._update_profile_display()

        def _mark_profile_modified(self):
            """Mark the current profile as modified."""
            self.profile_manager.mark_profile_modified()

        def _auto_save_state(self):
            """Automatically save current state for session restore."""
            self.profile_manager.auto_save_state()

        def get_saved_speed(self, device_match, channel):
            fallback = str(self.get_config_int("default_speed", DEFAULT_SPEED))
            return int(self.last_speeds.get(f"{device_match}:{channel}", fallback))

        def choose_color(self, title):
            dialog = Gtk.ColorChooserDialog(title=title, parent=self)
            response = dialog.run()
            color = dialog.get_rgba()
            dialog.destroy()
            if response != Gtk.ResponseType.OK:
                return None
            return self.rgba_to_hex(color)

        def rgba_to_hex(self, rgba):
            r = int(rgba.red * 255)
            g = int(rgba.green * 255)
            b = int(rgba.blue * 255)
            return f"#{r:02x}{g:02x}{b:02x}"

        def show_error(self, message):
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Error"
            )
            dialog.format_secondary_text(message)
            dialog.run()
            dialog.destroy()

        def show_info(self, message):
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Info"
            )
            dialog.format_secondary_text(message)
            dialog.run()
            dialog.destroy()

        def show_about(self):
            """Show custom About dialog."""
            dialog = Gtk.Dialog(
                title="About Liquidctl GUI",
                transient_for=self,
                modal=True,
                destroy_with_parent=True
            )
            dialog.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
            dialog.set_default_size(500, 400)
            dialog.set_border_width(0)
            
            # Content box
            content = dialog.get_content_area()
            content.set_spacing(0)
            
            # Header with title and version
            header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            header_box.set_margin_top(30)
            header_box.set_margin_bottom(20)
            header_box.set_margin_start(20)
            header_box.set_margin_end(20)
            
            title_label = Gtk.Label()
            title_label.set_markup('<span size="x-large" weight="bold">Liquidctl GUI</span>')
            title_label.set_halign(Gtk.Align.CENTER)
            header_box.pack_start(title_label, False, False, 0)
            
            version_label = Gtk.Label()
            version_label.set_markup(f'<span size="large">v{__version__}</span>')
            version_label.set_halign(Gtk.Align.CENTER)
            header_box.pack_start(version_label, False, False, 0)
            
            content.pack_start(header_box, False, False, 0)
            
            # Separator
            sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            content.pack_start(sep1, False, False, 0)
            
            # Description section
            desc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            desc_box.set_margin_top(20)
            desc_box.set_margin_bottom(20)
            desc_box.set_margin_start(30)
            desc_box.set_margin_end(30)
            
            desc_label = Gtk.Label()
            desc_label.set_markup(
                '<b>Native GTK control for liquidctl-compatible devices</b>\n\n'
                '• Dynamic device discovery and configuration\n'
                '• Live status monitoring with auto-refresh\n'
                '• Profile management and presets\n'
                '• RGB lighting and cooling control'
            )
            desc_label.set_line_wrap(True)
            desc_label.set_halign(Gtk.Align.START)
            desc_box.pack_start(desc_label, False, False, 0)
            
            content.pack_start(desc_box, False, False, 0)
            
            # Separator
            sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            content.pack_start(sep2, False, False, 0)
            
            # Credits and links section
            credits_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            credits_box.set_margin_top(20)
            credits_box.set_margin_bottom(20)
            credits_box.set_margin_start(30)
            credits_box.set_margin_end(30)
            
            # Credits heading
            credits_heading = Gtk.Label()
            credits_heading.set_markup('<b>Credits</b>')
            credits_heading.set_halign(Gtk.Align.START)
            credits_box.pack_start(credits_heading, False, False, 0)
            
            # Built on liquidctl
            liquidctl_link = Gtk.LinkButton(
                uri="https://github.com/liquidctl/liquidctl",
                label="Built on top of liquidctl"
            )
            liquidctl_link.set_halign(Gtk.Align.START)
            credits_box.pack_start(liquidctl_link, False, False, 0)
            
            # Project link
            project_link = Gtk.LinkButton(
                uri="https://github.com/amatson97/liquidctl-gui",
                label="Project on GitHub"
            )
            project_link.set_halign(Gtk.Align.START)
            credits_box.pack_start(project_link, False, False, 0)
            
            # License
            license_label = Gtk.Label()
            license_label.set_markup('<small>Licensed under MIT License</small>')
            license_label.set_halign(Gtk.Align.START)
            license_label.set_margin_top(10)
            credits_box.pack_start(license_label, False, False, 0)
            
            content.pack_start(credits_box, True, True, 0)
            
            dialog.show_all()
            dialog.run()
            dialog.destroy()

        def show_settings(self):
            """Show settings dialog for user preferences."""
            dialog = Gtk.Dialog(
                title="Settings",
                transient_for=self,
                modal=True,
                destroy_with_parent=True
            )
            dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
            dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
            dialog.set_default_size(420, 200)

            content = dialog.get_content_area()
            content.set_border_width(12)
            content.set_spacing(10)

            startup_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            content.pack_start(startup_row, False, False, 0)
            startup_label = Gtk.Label(label="Apply Profile at Boot")
            startup_label.set_xalign(0)
            startup_row.pack_start(startup_label, True, True, 0)
            startup_toggle = Gtk.CheckButton()
            startup_toggle.set_active(bool(self.config.get("launch_on_boot", False)))
            startup_row.pack_start(startup_toggle, False, False, 0)

            startup_enabled, startup_error = get_startup_enabled()
            if startup_error is None:
                startup_toggle.set_active(startup_enabled)
            else:
                startup_toggle.set_sensitive(False)
                startup_note = Gtk.Label(label=f"Startup service unavailable: {startup_error}")
                startup_note.set_xalign(0)
                startup_note.set_line_wrap(True)
                content.pack_start(startup_note, False, False, 0)

            log_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            content.pack_start(log_row, False, False, 0)
            log_label = Gtk.Label(label="Log level")
            log_label.set_xalign(0)
            log_row.pack_start(log_label, True, True, 0)

            log_levels = ["ERROR", "WARNING", "INFO", "DEBUG"]
            current_level = str(self.config.get("log_level", "INFO")).upper()
            log_combo = Gtk.ComboBoxText()
            for level in log_levels:
                log_combo.append_text(level)
            log_combo.set_active(log_levels.index(current_level) if current_level in log_levels else 2)
            log_row.pack_start(log_combo, False, False, 0)

            note = Gtk.Label(
                label="Changes apply immediately. Environment variable LIQUIDCTL_GUI_LOG_LEVEL overrides this setting."
            )
            note.set_xalign(0)
            note.set_line_wrap(True)
            note.set_margin_top(6)
            content.pack_start(note, False, False, 0)

            dialog.show_all()
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                selected = log_combo.get_active_text() or "INFO"
                self.config["log_level"] = selected
                desired_startup = startup_toggle.get_active()
                if desired_startup != bool(self.config.get("launch_on_boot", False)):
                    if desired_startup:
                        ok, err = enable_startup()
                    else:
                        ok, err = disable_startup()
                    if not ok:
                        self.show_error(err or "Failed to update startup setting")
                    else:
                        self.config["launch_on_boot"] = desired_startup
                save_config(self.config)
                self._apply_log_level()
            dialog.destroy()

        def _apply_log_level(self):
            level = _resolve_log_level(self.config)
            root_logger = logging.getLogger()
            root_logger.setLevel(level)
            for handler in root_logger.handlers:
                handler.setLevel(level)
            self._logger.setLevel(level)

        def _on_window_destroy(self, widget):
            """Cleanup when window is destroyed."""
            # Cancel any pending refresh timer
            if self.refresh_id:
                GLib.source_remove(self.refresh_id)
                self.refresh_id = None
            self._logger.info("Window destroyed, cleanup complete")

        def _auto_initialize_devices(self):
            """Auto-initialize all devices on startup (called via timeout)."""
            # Safety check: don't run if window is being destroyed
            if not self.get_window():
                self._logger.warning("Window not available, skipping auto-init")
                return False
            
            # Extra safety: ensure window is realized and mapped
            if not self.get_realized() or not self.get_mapped():
                self._logger.warning("Window not ready, skipping auto-init")
                return False
            
            try:
                self._logger.info("Starting staggered initialization of %d device(s)", len(self.plugins))
                self.status_label.set_text("Initializing devices...")
                
                # Stagger device initialization to avoid blocking GTK event loop
                # Initialize one device at a time with delays between them
                devices_to_init = list(self.plugins.items())
                self._init_next_device(devices_to_init, 0)
                    
            except Exception:
                self._logger.exception("Auto-initialization failed")
                self.status_label.set_text("Initialization failed")
            return False  # Don't repeat

        def _init_next_device(self, devices_list, index):
            """Initialize devices one at a time with delays (non-blocking)."""
            if not self.get_window():
                return False
                
            if index >= len(devices_list):
                # All devices initialized
                self._logger.info("All devices initialized")
                self.status_label.set_text("Devices initialized")
                
                # Reapply profile after all devices are initialized
                if self.last_colors or self.last_modes or self.last_speeds:
                    GLib.timeout_add(500, self._reapply_profile_after_init)
                return False
            
            # Initialize this device
            name, plugin = devices_list[index]
            try:
                self._logger.info("Initializing device %d/%d: %s", index + 1, len(devices_list), name)
                self.status_label.set_text(f"Initializing {name}... ({index + 1}/{len(devices_list)})")
                plugin.initialize()
            except Exception as e:
                self._logger.exception("Failed to initialize %s", name)
            
            # Schedule next device (300ms delay between devices to let GTK breathe)
            GLib.timeout_add(300, lambda: self._init_next_device(devices_list, index + 1))
            return False

        def _reapply_profile_after_init(self):
            """Reapply loaded profile after initialization (separate callback)."""
            if not self.get_window():
                return False
                
            try:
                self._logger.info("Reapplying profile settings after initialization")
                profile_data = {
                    "colors": self.last_colors,
                    "modes": self.last_modes,
                    "speeds": self.last_speeds
                }
                self.apply_profile_data(profile_data)
                self._logger.info("Profile settings reapplied")
            except Exception:
                self._logger.exception("Failed to reapply profile")
            return False  # Don't repeat

        def check_dependencies(self):
            if self.core.is_available:
                # Show info about which backend is being used
                if self.core.using_api:
                    logging.info("Using liquidctl Python API for device control")
                else:
                    logging.info("Using liquidctl CLI at: %s", self.core.liquidctl_path)
                return

            message = "liquidctl not found"
            details = (
                "Recommended: run ./launch.sh from the project root to create a \n"
                "virtual environment and install the Python prerequisite (liquidctl).\n\n"
                "The launcher can also prompt to install GTK system packages on\n"
                "Debian/Ubuntu systems. If you prefer manual installation, see\n"
                "the README for distro-specific instructions and alternatives.\n\n"
                "If liquidctl is already installed but not found, ensure ~/.local/bin\n"
                "is on PATH or set LIQUIDCTL_BIN to the full path of the binary."
            )

            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=message
            )
            dialog.format_secondary_text(details)
            dialog.run()
            dialog.destroy()



    class LiquidctlGtkApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=APP_ID)

        def do_activate(self):
            win = LiquidctlWindow(self)
            win.show_all()


def main():
    if not GTK_AVAILABLE:
        print("ERROR: GTK is not available. Run ./launch.sh to check/install prerequisites (or install python3-gi and gir1.2-gtk-3.0 via your distro).")
        return 1

    app = LiquidctlGtkApp()
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
