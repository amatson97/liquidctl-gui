"""Config helper mixin for liquidctl-gui."""


class ConfigHelpers:
    def get_config_int(self, key, default):
        value = self.config.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_preset_colors(self):
        presets = self.config.get("preset_colors", [])
        return [(item.get("label", ""), item.get("value", "")) for item in presets]

    def get_speed_presets(self):
        return [int(value) for value in self.config.get("speed_presets", []) if str(value).isdigit()]

    def get_modes(self, device_type):
        return self.config.get("modes", {}).get(device_type, [])

    def get_default_mode(self, device_type):
        default = self.config.get("default_modes", {}).get(device_type)
        modes = self.get_modes(device_type)
        if default in modes:
            return default
        return modes[0] if modes else ""

    def get_modes_with_color(self):
        return set(self.config.get("modes_with_color", []))

    def match_device(self, device_name):
        for rule in self.config.get("match_rules", []):
            contains = rule.get("contains")
            if contains and contains in device_name:
                return rule.get("match", device_name), rule.get("type", "generic")
        return device_name, "generic"
