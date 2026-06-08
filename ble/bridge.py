from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable

from ble.dependencies import BleakClient, BleakGATTCharacteristic, BleakGATTDescriptor, BleakScanner, BLEDevice, AdvertisementData
from helpers.data.uuids import BLUETOOTH_NUMBERS, normalize_uuid
from models import CharacteristicModel, DescriptorModel, DiscoveredDevice, ServiceModel
from qt_ui.debug_log import DebugLevel


class AsyncBleBridge:
    def __init__(self, emit: Callable[[str, Any], None]) -> None:
        self.emit = emit
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, name="ble-asyncio", daemon=True)
        self.thread.start()
        self.scanner: BleakScanner | None = None
        self.client: BleakClient | None = None
        self.devices: dict[str, DiscoveredDevice] = {}

    def log(self, level: DebugLevel, message: str) -> None:
        self.emit("log", (level, message))

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def call(self, coro: Any) -> None:
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        future.add_done_callback(self._handle_task_result)

    def _handle_task_result(self, future: Any) -> None:
        try:
            future.result()
        except Exception as exc:  # pragma: no cover - UI reports runtime BLE failures
            self.emit("error", str(exc))

    def start_scan(self) -> None:
        self.call(self._start_scan())

    async def _start_scan(self) -> None:
        if BleakScanner is None:
            self.emit("missing_dependency", None)
            return
        if self.scanner:
            return
        self.log(DebugLevel.INFO, "Starting BLE scan")
        self.scanner = BleakScanner(self._on_detection)
        await self.scanner.start()
        self.emit("scan_state", True)
        self.log(DebugLevel.INFO, "BLE scan started")

    def stop_scan(self) -> None:
        self.call(self._stop_scan())

    async def _stop_scan(self) -> None:
        if self.scanner:
            self.log(DebugLevel.INFO, "Stopping BLE scan")
            await self.scanner.stop()
            self.scanner = None
        self.emit("scan_state", False)
        self.log(DebugLevel.INFO, "BLE scan stopped")

    def _on_detection(self, device: BLEDevice, advertisement_data: AdvertisementData) -> None:
        name = device.name or advertisement_data.local_name or "Unknown Device"
        rssi = getattr(advertisement_data, "rssi", None)
        if rssi is None:
            rssi = getattr(device, "rssi", None)
        record = DiscoveredDevice(
            address=device.address,
            name=name,
            rssi=rssi,
            last_seen=time.time(),
            device=device,
            advertisement=advertisement_data,
        )
        self.devices[device.address] = record
        self.emit("device", record)

    def connect(self, address: str) -> None:
        self.call(self._connect(address))

    async def _connect(self, address: str) -> None:
        await self._stop_scan()
        device = self.devices[address].device
        self.log(DebugLevel.INFO, f"Connecting to {self.devices[address].name} ({address})")
        self.emit("connection_state", f"Connecting to {self.devices[address].name}...")
        self.client = BleakClient(device, disconnected_callback=lambda _: self.emit("disconnected", None))
        await self.client.connect()
        self.log(DebugLevel.INFO, f"Connected to {self.devices[address].name} ({address})")
        self.emit("connection_state", "Discovering GATT...")
        services = await self._discover_services()
        self.emit("services", services)
        self.emit("connection_state", f"Connected to {self.devices[address].name}")

    async def _discover_services(self) -> list[ServiceModel]:
        assert self.client is not None
        services: list[ServiceModel] = []
        gatt = self.client.services
        for service in gatt:
            self.log(DebugLevel.VERBOSE, f"Discovered service {service.uuid}")
            service_model = ServiceModel(
                uuid=str(service.uuid),
                name=BLUETOOTH_NUMBERS.service_name(str(service.uuid)),
            )
            characteristic_descriptor_handles: set[int] = set()
            for characteristic in service.characteristics:
                properties = set(characteristic.properties)
                model = CharacteristicModel(
                    uuid=str(characteristic.uuid),
                    handle=characteristic.handle,
                    name=BLUETOOTH_NUMBERS.characteristic_name(str(characteristic.uuid)),
                    properties=properties,
                    characteristic=characteristic,
                )
                user_description = await self._read_user_description(characteristic)
                if user_description:
                    model.name = user_description
                read_failed = False
                if "read" in properties:
                    try:
                        model.value = bytes(await self.client.read_gatt_char(characteristic))
                        self.log(DebugLevel.VERBOSE, f"Initial read characteristic 0x{characteristic.handle:04x}: {len(model.value)} bytes")
                    except Exception as exc:
                        read_failed = True
                        self.log(DebugLevel.WARNING, f"Initial read failed for characteristic 0x{characteristic.handle:04x}: {exc}")
                        model.value = f"Read failed: {exc}".encode("utf-8", errors="replace")
                if self._is_service_name_description(user_description):
                    model.hidden = True
                    service_name = None if read_failed else self._decode_text_value(model.value)
                    if service_name is not None:
                        service_model.name = service_name
                        service_model.name_characteristic_handle = model.handle
                for descriptor in characteristic.descriptors:
                    descriptor_model = await self._descriptor_model(descriptor)
                    characteristic_descriptor_handles.add(descriptor.handle)
                    model.descriptors.append(descriptor_model)
                service_model.characteristics.append(model)
            for descriptor in getattr(service, "descriptors", []):
                if descriptor.handle in characteristic_descriptor_handles:
                    continue
                service_model.descriptors.append(await self._descriptor_model(descriptor))
            services.append(service_model)
        return services

    async def _descriptor_model(self, descriptor: BleakGATTDescriptor) -> DescriptorModel:
        assert self.client is not None
        descriptor_model = DescriptorModel(
            uuid=str(descriptor.uuid),
            handle=descriptor.handle,
            name=BLUETOOTH_NUMBERS.descriptor_name(str(descriptor.uuid)),
            descriptor=descriptor,
        )
        try:
            descriptor_model.value = bytes(await self.client.read_gatt_descriptor(descriptor.handle))
            self.log(DebugLevel.VERBOSE, f"Initial read descriptor 0x{descriptor.handle:04x}: {len(descriptor_model.value)} bytes")
        except Exception as exc:
            self.log(DebugLevel.WARNING, f"Initial read failed for descriptor 0x{descriptor.handle:04x}: {exc}")
            descriptor_model.value = f"Read failed: {exc}".encode("utf-8", errors="replace")
        return descriptor_model

    async def _read_user_description(self, characteristic: BleakGATTCharacteristic) -> str | None:
        assert self.client is not None
        for descriptor in characteristic.descriptors:
            if normalize_uuid(str(descriptor.uuid)).startswith("00002901"):
                try:
                    data = await self.client.read_gatt_descriptor(descriptor.handle)
                    return bytes(data).decode("utf-8", errors="replace").strip() or None
                except Exception as exc:
                    self.log(DebugLevel.VERBOSE, f"User description read failed for descriptor 0x{descriptor.handle:04x}: {exc}")
                    return None
        return None

    def _decode_text_value(self, value: bytes | None) -> str | None:
        if not value:
            return None
        return value.decode("utf-8", errors="replace").strip() or None

    def _is_service_name_description(self, description: str | None) -> bool:
        if description is None:
            return False
        return "".join(description.split()).lower() == "servicename"

    def read_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
        self.call(self._read_characteristic(characteristic))

    async def _read_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
        assert self.client is not None
        self.log(DebugLevel.VERBOSE, f"Reading characteristic 0x{characteristic.handle:04x}")
        data = bytes(await self.client.read_gatt_char(characteristic))
        self.log(DebugLevel.INFO, f"Read characteristic 0x{characteristic.handle:04x}: {len(data)} bytes")
        self.emit("characteristic_value", (characteristic.handle, data))

    def write_characteristic(self, characteristic: BleakGATTCharacteristic, data: bytes) -> None:
        self.call(self._write_characteristic(characteristic, data))

    async def _write_characteristic(self, characteristic: BleakGATTCharacteristic, data: bytes) -> None:
        assert self.client is not None
        response = "write" in characteristic.properties
        self.log(DebugLevel.INFO, f"Writing characteristic 0x{characteristic.handle:04x}: {len(data)} bytes")
        await self.client.write_gatt_char(characteristic, data, response=response)
        self.emit("characteristic_value", (characteristic.handle, data))
        self.emit("toast", "Write complete")

    def read_descriptor(self, descriptor: BleakGATTDescriptor) -> None:
        self.call(self._read_descriptor(descriptor))

    async def _read_descriptor(self, descriptor: BleakGATTDescriptor) -> None:
        assert self.client is not None
        self.log(DebugLevel.VERBOSE, f"Reading descriptor 0x{descriptor.handle:04x}")
        data = bytes(await self.client.read_gatt_descriptor(descriptor.handle))
        self.log(DebugLevel.INFO, f"Read descriptor 0x{descriptor.handle:04x}: {len(data)} bytes")
        self.emit("descriptor_value", (descriptor.handle, data))

    def write_descriptor(self, descriptor: BleakGATTDescriptor, data: bytes) -> None:
        self.call(self._write_descriptor(descriptor, data))

    async def _write_descriptor(self, descriptor: BleakGATTDescriptor, data: bytes) -> None:
        assert self.client is not None
        self.log(DebugLevel.INFO, f"Writing descriptor 0x{descriptor.handle:04x}: {len(data)} bytes")
        await self.client.write_gatt_descriptor(descriptor.handle, data)
        self.emit("descriptor_value", (descriptor.handle, data))
        self.emit("toast", "Descriptor write complete")

    def toggle_notify(self, characteristic: BleakGATTCharacteristic, enable: bool) -> None:
        self.call(self._toggle_notify(characteristic, enable))

    async def _toggle_notify(self, characteristic: BleakGATTCharacteristic, enable: bool) -> None:
        assert self.client is not None
        if enable:
            self.log(DebugLevel.INFO, f"Starting notifications for characteristic 0x{characteristic.handle:04x}")
            await self.client.start_notify(
                characteristic,
                lambda sender, data: self._handle_notification(sender, bytes(data)),
            )
        else:
            self.log(DebugLevel.INFO, f"Stopping notifications for characteristic 0x{characteristic.handle:04x}")
            await self.client.stop_notify(characteristic)
        self.emit("notify_state", (characteristic.handle, enable))

    def _handle_notification(self, sender: BleakGATTCharacteristic, data: bytes) -> None:
        self.log(DebugLevel.VERBOSE, f"Notification from characteristic 0x{sender.handle:04x}: {len(data)} bytes")
        self.emit("characteristic_value", (sender.handle, data))

    def disconnect(self) -> None:
        self.call(self._disconnect())

    async def _disconnect(self) -> None:
        if self.client:
            self.log(DebugLevel.INFO, "Disconnecting BLE client")
            await self.client.disconnect()
            self.client = None
        self.emit("disconnected", None)
        self.log(DebugLevel.INFO, "BLE client disconnected")
