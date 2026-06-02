from __future__ import annotations

from typing import Any

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.characteristic import BleakGATTCharacteristic
    from bleak.backends.descriptor import BleakGATTDescriptor
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:  # pragma: no cover - exercised by users before deps install
    BleakClient = None
    BleakScanner = None
    BleakGATTCharacteristic = Any
    BleakGATTDescriptor = Any
    BLEDevice = Any
    AdvertisementData = Any
