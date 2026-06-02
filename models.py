from __future__ import annotations

from dataclasses import dataclass, field

from ble.dependencies import AdvertisementData, BLEDevice, BleakGATTCharacteristic, BleakGATTDescriptor
from helpers.formatting import ValueFormat


@dataclass
class DiscoveredDevice:
    address: str
    name: str
    rssi: int | None
    last_seen: float
    device: BLEDevice
    advertisement: AdvertisementData | None = None


@dataclass
class DescriptorModel:
    uuid: str
    handle: int
    name: str
    descriptor: BleakGATTDescriptor
    value: bytes | None = None
    display_format: ValueFormat = ValueFormat.ASCII


@dataclass
class CharacteristicModel:
    uuid: str
    handle: int
    name: str
    properties: set[str]
    characteristic: BleakGATTCharacteristic
    value: bytes | None = None
    display_format: ValueFormat = ValueFormat.ASCII
    notifying: bool = False
    descriptors: list[DescriptorModel] = field(default_factory=list)


@dataclass
class ServiceModel:
    uuid: str
    name: str
    characteristics: list[CharacteristicModel] = field(default_factory=list)
    descriptors: list[DescriptorModel] = field(default_factory=list)
