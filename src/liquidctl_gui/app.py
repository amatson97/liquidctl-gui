#!/usr/bin/env python3
"""
Liquidctl GUI Controller for supported devices (GTK)
Controls: LED colors, pump speed, fan speed
Recommended: run ./launch.sh to create a virtualenv and install `liquidctl`.
Ensure system GTK bindings (python3-gi, gir1.2-gtk-3.0) are provided by your distro.
"""

import json
import logging
import shutil
from pathlib import Path

from .lib.config import load_config, save_config
from .lib.config_helpers import ConfigHelpers
from .lib.functions import DeviceInfo, LiquidctlCore
from .lib.ui_helpers import UiHelpers


APP_TITLE = "Liquidctl Controller"
APP_ID = "com.liquidctl.gui"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 680
STATUS_TEXT_HEIGHT = 220
AUTO_REFRESH_SECONDS = 5
DEFAULT_SPEED = 60
PROFILE_DEFAULT_NAME = "profile.json"

DEFAULT_CONFIG = {
    "window": {
        "width": WINDOW_WIDTH,
        "height": WINDOW_HEIGHT
    },
    "status_text_height": STATUS_TEXT_HEIGHT,
    "auto_refresh_seconds": AUTO_REFRESH_SECONDS,
    "auto_refresh_enabled": True,
    "default_speed": DEFAULT_SPEED,
    "speed_presets": [40, 60, 80, 100],
    "preset_colors": [
        {"label": "White", "value": "#f0f8ff"},
        {"label": "Ice Blue", "value": "#4682b4"},
        {"label": "Cyan", "value": "#00ced1"},
        {"label": "Red", "value": "#dc143c"},
        {"label": "Purple", "value": "#8a2be2"}
    ],
    "default_modes": {
        "gigabyte": "fixed",
        "kraken": "fixed"
    },
    "modes": {
        "kraken": ["fixed", "breathing", "pulse", "fading", "spectrum-wave", "off"],
        "gigabyte": ["fixed", "pulse", "flash", "double-flash", "color-cycle", "off"]
    },
    "modes_with_color": ["breathing", "pulse", "fading", "flash", "double-flash"],
    "match_rules": [
        {"contains": "Gigabyte RGB Fusion", "match": "Gigabyte RGB Fusion", "type": "gigabyte"},
        {"contains": "Kraken", "match": "kraken", "type": "kraken"}
    ],
    "devices": []
}


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
        if not self.status_buffer:
            return
        status, _ = self.app.core.get_status(self.device.match)
        self.status_buffer.set_text(status or "No status available")

    def initialize(self):
        result, err = self.app.core.initialize(self.device.match)
        if err:
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
        if not self.status_buffer:
            return
        status, _ = self.app.core.get_status(self.device.match)
        if status:
            self.status_buffer.set_text(status)
        elif self.device.supports_lighting and not self.device.supports_cooling:
            self.status_buffer.set_text("Lighting only (no status reported by device)")
        else:
            self.status_buffer.set_text("No status available")


class GenericStatusPlugin(DevicePlugin):
    def build_ui(self, container):
        self.app.add_section_label(container, self.device.name)
        self.app.add_section_label(container, "No controls available for this device type.")
        self.app.add_separator(container)


class GigabyteRGBFusionPlugin(DevicePlugin):
    def build_ui(self, container):
        self.app.build_color_controls(
            container=container,
            section_label="LED Color (Sync):",
            device_match=self.device.match,
            channel="sync",
            mode_label="Mode (Sync):",
            device_type="gigabyte"
        )

        self.app.add_button(container, "LED4 Off (Power LED)", lambda: self.app.apply_mode_value(self.device.match, "led4", "off"))

        self.app.add_separator(container)

    def refresh_status(self):
        if not self.status_buffer:
            return
        status, _ = self.app.core.get_status(self.device.match)
        self.status_buffer.set_text(status or "Lighting only (no status reported by device)")


class KrakenXPlugin(DevicePlugin):
    """Plugin for NZXT Kraken X (X53/X63/X73) devices.
    
    Note: Kraken X only supports pump speed control. Radiator fans are 
    PWM-controlled by the motherboard, not the AIO unit.
    """
    def __init__(self, app, device_info):
        super().__init__(app, device_info)
        self.speed_scale = None

    def build_ui(self, container):
        self.app.build_color_controls(
            container=container,
            section_label="Logo LED:",
            device_match=self.device.match,
            channel="logo",
            mode_label="Mode (Logo):",
            device_type="kraken"
        )

        self.app.build_color_controls(
            container=container,
            section_label="Ring LED:",
            device_match=self.device.match,
            channel="ring",
            mode_label="Mode (Ring):",
            device_type="kraken"
        )

        # Kraken X only supports pump speed - fans are motherboard PWM
        speed_frame = self.app.add_frame(container, "Pump Speed (%)")
        self.speed_scale = self.app.add_scale(speed_frame, 0, 100, self.app.get_saved_speed(self.device.match, "pump"))
        self.app.build_speed_controls(speed_frame, self.device.match, self.speed_scale, channels=["pump"])

        self.app.add_separator(container)


if GTK_AVAILABLE:
    class LiquidctlWindow(UiHelpers, ConfigHelpers, Gtk.ApplicationWindow):
        def __init__(self, app):
            self.config, self.config_exists, self.config_error = load_config(DEFAULT_CONFIG)

            super().__init__(application=app, title=APP_TITLE)
            window_cfg = self.config.get("window", {})
            width = window_cfg.get("width", WINDOW_WIDTH)
            height = window_cfg.get("height", WINDOW_HEIGHT)
            self.set_size_request(width, height)
            self.set_resizable(True)

            logging.basicConfig(
                level=logging.DEBUG,
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
            self.auto_refresh_enabled = bool(self.config.get("auto_refresh_enabled", True))

            self.last_colors = {}
            self.last_modes = {}
            self.last_speeds = {}

            self._build_ui()
            self.check_dependencies()
            if self.config_error:
                self.show_error(f"Failed to load config. Using defaults. Details: {self.config_error}")
            # Prefer configured devices if present; otherwise detect.
            if self.config_exists and self.config.get("devices"):
                self.load_devices_from_config()
            else:
                self.detect_devices()

            # Auto-load a profile if present in the user's config directory or project root.
            user_profile = Path.home() / ".liquidctl-gui" / "example.json"
            project_profile = Path(__file__).resolve().parents[2] / "example.json"
            profile_loaded = False
            if user_profile.exists():
                ok, msg = self.load_profile_from_path(user_profile)
                profile_loaded = ok
                if not ok:
                    self._logger.info("Could not auto-load profile from %s: %s", user_profile, msg)
            elif project_profile.exists():
                ok, msg = self.load_profile_from_path(project_profile)
                profile_loaded = ok
                if not ok:
                    self._logger.info("Could not auto-load profile from %s: %s", project_profile, msg)

            if profile_loaded:
                self.show_info("Profile auto-loaded from disk.")
            self.refresh_status()

        def _build_ui(self):
            root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            root_box.set_border_width(8)
            self.add(root_box)

            control_frame = Gtk.Frame(label="Controls")
            root_box.pack_start(control_frame, False, False, 0)
            controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            controls.set_border_width(6)
            control_frame.add(controls)

            self.add_button(controls, "Detect Devices", self.detect_devices)
            self.add_button(controls, "Initialize Selected", self.initialize_selected)
            self.add_button(controls, "Initialize All", self.initialize_all)
            self.add_button(controls, "Refresh Now", self.refresh_status)

            self.auto_refresh_check = Gtk.CheckButton(label="Auto-refresh")
            self.auto_refresh_check.set_active(self.auto_refresh_enabled)
            self.auto_refresh_check.connect("toggled", self.toggle_auto_refresh)
            controls.pack_start(self.auto_refresh_check, False, False, 0)

            self.add_button(controls, "Save Profile", self.save_profile)
            self.add_button(controls, "Load Profile", self.load_profile)

            status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            status_row.set_border_width(2)
            root_box.pack_start(status_row, False, False, 0)

            self.status_label = Gtk.Label(label="Ready")
            self.status_label.set_xalign(0.0)
            status_row.pack_start(self.status_label, True, True, 0)

            main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            main_box.set_hexpand(True)
            main_box.set_vexpand(True)
            root_box.pack_start(main_box, True, True, 0)

            device_frame = Gtk.Frame(label="Devices")
            device_frame.set_vexpand(True)
            main_box.pack_start(device_frame, False, False, 0)

            self.device_list = Gtk.ListBox()
            self.device_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.device_list.connect("row-selected", self.on_device_selected)
            device_frame.add(self.device_list)
            self.device_list.set_vexpand(True)

            detail_scroll = Gtk.ScrolledWindow()
            detail_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            detail_scroll.set_hexpand(True)
            detail_scroll.set_vexpand(True)
            detail_paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
            detail_paned.set_hexpand(True)
            detail_paned.set_vexpand(True)
            main_box.pack_start(detail_paned, True, True, 0)

            self.detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.detail_box.set_border_width(6)
            self.detail_box.set_vexpand(True)
            detail_scroll.add(self.detail_box)
            detail_paned.pack1(detail_scroll, resize=True, shrink=True)

            status_frame = Gtk.Frame(label="Status")
            status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            status_box.set_border_width(6)
            status_frame.add(status_box)

            status_height = self.config.get("status_text_height", STATUS_TEXT_HEIGHT)
            self.status_buffer = self.add_status_text(status_box, height=status_height)
            detail_paned.pack2(status_frame, resize=False, shrink=False)

        def load_devices_from_config(self):
            self.devices = []
            self.plugins.clear()

            for child in self.device_list.get_children():
                self.device_list.remove(child)

            devices_cfg = self.config.get("devices", [])
            if not devices_cfg:
                row = Gtk.ListBoxRow()
                row.add(Gtk.Label(label="No devices configured"))
                self.device_list.add(row)
                self.device_list.show_all()
                self.show_empty_state()
                self.status_label.set_text("No devices configured")
                return

            for entry in devices_cfg:
                name = entry.get("name")
                if not name:
                    continue
                match = entry.get("match", name)
                device_type = entry.get("type", "generic")
                device = DeviceInfo(name=name, match=match, device_type=device_type)
                self.devices.append(device)
                row = Gtk.ListBoxRow()
                row.device = device
                row.add(Gtk.Label(label=device.name, xalign=0))
                self.device_list.add(row)
                self.plugins[device.name] = self.plugin_for_device(device)

            self.device_list.show_all()
            self.device_list.select_row(self.device_list.get_row_at_index(0))
            # Ensure the core / API has performed device discovery so that
            # subsequent status queries can map configured device descriptions
            # to actual device instances. This keeps the configured device
            # list but populates the underlying API device map.
            try:
                self._logger.debug("Performing background device discovery to populate API map")
                self.core.find_devices()
            except Exception:
                self._logger.exception("Failed to prime device discovery after loading config")

        def update_config_devices(self):
            self.config["devices"] = [
                {"name": device.name, "match": device.match, "type": device.device_type}
                for device in self.devices
            ]
            save_config(self.config)

        def run_command(self, cmd):
            return self.core.run_command(cmd)

        def detect_devices(self):
            self._logger.info("[ACTION] Detect Devices clicked")
            self._logger.info("Scanning for liquidctl-compatible devices...")
            self.devices = self.core.find_devices()
            self._logger.info("Found %d device(s)", len(self.devices))
            for d in self.devices:
                self._logger.info("  Device: %s", d.name)
                self._logger.debug("    Color channels: %s", d.color_channels)
                self._logger.debug("    Speed channels: %s", d.speed_channels)
                self._logger.debug("    Color modes: %s", d.color_modes[:5] if len(d.color_modes) > 5 else d.color_modes)
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
                row.add(Gtk.Label(label=device.name, xalign=0))
                self.device_list.add(row)
                self.plugins[device.name] = self.plugin_for_device(device)

            self.device_list.show_all()
            self.device_list.select_row(self.device_list.get_row_at_index(0))
            self.update_config_devices()

        def plugin_for_device(self, device):
            # If device has discovered capabilities, use dynamic plugin
            if device.color_channels or device.speed_channels:
                self._logger.debug("Using DynamicDevicePlugin for %s", device.name)
                return DynamicDevicePlugin(self, device)
            # Legacy fallback for devices loaded from config without capabilities
            if device.device_type == "gigabyte" or "Gigabyte RGB Fusion" in device.name:
                self._logger.debug("Using GigabyteRGBFusionPlugin for %s", device.name)
                return GigabyteRGBFusionPlugin(self, device)
            if device.device_type == "kraken" or "Kraken" in device.name:
                self._logger.debug("Using KrakenXPlugin for %s", device.name)
                return KrakenXPlugin(self, device)
            self._logger.debug("Using GenericStatusPlugin for %s", device.name)
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
            plugin.refresh_status()

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
            success, err = self.core.set_color(device_match, channel, "fixed", color_hex)
            return ("" if success else None, err)

        def set_led_mode(self, device_match, channel, mode):
            success, err = self.core.set_color(device_match, channel, mode, "")
            return ("" if success else None, err)

        def set_led_mode_with_color(self, device_match, channel, mode, color_hex):
            success, err = self.core.set_color(device_match, channel, mode, color_hex)
            return ("" if success else None, err)

        def set_speed(self, device_match, channel, speed):
            success, err = self.core.set_speed(device_match, channel, speed)
            return ("" if success else None, err)

        def refresh_status(self):
            for name, plugin in self.plugins.items():
                try:
                    plugin.refresh_status()
                except Exception:
                    logging.exception("Refresh failed for %s", name)

            if self.auto_refresh_enabled:
                interval = self.get_config_int("auto_refresh_seconds", AUTO_REFRESH_SECONDS)
                self.refresh_id = GLib.timeout_add_seconds(interval, self._refresh_status_timeout)

        def _refresh_status_timeout(self):
            self.refresh_status()
            return False

        def pick_color(self, device_match, channel):
            self._logger.debug("[ACTION] Pick Color clicked for %s:%s", device_match, channel)
            hex_color = self.choose_color("Pick Color")
            if not hex_color:
                self._logger.debug("[ACTION] Color picker cancelled")
                return
            self._logger.info("[ACTION] Setting color %s on %s:%s", hex_color, device_match, channel)
            _, stderr = self.set_led_color(device_match, channel, hex_color)
            friendly = self.core.friendly_error(stderr)
            if friendly:
                self.show_error(friendly)
                return
            self.last_colors[f"{device_match}:{channel}"] = hex_color
            self.last_modes[f"{device_match}:{channel}"] = "fixed"
            self.status_label.set_text(f"{channel} set to {hex_color}")

        def apply_preset_color(self, device_match, channel, color_hex):
            self._logger.info("[ACTION] Preset color %s clicked for %s:%s", color_hex, device_match, channel)
            _, stderr = self.set_led_color(device_match, channel, color_hex)
            friendly = self.core.friendly_error(stderr)
            if friendly:
                self.show_error(friendly)
                return
            self.last_colors[f"{device_match}:{channel}"] = color_hex
            self.last_modes[f"{device_match}:{channel}"] = "fixed"
            self.status_label.set_text(f"{channel} set to {color_hex}")

        def apply_mode(self, device_match, channel, combo):
            mode = combo.get_active_text()
            self._logger.info("[ACTION] Apply Mode '%s' clicked for %s:%s", mode, device_match, channel)
            color_key = f"{device_match}:{channel}"
            last_color = self.last_colors.get(color_key)

            if mode == "fixed":
                if not last_color:
                    last_color = self.choose_color("Pick Color for Fixed Mode")
                if not last_color:
                    self.show_error("Pick a color first for fixed mode.")
                    return
                _, stderr = self.set_led_color(device_match, channel, last_color)
            elif mode in self.get_modes_with_color():
                if not last_color:
                    last_color = self.choose_color(f"Pick Color for {mode}")
                if not last_color:
                    self.show_error("Pick a color first for this mode.")
                    return
                _, stderr = self.set_led_mode_with_color(device_match, channel, mode, last_color)
            else:
                _, stderr = self.set_led_mode(device_match, channel, mode)

            friendly = self.core.friendly_error(stderr)
            if friendly:
                self.show_error(friendly)
                return

            if last_color:
                self.last_colors[color_key] = last_color
            self.last_modes[color_key] = mode
            self.status_label.set_text(f"{channel} mode set to {mode}")

        def apply_mode_value(self, device_match, channel, mode):
            self._logger.info("[ACTION] Apply mode value '%s' for %s:%s", mode, device_match, channel)
            _, stderr = self.set_led_mode(device_match, channel, mode)
            friendly = self.core.friendly_error(stderr)
            if friendly:
                self.show_error(friendly)
                return
            self.last_modes[f"{device_match}:{channel}"] = mode
            self.status_label.set_text(f"{channel} mode set to {mode}")

        def apply_mode_dynamic(self, device_match, channel, combo):
            """Apply mode using the new core API (for dynamic plugin)."""
            mode = combo.get_active_text()
            self._logger.info("[ACTION] Apply Dynamic Mode '%s' for %s:%s", mode, device_match, channel)
            color_key = f"{device_match}:{channel}"
            last_color = self.last_colors.get(color_key)

            # Modes that typically need a color
            modes_needing_color = {"fixed", "breathing", "pulse", "fading", "flash", "double-flash"}

            if mode in modes_needing_color:
                if not last_color:
                    last_color = self.choose_color(f"Pick Color for {mode}")
                if not last_color:
                    self.show_error("Pick a color first for this mode.")
                    return

            success, err = self.core.set_color(device_match, channel, mode, last_color or "")
            if not success:
                self.show_error(self.core.friendly_error(err) or err)
                return

            if last_color:
                self.last_colors[color_key] = last_color
            self.last_modes[color_key] = mode
            self.status_label.set_text(f"{channel} mode set to {mode}")

        def apply_speed(self, device_match, channel, speed):
            self._logger.info("[ACTION] Apply Speed %d%% for %s:%s", speed, device_match, channel)
            _, stderr = self.set_speed(device_match, channel, speed)
            friendly = self.core.friendly_error(stderr)
            if friendly:
                self.show_error(friendly)
                return
            self.last_speeds[f"{device_match}:{channel}"] = str(speed)
            self.status_label.set_text(f"{channel} set to {speed}%")

        def apply_speed_preset(self, device_match, channel, speed, scale):
            self._logger.info("[ACTION] Speed preset %d%% clicked for %s:%s", speed, device_match, channel)
            _, stderr = self.set_speed(device_match, channel, speed)
            friendly = self.core.friendly_error(stderr)
            if friendly:
                self.show_error(friendly)
                return
            scale.set_value(speed)
            self.last_speeds[f"{device_match}:{channel}"] = str(speed)
            self.status_label.set_text(f"{channel} set to {speed}%")

        def toggle_auto_refresh(self, button):
            self.auto_refresh_enabled = button.get_active()
            self.config["auto_refresh_enabled"] = self.auto_refresh_enabled
            save_config(self.config)
            if not self.auto_refresh_enabled and self.refresh_id:
                GLib.source_remove(self.refresh_id)
                self.refresh_id = None
            elif self.auto_refresh_enabled and not self.refresh_id:
                self.refresh_status()

        def save_profile(self):
            profile = {
                "colors": self.last_colors,
                "modes": self.last_modes,
                "speeds": self.last_speeds
            }
            path = self.choose_file("Save Profile", Gtk.FileChooserAction.SAVE, PROFILE_DEFAULT_NAME)
            if not path:
                return
            try:
                Path(path).write_text(json.dumps(profile, indent=2))
                self.show_info("Profile saved successfully.")
            except Exception as e:
                self.show_error(str(e))

        def load_profile(self):
            path = self.choose_file("Load Profile", Gtk.FileChooserAction.OPEN)
            if not path:
                return
            try:
                data = json.loads(Path(path).read_text())
            except Exception as e:
                self.show_error(str(e))
                return

            self.last_colors.update(data.get("colors", {}))
            self.last_modes.update(data.get("modes", {}))
            self.last_speeds.update(data.get("speeds", {}))

            for key, color_hex in self.last_colors.items():
                if not color_hex:
                    continue
                device, channel = key.split(":", 1)
                self.set_led_color(device, channel, color_hex)

            for key, mode in self.last_modes.items():
                device, channel = key.split(":", 1)
                self.set_led_mode(device, channel, mode)

            for key, speed in self.last_speeds.items():
                device, channel = key.split(":", 1)
                self.set_speed(device, channel, speed)

            self.show_info("Profile loaded and applied.")

        def load_profile_from_path(self, path):
            """Load and apply a profile JSON from a given filesystem path (non-interactive)."""
            try:
                data = json.loads(Path(path).read_text())
            except Exception as e:
                self._logger.warning("Failed to load profile %s: %s", path, e)
                return False, str(e)

            self.last_colors.update(data.get("colors", {}))
            self.last_modes.update(data.get("modes", {}))
            self.last_speeds.update(data.get("speeds", {}))

            for key, color_hex in self.last_colors.items():
                if not color_hex:
                    continue
                device, channel = key.split(":", 1)
                try:
                    self.set_led_color(device, channel, color_hex)
                except Exception as e:
                    self._logger.warning("Failed to apply color %s for %s: %s", color_hex, key, e)

            for key, mode in self.last_modes.items():
                device, channel = key.split(":", 1)
                try:
                    self.set_led_mode(device, channel, mode)
                except Exception as e:
                    self._logger.warning("Failed to apply mode %s for %s: %s", mode, key, e)

            for key, speed in self.last_speeds.items():
                device, channel = key.split(":", 1)
                try:
                    self.set_speed(device, channel, speed)
                except Exception as e:
                    self._logger.warning("Failed to apply speed %s for %s: %s", speed, key, e)

            return True, ""

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
