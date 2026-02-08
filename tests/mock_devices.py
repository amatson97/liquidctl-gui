"""Mock liquidctl devices for testing without real hardware.

This module provides simulated devices that mimic the behavior of various
liquidctl-supported hardware. Use these to test the API lookup and GUI
without needing physical devices connected.

Usage:
    from tests.mock_devices import get_mock_devices, MockKrakenX3, MockCommanderPro

    # Get all mock devices
    devices = get_mock_devices()

    # Or use specific devices
    kraken = MockKrakenX3()
"""

from dataclasses import dataclass, field
from typing import Any


# Module-level constants that mimic liquidctl driver modules
_COLOR_CHANNELS = {
    'led': (0, 0x20),
}

_SPEED_CHANNELS = {
    'fan': (0, 100),
    'pump': (0, 100),
}

_COLOR_MODES = {
    'off': [],
    'fixed': ['color'],
    'breathing': ['color', 'speed'],
    'super-breathing': ['color', 'speed'],
    'fading': ['color', 'speed'],
    'marquee-3': ['color', 'speed', 'direction'],
    'marquee-4': ['color', 'speed', 'direction'],
    'marquee-5': ['color', 'speed', 'direction'],
    'marquee-6': ['color', 'speed', 'direction'],
    'covering-marquee': ['color', 'speed', 'direction'],
    'spectrum-wave': ['speed', 'direction'],
    'rainbow-flow': ['speed', 'direction'],
    'super-rainbow': ['speed'],
    'rainbow-pulse': ['speed'],
    'candle': ['color'],
    'starry-night': ['color', 'speed'],
    'loading': ['color'],
    'tai-chi': ['color', 'speed'],
    'water-cooler': ['color', 'speed'],
    'wings': ['color', 'speed'],
}


class BaseMockDevice:
    """Base class for mock liquidctl devices."""

    description: str = "Mock Device"
    vendor_id: int = 0x1234
    product_id: int = 0x5678
    release_number: int = 1
    serial_number: str = "MOCK123456"
    bus: str = "usb"
    address: str = "1:2"

    # Capability flags
    supports_lighting: bool = True
    supports_cooling: bool = True

    # Track state for testing
    _connected: bool = False
    _initialized: bool = False
    _current_colors: dict = None
    _current_speeds: dict = None

    def __init__(self):
        self._current_colors = {}
        self._current_speeds = {}

    def connect(self, **kwargs):
        """Simulate device connection."""
        self._connected = True

    def disconnect(self, **kwargs):
        """Simulate device disconnection."""
        self._connected = False

    def initialize(self, **kwargs) -> list[tuple]:
        """Simulate device initialization, returns status tuples."""
        self._initialized = True
        return [
            ('Firmware version', '1.0.0', ''),
            ('Status', 'OK', ''),
        ]

    def get_status(self, **kwargs) -> list[tuple]:
        """Return simulated device status."""
        return [
            ('Status', 'OK', ''),
        ]

    def set_color(self, channel: str, mode: str, colors: list, speed: str = 'normal', **kwargs):
        """Simulate setting LED color."""
        self._current_colors[channel] = {'mode': mode, 'colors': colors, 'speed': speed}

    def set_fixed_speed(self, channel: str, duty: int, **kwargs):
        """Simulate setting fan/pump speed."""
        self._current_speeds[channel] = duty

    def set_speed_profile(self, channel: str, profile: list, **kwargs):
        """Simulate setting a speed curve profile."""
        self._current_speeds[channel] = {'profile': profile}


class MockKrakenX3(BaseMockDevice):
    """Mock NZXT Kraken X (X53, X63 or X73) device.
    
    Note: Kraken X devices only support pump speed control.
    Radiator fans are PWM-controlled by the motherboard.
    """

    description = "NZXT Kraken X (X53, X63 or X73)"
    vendor_id = 0x1e71
    product_id = 0x2007

    # Kraken-specific channels exposed as properties
    @property
    def color_channels(self):
        return {
            'external': (0, 0x10),
            'ring': (0, 0x08),
            'logo': (0, 0x01),
            'sync': (0, 0x09),
        }

    @property
    def speed_channels(self):
        # Kraken X only controls pump speed, not fans
        return {
            'pump': (60, 100),
        }

    def initialize(self, **kwargs):
        self._initialized = True
        return [
            ('Firmware version', '2.5.8', ''),
        ]

    def get_status(self, **kwargs):
        return [
            ('Liquid temperature', 32.5, '°C'),
            ('Pump speed', 2100, 'rpm'),
            ('Pump duty', 60, '%'),
        ]


class MockKrakenZ3(BaseMockDevice):
    """Mock NZXT Kraken Z (Z53, Z63 or Z73) device with LCD."""

    description = "NZXT Kraken Z (Z53, Z63 or Z73)"
    vendor_id = 0x1e71
    product_id = 0x3008

    @property
    def color_channels(self):
        return {
            'external': (0, 0x10),
        }

    @property
    def speed_channels(self):
        return {
            'fan': (25, 100),
            'pump': (60, 100),
        }

    def initialize(self, **kwargs):
        self._initialized = True
        return [
            ('Firmware version', '1.4.2', ''),
            ('LCD FW version', '1.2.1', ''),
        ]

    def get_status(self, **kwargs):
        return [
            ('Liquid temperature', 34.0, '°C'),
            ('Pump speed', 2350, 'rpm'),
            ('Pump duty', 65, '%'),
            ('Fan speed', 800, 'rpm'),
            ('Fan duty', 30, '%'),
        ]


class MockCommanderPro(BaseMockDevice):
    """Mock Corsair Commander Pro device."""

    description = "Corsair Commander Pro"
    vendor_id = 0x1b1c
    product_id = 0x0c10

    @property
    def color_channels(self):
        return {
            'led1': (0, 204),
            'led2': (0, 204),
        }

    @property
    def speed_channels(self):
        return {
            'fan1': (0, 100),
            'fan2': (0, 100),
            'fan3': (0, 100),
            'fan4': (0, 100),
            'fan5': (0, 100),
            'fan6': (0, 100),
        }

    def initialize(self, **kwargs):
        self._initialized = True
        return [
            ('Firmware version', '1.0.28', ''),
            ('Bootloader version', '1.2', ''),
        ]

    def get_status(self, **kwargs):
        return [
            ('Temperature 1', 38.5, '°C'),
            ('Temperature 2', 42.0, '°C'),
            ('Fan 1 speed', 1200, 'rpm'),
            ('Fan 2 speed', 1150, 'rpm'),
            ('Fan 3 speed', 1180, 'rpm'),
            ('Fan 4 speed', 0, 'rpm'),
            ('Fan 5 speed', 0, 'rpm'),
            ('Fan 6 speed', 0, 'rpm'),
        ]


class MockRGBFusion2(BaseMockDevice):
    """Mock Gigabyte RGB Fusion 2.0 controller."""

    description = "Gigabyte RGB Fusion 2.0 8297 Controller"
    vendor_id = 0x048d
    product_id = 0x8297
    supports_cooling = False

    @property
    def color_channels(self):
        return {
            'led1': (0, 1),
            'led2': (0, 1),
            'led3': (0, 1),
            'led4': (0, 1),
            'led5': (0, 1),
            'led6': (0, 1),
            'led7': (0, 1),
            'led8': (0, 1),
        }

    @property
    def speed_channels(self):
        return {}

    def initialize(self, **kwargs):
        self._initialized = True
        return [
            ('Hardware name', 'IT8297BX-GBX570', ''),
        ]

    def get_status(self, **kwargs):
        return []


class MockSmartDevice2(BaseMockDevice):
    """Mock NZXT Smart Device V2."""

    description = "NZXT Smart Device V2"
    vendor_id = 0x1e71
    product_id = 0x2006

    @property
    def color_channels(self):
        return {
            'led1': (0, 40),
            'led2': (0, 40),
        }

    @property
    def speed_channels(self):
        return {
            'fan1': (25, 100),
            'fan2': (25, 100),
            'fan3': (25, 100),
        }

    def initialize(self, **kwargs):
        self._initialized = True
        return [
            ('Firmware version', '1.7.0', ''),
            ('Accessories', '2x HUE 2 LED strips, 3x AER RGB 2 fans', ''),
        ]

    def get_status(self, **kwargs):
        return [
            ('Fan 1 speed', 850, 'rpm'),
            ('Fan 1 current', 0.12, 'A'),
            ('Fan 2 speed', 920, 'rpm'),
            ('Fan 2 current', 0.11, 'A'),
            ('Fan 3 speed', 880, 'rpm'),
            ('Fan 3 current', 0.12, 'A'),
            ('Noise level', 42, 'dB'),
        ]


class MockH100i(BaseMockDevice):
    """Mock Corsair Hydro H100i Pro XT."""

    description = "Corsair Hydro H100i Pro XT"
    vendor_id = 0x1b1c
    product_id = 0x0c22

    @property
    def color_channels(self):
        return {
            'led': (0, 16),
        }

    @property
    def speed_channels(self):
        return {
            'fan': (0, 100),
            'pump': (50, 100),
        }

    def initialize(self, **kwargs):
        self._initialized = True
        return [
            ('Firmware version', '2.10.219', ''),
        ]

    def get_status(self, **kwargs):
        return [
            ('Liquid temperature', 29.3, '°C'),
            ('Pump mode', 'Balanced', ''),
            ('Fan 1 mode', 'DC', ''),
            ('Fan 1 speed', 780, 'rpm'),
            ('Fan 2 mode', 'DC', ''),
            ('Fan 2 speed', 790, 'rpm'),
        ]


class MockAquacomputer(BaseMockDevice):
    """Mock Aquacomputer Quadro device."""

    description = "Aquacomputer Quadro"
    vendor_id = 0x0c70
    product_id = 0xf00d
    supports_lighting = False

    @property
    def color_channels(self):
        return {}

    @property
    def speed_channels(self):
        return {
            'fan1': (0, 100),
            'fan2': (0, 100),
            'fan3': (0, 100),
            'fan4': (0, 100),
        }

    def initialize(self, **kwargs):
        self._initialized = True
        return [
            ('Serial number', '12345-67890', ''),
            ('Firmware version', '1050', ''),
        ]

    def get_status(self, **kwargs):
        return [
            ('Sensor 1', 35.2, '°C'),
            ('Sensor 2', 38.7, '°C'),
            ('Fan 1 power', 45.2, '%'),
            ('Fan 1 speed', 920, 'rpm'),
            ('Fan 2 power', 55.0, '%'),
            ('Fan 2 speed', 1100, 'rpm'),
            ('Fan 3 power', 0.0, '%'),
            ('Fan 3 speed', 0, 'rpm'),
            ('Fan 4 power', 0.0, '%'),
            ('Fan 4 speed', 0, 'rpm'),
            ('Flow sensor', 120.5, 'dL/h'),
        ]


class MockEVGAGPU(BaseMockDevice):
    """Mock EVGA GTX 1080 FTW GPU with iCX."""

    description = "EVGA GTX 1080 FTW"
    vendor_id = 0x3842
    product_id = 0x1080
    supports_cooling = False

    @property
    def color_channels(self):
        return {
            'led': (0, 1),
        }

    @property
    def speed_channels(self):
        return {}

    def initialize(self, **kwargs):
        self._initialized = True
        return [
            ('Mode', 'Hardware controlled', ''),
        ]

    def get_status(self, **kwargs):
        return [
            ('Mode', 'Hardware controlled', ''),
            ('LED brightness', 100, '%'),
        ]


# Registry of all available mock device classes
MOCK_DEVICE_CLASSES = [
    MockKrakenX3,
    MockKrakenZ3,
    MockCommanderPro,
    MockRGBFusion2,
    MockSmartDevice2,
    MockH100i,
    MockAquacomputer,
    MockEVGAGPU,
]


def get_mock_devices(device_types: list[str] | None = None) -> list[BaseMockDevice]:
    """Get a list of mock device instances.

    Args:
        device_types: Optional list of device class names to include.
                     If None, returns one of each type.

    Returns:
        List of mock device instances.

    Example:
        # Get all device types
        devices = get_mock_devices()

        # Get specific devices only
        devices = get_mock_devices(['MockKrakenX3', 'MockCommanderPro'])
    """
    if device_types is None:
        return [cls() for cls in MOCK_DEVICE_CLASSES]

    devices = []
    for cls in MOCK_DEVICE_CLASSES:
        if cls.__name__ in device_types:
            devices.append(cls())
    return devices


def get_mock_device_by_description(description: str) -> BaseMockDevice | None:
    """Get a mock device instance by its description string.

    Args:
        description: The device description to match.

    Returns:
        A mock device instance, or None if not found.
    """
    for cls in MOCK_DEVICE_CLASSES:
        instance = cls()
        if instance.description == description:
            return instance
    return None


# For patching find_liquidctl_devices in tests
def mock_find_liquidctl_devices():
    """Drop-in replacement for liquidctl.driver.find_liquidctl_devices.

    Use with unittest.mock.patch:
        @patch('liquidctl.driver.find_liquidctl_devices', mock_find_liquidctl_devices)
        def test_something(self):
            ...
    """
    return get_mock_devices()


def mock_find_liquidctl_devices_subset(device_types: list[str]):
    """Factory for creating a mock find function with specific devices.

    Args:
        device_types: List of mock device class names to include.

    Returns:
        A callable that returns mock devices of the specified types.

    Example:
        @patch('liquidctl.driver.find_liquidctl_devices',
               mock_find_liquidctl_devices_subset(['MockKrakenX3']))
        def test_single_kraken(self):
            ...
    """
    def _mock():
        return get_mock_devices(device_types)
    return _mock
