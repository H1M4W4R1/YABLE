from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable

from ble.dependencies import BleakClient, BleakGATTCharacteristic, BleakGATTDescriptor, BleakScanner, BLEDevice, AdvertisementData
from helpers.data.uuids import BLUETOOTH_NUMBERS, normalize_uuid
from models import CharacteristicModel, DescriptorModel, DiscoveredDevice, ServiceModel


class AsyncBleBridge:
    def __init__(self, emit: Callable[[str, Any], None]) -> None:
        self.emit = emit
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, name="ble-asyncio", daemon=True)
        self.thread.start()
        self.scanner: BleakScanner | None = None
        self.client: BleakClient | None = None
        self.devices: dict[str, DiscoveredDevice] = {}

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
        self.scanner = BleakScanner(self._on_detection)
        await self.scanner.start()
        self.emit("scan_state", True)

    def stop_scan(self) -> None:
        self.call(self._stop_scan())

    async def _stop_scan(self) -> None:
        if self.scanner:
            await self.scanner.stop()
            self.scanner = None
        self.emit("scan_state", False)

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
        self.emit("connection_state", f"Connecting to {self.devices[address].name}...")
        self.client = BleakClient(device, disconnected_callback=lambda _: self.emit("disconnected", None))
        await self.client.connect()
        self.emit("connection_state", "Discovering GATT...")
        services = await self._discover_services()
        self.emit("services", services)
        self.emit("connection_state", f"Connected to {self.devices[address].name}")

    async def _discover_services(self) -> list[ServiceModel]:
        assert self.client is not None
        services: list[ServiceModel] = []
        gatt = self.client.services
        for service in gatt:
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
                if "read" in properties:
                    try:
                        model.value = bytes(await self.client.read_gatt_char(characteristic))
                    except Exception as exc:
                        model.value = f"Read failed: {exc}".encode("utf-8", errors="replace")
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
        except Exception as exc:
            descriptor_model.value = f"Read failed: {exc}".encode("utf-8", errors="replace")
        return descriptor_model

    async def _read_user_description(self, characteristic: BleakGATTCharacteristic) -> str | None:
        assert self.client is not None
        for descriptor in characteristic.descriptors:
            if normalize_uuid(str(descriptor.uuid)).startswith("00002901"):
                try:
                    data = await self.client.read_gatt_descriptor(descriptor.handle)
                    return bytes(data).decode("utf-8", errors="replace").strip() or None
                except Exception:
                    return None
        return None

    def read_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
        self.call(self._read_characteristic(characteristic))

    async def _read_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
        assert self.client is not None
        data = bytes(await self.client.read_gatt_char(characteristic))
        self.emit("characteristic_value", (characteristic.handle, data))

    def write_characteristic(self, characteristic: BleakGATTCharacteristic, data: bytes) -> None:
        self.call(self._write_characteristic(characteristic, data))

    async def _write_characteristic(self, characteristic: BleakGATTCharacteristic, data: bytes) -> None:
        assert self.client is not None
        response = "write" in characteristic.properties
        await self.client.write_gatt_char(characteristic, data, response=response)
        self.emit("characteristic_value", (characteristic.handle, data))
        self.emit("toast", "Write complete")

    def read_descriptor(self, descriptor: BleakGATTDescriptor) -> None:
        self.call(self._read_descriptor(descriptor))

    async def _read_descriptor(self, descriptor: BleakGATTDescriptor) -> None:
        assert self.client is not None
        data = bytes(await self.client.read_gatt_descriptor(descriptor.handle))
        self.emit("descriptor_value", (descriptor.handle, data))

    def write_descriptor(self, descriptor: BleakGATTDescriptor, data: bytes) -> None:
        self.call(self._write_descriptor(descriptor, data))

    async def _write_descriptor(self, descriptor: BleakGATTDescriptor, data: bytes) -> None:
        assert self.client is not None
        await self.client.write_gatt_descriptor(descriptor.handle, data)
        self.emit("descriptor_value", (descriptor.handle, data))
        self.emit("toast", "Descriptor write complete")

    def toggle_notify(self, characteristic: BleakGATTCharacteristic, enable: bool) -> None:
        self.call(self._toggle_notify(characteristic, enable))

    async def _toggle_notify(self, characteristic: BleakGATTCharacteristic, enable: bool) -> None:
        assert self.client is not None
        if enable:
            await self.client.start_notify(
                characteristic,
                lambda sender, data: self.emit("characteristic_value", (sender.handle, bytes(data))),
            )
        else:
            await self.client.stop_notify(characteristic)
        self.emit("notify_state", (characteristic.handle, enable))

    def disconnect(self) -> None:
        self.call(self._disconnect())

    async def _disconnect(self) -> None:
        if self.client:
            await self.client.disconnect()
            self.client = None
        self.emit("disconnected", None)
