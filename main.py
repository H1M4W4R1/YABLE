from __future__ import annotations

import asyncio
import binascii
import json
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import messagebox, ttk

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


APP_TITLE = "YABLED"

COLORS = {
    "bg": "#0d1117",
    "panel": "#161b22",
    "panel_2": "#0f141b",
    "panel_3": "#21262d",
    "line": "#30363d",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "accent": "#22d3ee",
    "accent_2": "#67e8f9",
    "danger": "#f87171",
    "success": "#34d399",
    "warning": "#fbbf24",
}


class ValueFormat(str, Enum):
    HEX = "HEX"
    DEC = "DEC"
    OCT = "OCT"
    BIN = "BIN"
    ASCII = "ASCII"
    DATETIME = "DATETIME"


FORMAT_LABELS = [fmt.value for fmt in ValueFormat]

UUID_DATA_DIR = Path(__file__).resolve().parent / "data" / "uuids"
BLUETOOTH_BASE_UUID_SUFFIX = "-0000-1000-8000-00805f9b34fb"


def normalize_uuid(uuid: str) -> str:
    return str(uuid).lower()


class BluetoothNumbers:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.service_names = self._load_uuid_names("service_uuids.json")
        self.characteristic_names = self._load_uuid_names("characteristic_uuids.json")
        self.descriptor_names = self._load_uuid_names("descriptor_uuids.json")
        self.company_names = self._load_company_names()
        self.appearance_names = self._load_appearance_names()

    def _load_json(self, filename: str) -> Any:
        path = self.data_dir / filename
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def _load_uuid_names(self, filename: str) -> dict[str, str]:
        names: dict[str, str] = {}
        for entry in self._load_json(filename):
            uuid = str(entry.get("uuid", "")).strip()
            name = str(entry.get("name", "")).strip()
            if not uuid or not name:
                continue
            for key in uuid_lookup_keys(uuid):
                names[key] = name
        return names

    def _load_company_names(self) -> dict[int, str]:
        names: dict[int, str] = {}
        for entry in self._load_json("company_ids.json"):
            value = entry.get("value", entry.get("id", entry.get("code")))
            name = str(entry.get("name", "")).strip()
            if value is None or not name:
                continue
            try:
                names[int(value)] = name
            except (TypeError, ValueError):
                continue
        return names

    def _load_appearance_names(self) -> dict[int, str]:
        names: dict[int, str] = {}
        for entry in self._load_json("gap_appearance.json"):
            name = str(entry.get("name", entry.get("description", ""))).strip()
            if not name:
                continue
            category = entry.get("category")
            value = entry.get("value")
            try:
                if value is None:
                    value = int(category) << 6
                names[int(value)] = name
            except (TypeError, ValueError):
                continue
            subcategories = entry.get("subcategory", [])
            if not isinstance(subcategories, list):
                subcategories = [{"value": subcategories, "name": name}]
            for subcategory in subcategories:
                sub_name = str(subcategory.get("name", "")).strip()
                sub_value = subcategory.get("value")
                if not sub_name or sub_value is None:
                    continue
                try:
                    names[(int(category) << 6) | int(sub_value)] = f"{name}: {sub_name}"
                except (TypeError, ValueError):
                    continue
        return names

    def service_name(self, uuid: str, fallback: str = "BLE Service") -> str:
        return self.service_names.get(normalize_uuid(uuid), fallback)

    def characteristic_name(self, uuid: str, fallback: str = "BLE Characteristic") -> str:
        return self.characteristic_names.get(normalize_uuid(uuid), fallback)

    def descriptor_name(self, uuid: str, fallback: str = "BLE Descriptor") -> str:
        return self.descriptor_names.get(normalize_uuid(uuid), fallback)

    def company_name(self, company_id: int) -> str:
        return self.company_names.get(company_id, f"Company 0x{company_id:04X}")

    def appearance_name(self, appearance: int | None) -> str | None:
        if appearance is None:
            return None
        return self.appearance_names.get(appearance, f"Appearance 0x{appearance:04X}")


def uuid_lookup_keys(uuid: str) -> list[str]:
    normalized = normalize_uuid(uuid)
    keys = [normalized]
    compact = normalized.replace("-", "")
    if len(compact) == 4:
        keys.append(f"0000{compact}{BLUETOOTH_BASE_UUID_SUFFIX}")
    elif len(compact) == 8:
        keys.append(f"{compact}{BLUETOOTH_BASE_UUID_SUFFIX}")
    return keys


BLUETOOTH_NUMBERS = BluetoothNumbers(UUID_DATA_DIR)


def friendly_uuid_name(uuid: str, fallback: str) -> str:
    return (
        BLUETOOTH_NUMBERS.service_name(uuid, "")
        or BLUETOOTH_NUMBERS.characteristic_name(uuid, "")
        or BLUETOOTH_NUMBERS.descriptor_name(uuid, "")
        or fallback
    )


def format_elapsed(seconds: float) -> str:
    if seconds < 1:
        return "now"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m ago"
    return f"{minutes // 60}h ago"


def signal_icon(rssi: int | None) -> str:
    if rssi is None:
        return "▁▁▁▁"
    if rssi >= -55:
        return "▂▄▆█"
    if rssi >= -70:
        return "▂▄▆▁"
    if rssi >= -85:
        return "▂▄▁▁"
    return "▂▁▁▁"


def signal_icon(rssi: int | None) -> str:
    if rssi is None:
        return "----"
    if rssi >= -55:
        return "best"
    if rssi >= -70:
        return "good"
    if rssi >= -85:
        return "fair"
    return "weak"


def manufacturer_names(advertisement: AdvertisementData | None) -> list[str]:
    manufacturer_data = getattr(advertisement, "manufacturer_data", None) or {}
    return [BLUETOOTH_NUMBERS.company_name(int(company_id)) for company_id in sorted(manufacturer_data)]


def extract_gap_appearance(advertisement: AdvertisementData | None) -> int | None:
    if advertisement is None:
        return None
    appearance = getattr(advertisement, "appearance", None)
    if isinstance(appearance, int):
        return appearance

    def find_appearance(value: Any) -> int | None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() == "appearance" and isinstance(child, int):
                    return child
                found = find_appearance(child)
                if found is not None:
                    return found
        elif isinstance(value, (list, tuple)):
            for child in value:
                found = find_appearance(child)
                if found is not None:
                    return found
        return None

    return find_appearance(getattr(advertisement, "platform_data", None))


def bytes_to_text(data: bytes | bytearray | None, fmt: ValueFormat) -> str:
    if data is None:
        return ""
    raw = bytes(data)
    if not raw:
        return "(empty)"

    if fmt == ValueFormat.HEX:
        return " ".join(f"{byte:02X}" for byte in raw)
    if fmt == ValueFormat.DEC:
        return " ".join(str(byte) for byte in raw)
    if fmt == ValueFormat.OCT:
        return " ".join(format(byte, "03o") for byte in raw)
    if fmt == ValueFormat.BIN:
        return " ".join(format(byte, "08b") for byte in raw)
    if fmt == ValueFormat.ASCII:
        return "".join(chr(byte) if 32 <= byte < 127 else "." for byte in raw)
    if fmt == ValueFormat.DATETIME:
        if len(raw) in (4, 8):
            epoch = int.from_bytes(raw, "little", signed=False)
            try:
                return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
            except (OverflowError, OSError, ValueError):
                pass
        return "not a Unix timestamp"
    return binascii.hexlify(raw).decode("ascii").upper()


def text_to_bytes(text: str, fmt: ValueFormat) -> bytes:
    value = text.strip()
    if fmt == ValueFormat.HEX:
        compact = value.replace(" ", "").replace("0x", "").replace(",", "")
        if len(compact) % 2:
            compact = "0" + compact
        return bytes.fromhex(compact)
    if fmt == ValueFormat.DEC:
        return bytes(int(part, 10) & 0xFF for part in value.replace(",", " ").split())
    if fmt == ValueFormat.OCT:
        return bytes(int(part, 8) & 0xFF for part in value.replace(",", " ").split())
    if fmt == ValueFormat.BIN:
        return bytes(int(part, 2) & 0xFF for part in value.replace(",", " ").split())
    if fmt == ValueFormat.ASCII:
        return value.encode("utf-8")
    if fmt == ValueFormat.DATETIME:
        if value.isdigit():
            epoch = int(value)
        else:
            parsed = datetime.fromisoformat(value)
            epoch = int(parsed.timestamp())
        return epoch.to_bytes(4, "little", signed=False)
    raise ValueError(f"Unsupported format: {fmt}")


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
                name = BLUETOOTH_NUMBERS.characteristic_name(str(characteristic.uuid))
                model = CharacteristicModel(
                    uuid=str(characteristic.uuid),
                    handle=characteristic.handle,
                    name=name,
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
                    characteristic_descriptor_handles.add(descriptor.handle)
                    model.descriptors.append(descriptor_model)
                service_model.characteristics.append(model)
            for descriptor in getattr(service, "descriptors", []):
                if descriptor.handle in characteristic_descriptor_handles:
                    continue
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
                service_model.descriptors.append(descriptor_model)
            services.append(service_model)
        return services

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


class WriteDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, target: CharacteristicModel | DescriptorModel, on_write: Callable[[bytes], None]) -> None:
        super().__init__(parent)
        self.target = target
        self.on_write = on_write
        self.title(f"Write {target.name}")
        self.configure(bg=COLORS["panel"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.format_var = tk.StringVar(value=target.display_format.value)
        self.value_var = tk.StringVar(value=bytes_to_text(target.value, target.display_format))

        ttk.Label(self, text=target.name, style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(18, 4))
        ttk.Label(self, text=target.uuid, style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 14))
        ttk.Label(self, text="Format").grid(row=2, column=0, sticky="w", padx=18, pady=6)
        format_box = ttk.Combobox(self, values=FORMAT_LABELS, textvariable=self.format_var, state="readonly", width=18)
        format_box.grid(row=2, column=1, sticky="ew", padx=18, pady=6)
        ttk.Label(self, text="Value").grid(row=3, column=0, sticky="nw", padx=18, pady=6)
        entry = tk.Text(self, height=5, width=48, bg=COLORS["panel_2"], fg=COLORS["text"], insertbackground=COLORS["accent"], relief="flat", padx=10, pady=10)
        entry.grid(row=3, column=1, sticky="ew", padx=18, pady=6)
        entry.insert("1.0", self.value_var.get())
        entry.focus_set()
        self.entry = entry

        button_row = ttk.Frame(self, style="Panel.TFrame")
        button_row.grid(row=4, column=0, columnspan=2, sticky="e", padx=18, pady=(12, 18))
        ttk.Button(button_row, text="Cancel", command=self.destroy, style="Ghost.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Write", command=self._write, style="Accent.TButton").pack(side="left")

    def _write(self) -> None:
        try:
            data = text_to_bytes(self.entry.get("1.0", "end").strip(), ValueFormat(self.format_var.get()))
        except Exception as exc:
            messagebox.showerror("Invalid value", str(exc), parent=self)
            return
        self.on_write(data)
        self.destroy()


class BleDebuggerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1220x760")
        self.minsize(980, 620)
        self.overrideredirect(True)
        self.configure(bg=COLORS["bg"])

        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.bridge = AsyncBleBridge(self._emit)
        self.devices: dict[str, DiscoveredDevice] = {}
        self.device_cards: dict[str, dict[str, Any]] = {}
        self.services: list[ServiceModel] = []
        self.characteristics_by_handle: dict[int, CharacteristicModel] = {}
        self.descriptors_by_handle: dict[int, DescriptorModel] = {}
        self.char_widgets: dict[int, dict[str, Any]] = {}
        self.descriptor_widgets: dict[int, dict[str, Any]] = {}
        self.scan_running = False
        self.connected = False
        self.selected_address: str | None = None
        self._normal_geometry = ""
        self._is_maximized = False
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._configure_styles()
        self._build_layout()
        self._poll_events()
        self._tick_elapsed()
        self.bind("<Map>", self._restore_frameless_chrome)

    def _emit(self, event: str, payload: Any) -> None:
        self.events.put((event, payload))

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], fieldbackground=COLORS["panel_2"], font=("Segoe UI", 10))
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Surface.TFrame", background=COLORS["panel_2"])
        style.configure("TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("MutedBg.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI Semibold", 12))
        style.configure("Hero.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI Semibold", 18))
        style.configure("Accent.TButton", background=COLORS["accent"], foreground="#061018", borderwidth=0, focusthickness=0, padding=(14, 8), font=("Segoe UI Semibold", 10))
        style.map("Accent.TButton", background=[("active", COLORS["accent_2"]), ("disabled", COLORS["panel_3"])])
        style.configure("Ghost.TButton", background=COLORS["panel_3"], foreground=COLORS["text"], borderwidth=0, padding=(12, 7))
        style.map("Ghost.TButton", background=[("active", "#263244"), ("disabled", COLORS["panel_2"])])
        style.configure("Treeview", background=COLORS["panel_2"], foreground=COLORS["text"], fieldbackground=COLORS["panel_2"], borderwidth=0, rowheight=32)
        style.configure("Treeview.Heading", background=COLORS["panel"], foreground=COLORS["muted"], relief="flat", font=("Segoe UI Semibold", 9))
        style.map("Treeview", background=[("selected", "#12303b")], foreground=[("selected", COLORS["text"])])
        style.configure("Vertical.TScrollbar", background=COLORS["panel_3"], troughcolor=COLORS["panel"], arrowcolor=COLORS["accent"])
        style.configure("TCombobox", borderwidth=0, arrowsize=14, padding=6)

    def _build_layout(self) -> None:
        chrome = tk.Frame(self, bg=COLORS["bg"], height=38)
        chrome.pack(fill="x")
        chrome.pack_propagate(False)
        chrome.bind("<ButtonPress-1>", self._begin_window_drag)
        chrome.bind("<B1-Motion>", self._drag_window)

        logo = tk.Canvas(chrome, width=42, height=28, bg=COLORS["bg"], highlightthickness=0)
        logo.pack(side="left", padx=(16, 4), pady=5)
        logo.create_oval(5, 7, 19, 21, outline=COLORS["accent"], width=2)
        logo.create_oval(20, 7, 34, 21, outline=COLORS["accent_2"], width=2)
        logo.create_line(15, 14, 24, 14, fill=COLORS["text"], width=2)
        logo.create_line(28, 7, 34, 14, fill=COLORS["accent_2"], width=2)
        logo.create_line(28, 21, 34, 14, fill=COLORS["accent_2"], width=2)
        logo.bind("<ButtonPress-1>", self._begin_window_drag)
        logo.bind("<B1-Motion>", self._drag_window)

        self.status_label = ttk.Label(chrome, text="Ready", style="MutedBg.TLabel")
        self.status_label.pack(side="left", padx=(8, 0))
        self.status_label.bind("<ButtonPress-1>", self._begin_window_drag)
        self.status_label.bind("<B1-Motion>", self._drag_window)

        window_controls = tk.Frame(chrome, bg=COLORS["bg"])
        window_controls.pack(side="right", padx=(0, 8))
        self._make_window_button(window_controls, "−", self._minimize_window).pack(side="left")
        self.maximize_button = self._make_window_button(window_controls, "□", self._toggle_maximize)
        self.maximize_button.pack(side="left")
        self._make_window_button(window_controls, "×", self.destroy, danger=True).pack(side="left")

        body = tk.PanedWindow(self, orient="horizontal", bg=COLORS["bg"], sashwidth=6, bd=0, relief="flat")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        left = ttk.Frame(body, style="Panel.TFrame")
        right = ttk.Frame(body, style="Panel.TFrame")
        body.add(left, minsize=390, width=430)
        body.add(right, minsize=540)

        left_header = ttk.Frame(left, style="Panel.TFrame")
        left_header.pack(fill="x", padx=14, pady=(14, 8))
        ttk.Label(left_header, text="Advertised devices", style="Title.TLabel").pack(side="left")
        self.scan_button = ttk.Button(left_header, text="Start scan", command=self._toggle_scan, style="Accent.TButton")
        self.scan_button.pack(side="right", padx=(8, 0))
        self.connect_button = ttk.Button(left_header, text="Connect + GATT", command=self._connect_selected, style="Ghost.TButton", state="disabled")
        self.connect_button.pack(side="right")

        self.device_canvas = tk.Canvas(left, bg=COLORS["panel"], highlightthickness=0)
        self.device_canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 14))
        device_scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.device_canvas.yview)
        device_scrollbar.pack(side="right", fill="y", padx=(0, 14), pady=(0, 14))
        self.device_canvas.configure(yscrollcommand=device_scrollbar.set)
        self.device_frame = ttk.Frame(self.device_canvas, style="Panel.TFrame")
        self.device_canvas_window = self.device_canvas.create_window((0, 0), window=self.device_frame, anchor="nw")
        self.device_frame.bind("<Configure>", lambda _: self.device_canvas.configure(scrollregion=self.device_canvas.bbox("all")))
        self.device_canvas.bind("<Configure>", lambda event: self.device_canvas.itemconfigure(self.device_canvas_window, width=event.width))

        gatt_header = ttk.Frame(right, style="Panel.TFrame")
        gatt_header.pack(fill="x", padx=14, pady=(14, 8))
        ttk.Label(gatt_header, text="GATT", style="Title.TLabel").pack(side="left")
        self.disconnect_button = ttk.Button(gatt_header, text="Disconnect", command=self._disconnect, style="Ghost.TButton", state="disabled")
        self.disconnect_button.pack(side="right", padx=(8, 0))
        self.gatt_hint = ttk.Label(gatt_header, text="Connect to a device to discover services", style="Muted.TLabel")
        self.gatt_hint.pack(side="right")

        self.canvas = tk.Canvas(right, bg=COLORS["panel"], highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 14))
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 14), pady=(0, 14))
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.gatt_frame = ttk.Frame(self.canvas, style="Panel.TFrame")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.gatt_frame, anchor="nw")
        self.gatt_frame.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.canvas_window, width=event.width))

    def _make_window_button(self, parent: tk.Frame, text: str, command: Callable[[], None], danger: bool = False) -> tk.Label:
        label = tk.Label(
            parent,
            text=text,
            width=4,
            height=1,
            bg=COLORS["bg"],
            fg=COLORS["danger"] if danger else COLORS["muted"],
            font=("Segoe UI Semibold", 12),
            cursor="hand2",
        )
        label.bind("<Button-1>", lambda _event: command())
        label.bind("<Enter>", lambda _event: label.configure(bg="#2b1518" if danger else COLORS["panel_3"], fg=COLORS["text"]))
        label.bind("<Leave>", lambda _event: label.configure(bg=COLORS["bg"], fg=COLORS["danger"] if danger else COLORS["muted"]))
        return label

    def _begin_window_drag(self, event: tk.Event) -> None:
        if self._is_maximized:
            return
        self._drag_start_x = event.x_root - self.winfo_x()
        self._drag_start_y = event.y_root - self.winfo_y()

    def _drag_window(self, event: tk.Event) -> None:
        if self._is_maximized:
            return
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.geometry(f"+{x}+{y}")

    def _minimize_window(self) -> None:
        self.overrideredirect(False)
        self.iconify()

    def _restore_frameless_chrome(self, _event: tk.Event | None = None) -> None:
        if self.state() == "normal":
            self.after(10, lambda: self.overrideredirect(True))

    def _toggle_maximize(self) -> None:
        if self._is_maximized:
            self.geometry(self._normal_geometry)
            self._is_maximized = False
            self.maximize_button.configure(text="□")
            return
        self._normal_geometry = self.geometry()
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        self.geometry(f"{width}x{height}+0+0")
        self._is_maximized = True
        self.maximize_button.configure(text="❐")

    def _toggle_scan(self) -> None:
        if self.scan_running:
            self.bridge.stop_scan()
        else:
            self.bridge.start_scan()
            self._set_status("Scanning for advertisements...")

    def _connect_selected(self) -> None:
        if not self.selected_address:
            return
        self.connect_button.configure(state="disabled")
        self.bridge.connect(self.selected_address)

    def _connect_device_card(self, address: str) -> None:
        self._select_device(address)
        self._connect_selected()

    def _disconnect(self) -> None:
        self.bridge.disconnect()

    def _select_device(self, address: str) -> None:
        self.selected_address = address
        self.connect_button.configure(state="normal")
        for card_address, widgets in self.device_cards.items():
            selected = card_address == address
            bg = COLORS["panel_3"] if selected else COLORS["panel_2"]
            border = COLORS["accent"] if selected else COLORS["line"]
            widgets["frame"].configure(bg=bg, highlightbackground=border)
            for widget in widgets.get("background_widgets", []):
                widget.configure(bg=bg)

    def _poll_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event, payload)
        self.after(80, self._poll_events)

    def _handle_event(self, event: str, payload: Any) -> None:
        if event == "missing_dependency":
            self._set_status("Install dependencies with: python -m pip install -r requirements.txt")
            messagebox.showerror("Missing dependency", "The bleak package is required for BLE access.\n\nRun: python -m pip install -r requirements.txt", parent=self)
        elif event == "scan_state":
            self.scan_running = bool(payload)
            self.scan_button.configure(text="Stop scan" if self.scan_running else "Start scan")
        elif event == "device":
            self._upsert_device(payload)
        elif event == "connection_state":
            self._set_status(str(payload))
        elif event == "services":
            self.connected = True
            self.disconnect_button.configure(state="normal")
            self._render_services(payload)
        elif event == "characteristic_value":
            handle, data = payload
            self._update_characteristic_value(handle, data)
        elif event == "descriptor_value":
            handle, data = payload
            self._update_descriptor_value(handle, data)
        elif event == "notify_state":
            handle, enabled = payload
            self._set_notify_state(handle, enabled)
        elif event == "toast":
            self._set_status(str(payload))
        elif event == "disconnected":
            self.connected = False
            self.disconnect_button.configure(state="disabled")
            self._set_status("Disconnected")
        elif event == "error":
            self._set_status(f"Error: {payload}")
            messagebox.showerror("BLE error", str(payload), parent=self)

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _create_device_card(self, address: str) -> dict[str, Any]:
        frame = tk.Frame(self.device_frame, bg=COLORS["panel_2"], highlightthickness=1, highlightbackground=COLORS["line"], cursor="hand2")
        frame.pack(fill="x", padx=0, pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        top = tk.Frame(frame, bg=COLORS["panel_2"])
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        top.columnconfigure(0, weight=1)
        name = tk.Label(top, text="", bg=COLORS["panel_2"], fg=COLORS["text"], font=("Segoe UI Semibold", 10), anchor="w")
        name.grid(row=0, column=0, sticky="ew")
        rssi = tk.Label(top, text="", bg=COLORS["panel_2"], fg=COLORS["accent_2"], font=("Segoe UI", 9), anchor="e")
        rssi.grid(row=0, column=1, sticky="e", padx=(8, 0))

        address_label = tk.Label(frame, text=address, bg=COLORS["panel_2"], fg=COLORS["muted"], font=("Cascadia Mono", 8), anchor="w")
        address_label.grid(row=1, column=0, sticky="ew", padx=12)

        meta = tk.Frame(frame, bg=COLORS["panel_2"])
        meta.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 10))
        meta.columnconfigure(0, weight=1)
        company = tk.Label(meta, text="", bg=COLORS["panel_2"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="w", wraplength=270, justify="left")
        company.grid(row=0, column=0, sticky="ew")
        appearance = tk.Label(meta, text="", bg=COLORS["panel_2"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="w", wraplength=270, justify="left")
        appearance.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        last = tk.Label(meta, text="", bg=COLORS["panel_2"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="e")
        last.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(8, 0))

        background_widgets = [top, meta, name, rssi, address_label, company, appearance, last]
        for widget in [frame, *background_widgets]:
            widget.bind("<Button-1>", lambda _event, selected=address: self._select_device(selected))
            widget.bind("<Double-Button-1>", lambda _event, selected=address: self._connect_device_card(selected))

        return {
            "frame": frame,
            "name": name,
            "address": address_label,
            "last": last,
            "rssi": rssi,
            "company": company,
            "appearance": appearance,
            "background_widgets": background_widgets,
        }

    def _upsert_device(self, record: DiscoveredDevice) -> None:
        self.devices[record.address] = record
        company_text = ", ".join(manufacturer_names(record.advertisement)) or "Company unknown"
        appearance = BLUETOOTH_NUMBERS.appearance_name(extract_gap_appearance(record.advertisement)) or "Appearance unknown"
        rssi_text = f"{signal_icon(record.rssi)}  {record.rssi if record.rssi is not None else '--'} dBm"
        last_text = format_elapsed(time.time() - record.last_seen)

        if record.address not in self.device_cards:
            self.device_cards[record.address] = self._create_device_card(record.address)

        widgets = self.device_cards[record.address]
        widgets["name"].configure(text=record.name)
        widgets["address"].configure(text=record.address)
        widgets["last"].configure(text=last_text)
        widgets["rssi"].configure(text=rssi_text)
        widgets["company"].configure(text=company_text)
        widgets["appearance"].configure(text=appearance)

    def _tick_elapsed(self) -> None:
        now = time.time()
        for address, record in self.devices.items():
            widgets = self.device_cards.get(address)
            if widgets:
                widgets["last"].configure(text=format_elapsed(now - record.last_seen))
        self.after(1000, self._tick_elapsed)

    def _clear_gatt(self) -> None:
        for child in self.gatt_frame.winfo_children():
            child.destroy()
        self.characteristics_by_handle.clear()
        self.descriptors_by_handle.clear()
        self.char_widgets.clear()
        self.descriptor_widgets.clear()

    def _render_services(self, services: list[ServiceModel]) -> None:
        self.services = services
        self._clear_gatt()
        self.gatt_hint.configure(text=f"{len(services)} services")
        for service in services:
            self._render_service(service)

    def _render_service(self, service: ServiceModel) -> None:
        outer = ttk.Frame(self.gatt_frame, style="Panel.TFrame")
        outer.pack(fill="x", padx=0, pady=(0, 10))
        header = tk.Frame(outer, bg=COLORS["panel_2"], height=42)
        header.pack(fill="x")
        triangle = tk.Label(header, text="▼", bg=COLORS["panel_2"], fg=COLORS["accent"], width=3, font=("Segoe UI", 11))
        triangle.pack(side="left")
        title = tk.Label(header, text=service.name, bg=COLORS["panel_2"], fg=COLORS["text"], font=("Segoe UI Semibold", 11), anchor="w")
        title.pack(side="left", fill="x", expand=True)
        uuid_label = tk.Label(header, text=service.uuid, bg=COLORS["panel_2"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="e")
        uuid_label.pack(side="right", padx=12)

        content = ttk.Frame(outer, style="Panel.TFrame")
        content.pack(fill="x")

        def toggle() -> None:
            if content.winfo_ismapped():
                content.pack_forget()
                triangle.configure(text="▶")
            else:
                content.pack(fill="x")
                triangle.configure(text="▼")

        for widget in (header, triangle, title, uuid_label):
            widget.bind("<Button-1>", lambda _event: toggle())

        for characteristic in service.characteristics:
            self._render_characteristic(content, characteristic)
        for descriptor in service.descriptors:
            self._render_descriptor(content, descriptor, indent=0)

    def _render_characteristic(self, parent: ttk.Frame, characteristic: CharacteristicModel) -> None:
        self.characteristics_by_handle[characteristic.handle] = characteristic
        row = tk.Frame(parent, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["line"])
        row.pack(fill="x", padx=0, pady=(6, 0))

        left = tk.Frame(row, bg=COLORS["panel"])
        left.grid(row=0, column=0, sticky="nsew", padx=12, pady=10)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, minsize=300)

        name_row = tk.Frame(left, bg=COLORS["panel"])
        name_row.pack(anchor="w", fill="x")
        descriptor_triangle = tk.Label(name_row, text=">" if characteristic.descriptors else " ", bg=COLORS["panel"], fg=COLORS["accent"], width=2, font=("Segoe UI", 9))
        descriptor_triangle.pack(side="left")
        name_label = tk.Label(name_row, text=characteristic.name, bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI Semibold", 10), anchor="w")
        name_label.pack(side="left", fill="x", expand=True)
        prop_text = "  ".join(sorted(characteristic.properties)) or "no properties"
        tk.Label(left, text=f"{characteristic.uuid}  •  {prop_text}", bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="w").pack(anchor="w", pady=(3, 0))

        right = tk.Frame(row, bg=COLORS["panel"])
        right.grid(row=0, column=1, sticky="e", padx=12, pady=10)

        value = tk.Label(
            right,
            text=bytes_to_text(characteristic.value, characteristic.display_format) or "unread",
            bg=COLORS["panel_2"],
            fg=COLORS["accent_2"],
            font=("Cascadia Mono", 9),
            padx=10,
            pady=7,
            width=28,
            anchor="e",
        )
        value.pack(side="left", padx=(0, 8))
        value.bind("<Button-3>", lambda event, handle=characteristic.handle: self._show_format_menu(event, handle))

        if "read" in characteristic.properties:
            ttk.Button(right, text="Read", command=lambda char=characteristic: self.bridge.read_characteristic(char.characteristic), style="Ghost.TButton").pack(side="left", padx=3)
        if "write" in characteristic.properties or "write-without-response" in characteristic.properties:
            ttk.Button(right, text="Write", command=lambda char=characteristic: self._open_write_dialog(char), style="Accent.TButton").pack(side="left", padx=3)
        if "notify" in characteristic.properties or "indicate" in characteristic.properties:
            notify_button = ttk.Button(right, text="Notify", command=lambda char=characteristic: self._toggle_notify(char), style="Ghost.TButton")
            notify_button.pack(side="left", padx=3)
        else:
            notify_button = None

        descriptor_content = ttk.Frame(parent, style="Panel.TFrame")

        def toggle_descriptors() -> None:
            if not characteristic.descriptors:
                return
            if descriptor_content.winfo_ismapped():
                descriptor_content.pack_forget()
                descriptor_triangle.configure(text=">")
            else:
                descriptor_content.pack(fill="x", after=row)
                descriptor_triangle.configure(text="v")

        if characteristic.descriptors:
            for widget in (name_row, descriptor_triangle, name_label):
                widget.bind("<Button-1>", lambda _event: toggle_descriptors())
            for descriptor in characteristic.descriptors:
                self._render_descriptor(descriptor_content, descriptor, indent=28)

        self.char_widgets[characteristic.handle] = {"value": value, "notify": notify_button}

    def _render_descriptor(self, parent: ttk.Frame, descriptor: DescriptorModel, indent: int) -> None:
        self.descriptors_by_handle[descriptor.handle] = descriptor
        row = tk.Frame(parent, bg=COLORS["panel_2"], highlightthickness=1, highlightbackground=COLORS["line"])
        row.pack(fill="x", padx=(indent, 0), pady=(4, 0))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, minsize=260)

        left = tk.Frame(row, bg=COLORS["panel_2"])
        left.grid(row=0, column=0, sticky="nsew", padx=12, pady=8)
        tk.Label(left, text=descriptor.name, bg=COLORS["panel_2"], fg=COLORS["text"], font=("Segoe UI Semibold", 9), anchor="w").pack(anchor="w")
        tk.Label(left, text=descriptor.uuid, bg=COLORS["panel_2"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="w").pack(anchor="w", pady=(2, 0))

        right = tk.Frame(row, bg=COLORS["panel_2"])
        right.grid(row=0, column=1, sticky="e", padx=12, pady=8)
        value = tk.Label(
            right,
            text=bytes_to_text(descriptor.value, descriptor.display_format) or "unread",
            bg=COLORS["panel"],
            fg=COLORS["accent_2"],
            font=("Cascadia Mono", 9),
            padx=10,
            pady=6,
            width=24,
            anchor="e",
        )
        value.pack(side="left", padx=(0, 8))
        value.bind("<Button-3>", lambda event, handle=descriptor.handle: self._show_descriptor_format_menu(event, handle))

        ttk.Button(right, text="Read", command=lambda desc=descriptor: self.bridge.read_descriptor(desc.descriptor), style="Ghost.TButton").pack(side="left", padx=3)
        ttk.Button(right, text="Write", command=lambda desc=descriptor: self._open_descriptor_write_dialog(desc), style="Accent.TButton").pack(side="left", padx=3)
        self.descriptor_widgets[descriptor.handle] = {"value": value}

    def _show_format_menu(self, event: tk.Event, handle: int) -> None:
        characteristic = self.characteristics_by_handle[handle]
        menu = tk.Menu(self, tearoff=False, bg=COLORS["panel_2"], fg=COLORS["text"], activebackground=COLORS["accent"], activeforeground="#061018")
        for fmt in ValueFormat:
            menu.add_command(label=fmt.value, command=lambda chosen=fmt: self._set_characteristic_format(handle, chosen))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_descriptor_format_menu(self, event: tk.Event, handle: int) -> None:
        menu = tk.Menu(self, tearoff=False, bg=COLORS["panel_2"], fg=COLORS["text"], activebackground=COLORS["accent"], activeforeground="#061018")
        for fmt in ValueFormat:
            menu.add_command(label=fmt.value, command=lambda chosen=fmt: self._set_descriptor_format(handle, chosen))
        menu.tk_popup(event.x_root, event.y_root)

    def _set_characteristic_format(self, handle: int, fmt: ValueFormat) -> None:
        characteristic = self.characteristics_by_handle[handle]
        characteristic.display_format = fmt
        self._refresh_characteristic_label(handle)

    def _set_descriptor_format(self, handle: int, fmt: ValueFormat) -> None:
        descriptor = self.descriptors_by_handle[handle]
        descriptor.display_format = fmt
        self._refresh_descriptor_label(handle)

    def _refresh_characteristic_label(self, handle: int) -> None:
        characteristic = self.characteristics_by_handle[handle]
        widgets = self.char_widgets.get(handle)
        if widgets:
            widgets["value"].configure(text=bytes_to_text(characteristic.value, characteristic.display_format) or "unread")

    def _refresh_descriptor_label(self, handle: int) -> None:
        descriptor = self.descriptors_by_handle[handle]
        widgets = self.descriptor_widgets.get(handle)
        if widgets:
            widgets["value"].configure(text=bytes_to_text(descriptor.value, descriptor.display_format) or "unread")

    def _update_characteristic_value(self, handle: int, data: bytes) -> None:
        characteristic = self.characteristics_by_handle.get(handle)
        if not characteristic:
            return
        characteristic.value = data
        self._refresh_characteristic_label(handle)

    def _update_descriptor_value(self, handle: int, data: bytes) -> None:
        descriptor = self.descriptors_by_handle.get(handle)
        if not descriptor:
            return
        descriptor.value = data
        self._refresh_descriptor_label(handle)

    def _set_notify_state(self, handle: int, enabled: bool) -> None:
        characteristic = self.characteristics_by_handle.get(handle)
        if not characteristic:
            return
        characteristic.notifying = enabled
        widgets = self.char_widgets.get(handle)
        if widgets and widgets["notify"]:
            widgets["notify"].configure(text="Stop" if enabled else "Notify")

    def _toggle_notify(self, characteristic: CharacteristicModel) -> None:
        self.bridge.toggle_notify(characteristic.characteristic, not characteristic.notifying)

    def _open_write_dialog(self, characteristic: CharacteristicModel) -> None:
        WriteDialog(self, characteristic, lambda data: self.bridge.write_characteristic(characteristic.characteristic, data))

    def _open_descriptor_write_dialog(self, descriptor: DescriptorModel) -> None:
        WriteDialog(self, descriptor, lambda data: self.bridge.write_descriptor(descriptor.descriptor, data))


def main() -> None:
    app = BleDebuggerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
