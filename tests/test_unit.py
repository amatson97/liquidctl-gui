import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from liquidctl_gui.lib import config as config_module
from liquidctl_gui.lib.config_helpers import ConfigHelpers
from liquidctl_gui.lib.functions import LiquidctlCore


class DummyConfig(ConfigHelpers):
    def __init__(self, config):
        self.config = config


class TestLiquidctlCore(unittest.TestCase):
    def test_build_commands(self):
        core = LiquidctlCore(liquidctl_path="liquidctl")
        self.assertEqual(
            core.build_init_cmd("kraken"),
            ["sudo", "liquidctl", "--match", "kraken", "initialize"]
        )
        self.assertEqual(
            core.build_status_cmd("kraken"),
            ["sudo", "liquidctl", "--match", "kraken", "status"]
        )
        self.assertEqual(
            core.build_set_color_cmd("kraken", "ring", "#00ced1"),
            ["sudo", "liquidctl", "--match", "kraken", "set", "ring", "color", "fixed", "#00ced1"]
        )
        self.assertEqual(
            core.build_set_mode_cmd("kraken", "logo", "breathing"),
            ["sudo", "liquidctl", "--match", "kraken", "set", "logo", "color", "breathing"]
        )
        self.assertEqual(
            core.build_set_speed_cmd("kraken", "pump", 60),
            ["sudo", "liquidctl", "--match", "kraken", "set", "pump", "speed", "60"]
        )

    def test_parse_list_output(self):
        sample = """
Device #0: Gigabyte RGB Fusion 2.0 8297 Controller (IT8297BX-GBX570)
Device #1: NZXT Kraken X (X53, X63 or X73)
Some unrelated line
Device #2: Some Other Device
"""
        names = LiquidctlCore.parse_list_output(sample)
        self.assertEqual(
            names,
            [
                "Gigabyte RGB Fusion 2.0 8297 Controller (IT8297BX-GBX570)",
                "NZXT Kraken X (X53, X63 or X73)",
                "Some Other Device"
            ]
        )

    def test_friendly_error(self):
        self.assertIn("Sudo password required", LiquidctlCore.friendly_error("sudo: a password is required"))
        self.assertIn("Permission denied", LiquidctlCore.friendly_error("Permission denied"))
        self.assertEqual(LiquidctlCore.friendly_error("some other error"), "some other error")


class TestConfigHelpers(unittest.TestCase):
    def test_config_accessors(self):
        config = {
            "preset_colors": [{"label": "Cyan", "value": "#00ced1"}],
            "speed_presets": [40, "60", "bad", 100],
            "modes": {"kraken": ["fixed", "breathing"]},
            "default_modes": {"kraken": "fixed"},
            "modes_with_color": ["breathing"],
            "match_rules": [{"contains": "Kraken", "match": "kraken", "type": "kraken"}],
            "auto_refresh_seconds": "5"
        }
        helper = DummyConfig(config)
        self.assertEqual(helper.get_preset_colors(), [("Cyan", "#00ced1")])
        self.assertEqual(helper.get_speed_presets(), [40, 60, 100])
        self.assertEqual(helper.get_modes("kraken"), ["fixed", "breathing"])
        self.assertEqual(helper.get_default_mode("kraken"), "fixed")
        self.assertEqual(helper.get_modes_with_color(), {"breathing"})
        self.assertEqual(helper.get_config_int("auto_refresh_seconds", 10), 5)
        self.assertEqual(helper.match_device("NZXT Kraken X"), ("kraken", "kraken"))
        self.assertEqual(helper.match_device("Unknown Device"), ("Unknown Device", "generic"))


class TestConfigIO(unittest.TestCase):
    def test_load_save_config(self):
        defaults = {"a": 1, "nested": {"b": 2, "c": 3}}
        override = {"nested": {"c": 99}, "d": 4}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            original_dir = config_module.CONFIG_DIR
            original_file = config_module.CONFIG_FILE
            try:
                config_module.CONFIG_DIR = tmp_path
                config_module.CONFIG_FILE = tmp_path / "config.json"

                config_module.save_config(override)
                loaded, exists, error = config_module.load_config(defaults)
            finally:
                config_module.CONFIG_DIR = original_dir
                config_module.CONFIG_FILE = original_file

        self.assertTrue(exists)
        self.assertIsNone(error)
        self.assertEqual(loaded["a"], 1)
        self.assertEqual(loaded["d"], 4)
        self.assertEqual(loaded["nested"], {"b": 2, "c": 99})


class TestLiquidctlAPI(unittest.TestCase):
    """Tests for LiquidctlAPI using simulated devices."""

    def setUp(self):
        """Set up mock devices for each test."""
        from tests.mock_devices import get_mock_devices, MockKrakenX3, MockCommanderPro
        self.mock_devices = get_mock_devices()
        self.kraken = MockKrakenX3()
        self.commander = MockCommanderPro()

    def test_api_finds_simulated_devices(self):
        """API should discover all injected simulated devices."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI

        api = LiquidctlAPI(simulated_devices=self.mock_devices)
        self.assertTrue(api.is_simulated)

        devices = api.find_devices()
        self.assertEqual(len(devices), len(self.mock_devices))

        # Verify device names are extracted
        names = [d.name for d in devices]
        self.assertIn("NZXT Kraken X (X53, X63 or X73)", names)
        self.assertIn("Corsair Commander Pro", names)
        self.assertIn("Gigabyte RGB Fusion 2.0 8297 Controller", names)

    def test_api_extracts_capabilities(self):
        """API should correctly extract device capabilities."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI

        api = LiquidctlAPI(simulated_devices=[self.kraken])
        api.find_devices()

        caps = api.get_capabilities("NZXT Kraken X (X53, X63 or X73)")
        self.assertIsNotNone(caps)
        self.assertEqual(caps.driver_class, "MockKrakenX3")

        # Kraken should have lighting and cooling
        self.assertTrue(caps.supports_lighting)
        self.assertTrue(caps.supports_cooling)

        # Check channels were extracted
        self.assertIn('ring', caps.color_channels)
        self.assertIn('logo', caps.color_channels)
        # Kraken X only has pump control (fans are motherboard PWM)
        self.assertIn('pump', caps.speed_channels)
        self.assertNotIn('fan', caps.speed_channels)

    def test_api_initialize(self):
        """API should successfully initialize simulated devices."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI

        api = LiquidctlAPI(simulated_devices=[self.kraken])
        api.find_devices()

        status, error = api.initialize("NZXT Kraken X (X53, X63 or X73)")
        self.assertEqual(error, "")
        self.assertGreater(len(status), 0)
        self.assertEqual(status[0][0], 'Firmware version')

    def test_api_get_status(self):
        """API should return device status."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI

        api = LiquidctlAPI(simulated_devices=[self.kraken])
        api.find_devices()

        status, error = api.get_status("NZXT Kraken X (X53, X63 or X73)")
        self.assertEqual(error, "")
        self.assertGreater(len(status), 0)

        # Check for expected Kraken status values
        props = [s[0] for s in status]
        self.assertIn('Liquid temperature', props)
        self.assertIn('Pump speed', props)

    def test_api_set_color(self):
        """API should set color on simulated devices."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI

        api = LiquidctlAPI(simulated_devices=[self.kraken])
        api.find_devices()

        success, error = api.set_color(
            "NZXT Kraken X (X53, X63 or X73)",
            channel='ring',
            mode='fixed',
            colors=[[255, 0, 128]],
        )
        self.assertTrue(success)
        self.assertEqual(error, "")

        # Verify state was updated on mock device
        self.assertIn('ring', self.kraken._current_colors)
        self.assertEqual(self.kraken._current_colors['ring']['mode'], 'fixed')

    def test_api_set_speed(self):
        """API should set speed on simulated devices."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI

        api = LiquidctlAPI(simulated_devices=[self.kraken])
        api.find_devices()

        success, error = api.set_speed(
            "NZXT Kraken X (X53, X63 or X73)",
            channel='pump',
            speed=75,
        )
        self.assertTrue(success)
        self.assertEqual(error, "")

        # Verify state was updated
        self.assertEqual(self.kraken._current_speeds['pump'], 75)

    def test_api_format_status(self):
        """API should format status output correctly."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI

        api = LiquidctlAPI(simulated_devices=[self.kraken])
        api.find_devices()

        status, _ = api.get_status("NZXT Kraken X (X53, X63 or X73)")
        formatted = api.format_status(status)

        self.assertIn("Liquid temperature: 32.5 °C", formatted)
        self.assertIn("Pump speed: 2100 rpm", formatted)

    def test_api_device_not_found(self):
        """API should return error for unknown devices."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI

        api = LiquidctlAPI(simulated_devices=[self.kraken])
        api.find_devices()

        status, error = api.get_status("Unknown Device XYZ")
        self.assertIn("not found", error)
        self.assertEqual(status, [])

    def test_api_cooling_only_device(self):
        """API should handle devices with only cooling (no lighting)."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI
        from tests.mock_devices import MockAquacomputer

        aqua = MockAquacomputer()
        api = LiquidctlAPI(simulated_devices=[aqua])
        api.find_devices()

        caps = api.get_capabilities("Aquacomputer Quadro")
        self.assertIsNotNone(caps)
        self.assertFalse(caps.supports_lighting)
        self.assertTrue(caps.supports_cooling)
        self.assertEqual(len(caps.color_channels), 0)
        self.assertGreater(len(caps.speed_channels), 0)

    def test_api_lighting_only_device(self):
        """API should handle devices with only lighting (no cooling)."""
        from liquidctl_gui.lib.liquidctl_api import LiquidctlAPI
        from tests.mock_devices import MockRGBFusion2

        rgb = MockRGBFusion2()
        api = LiquidctlAPI(simulated_devices=[rgb])
        api.find_devices()

        caps = api.get_capabilities("Gigabyte RGB Fusion 2.0 8297 Controller")
        self.assertIsNotNone(caps)
        self.assertTrue(caps.supports_lighting)
        self.assertFalse(caps.supports_cooling)
        self.assertGreater(len(caps.color_channels), 0)
        self.assertEqual(len(caps.speed_channels), 0)


class TestMockDevices(unittest.TestCase):
    """Tests to verify mock devices behave correctly."""

    def test_all_mock_devices_instantiate(self):
        """All mock device classes should instantiate without error."""
        from tests.mock_devices import MOCK_DEVICE_CLASSES

        for cls in MOCK_DEVICE_CLASSES:
            device = cls()
            self.assertIsInstance(device.description, str)
            self.assertGreater(len(device.description), 0)

    def test_mock_device_lifecycle(self):
        """Mock devices should support full lifecycle."""
        from tests.mock_devices import MockKrakenX3

        device = MockKrakenX3()

        device.connect()
        self.assertTrue(device._connected)

        status = device.initialize()
        self.assertIsInstance(status, list)
        self.assertTrue(device._initialized)

        status = device.get_status()
        self.assertIsInstance(status, list)
        self.assertGreater(len(status), 0)

        device.set_color('ring', 'fixed', [[0, 255, 0]])
        self.assertIn('ring', device._current_colors)

        device.set_fixed_speed('pump', 80)
        self.assertEqual(device._current_speeds['pump'], 80)

        device.disconnect()
        self.assertFalse(device._connected)

    def test_get_mock_devices_all(self):
        """get_mock_devices() should return all device types."""
        from tests.mock_devices import get_mock_devices, MOCK_DEVICE_CLASSES

        devices = get_mock_devices()
        self.assertEqual(len(devices), len(MOCK_DEVICE_CLASSES))

    def test_get_mock_devices_subset(self):
        """get_mock_devices() should filter by device type names."""
        from tests.mock_devices import get_mock_devices

        devices = get_mock_devices(['MockKrakenX3', 'MockCommanderPro'])
        self.assertEqual(len(devices), 2)

        names = [type(d).__name__ for d in devices]
        self.assertIn('MockKrakenX3', names)
        self.assertIn('MockCommanderPro', names)


if __name__ == "__main__":
    unittest.main()
