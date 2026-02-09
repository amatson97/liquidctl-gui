"""Config helper mixin for liquidctl-gui (dynamic configuration only)."""


class ConfigHelpers:
    """Helper methods for accessing user-configurable settings.
    
    All device-specific configuration is now discovered dynamically from
    the liquidctl library. This class only handles user preferences like
    window size, color presets, and speed presets.
    """
    
    def get_config_int(self, key, default):
        """Get an integer value from config with fallback."""
        value = self.config.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_preset_colors(self):
        """Get user-configured preset colors."""
        presets = self.config.get("preset_colors", [])
        return [(item.get("label", ""), item.get("value", "")) for item in presets]

    def get_speed_presets(self):
        """Get user-configured speed preset values."""
        return [int(value) for value in self.config.get("speed_presets", []) if str(value).isdigit()]
