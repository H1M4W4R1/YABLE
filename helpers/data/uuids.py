from __future__ import annotations

import json
from pathlib import Path
from typing import Any


UUID_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "uuids"
BLUETOOTH_BASE_UUID_SUFFIX = "-0000-1000-8000-00805f9b34fb"


def normalize_uuid(uuid: str) -> str:
    return str(uuid).lower()


def uuid_lookup_keys(uuid: str) -> list[str]:
    normalized = normalize_uuid(uuid)
    keys = [normalized]
    compact = normalized.replace("-", "")
    if len(compact) == 4:
        keys.append(f"0000{compact}{BLUETOOTH_BASE_UUID_SUFFIX}")
    elif len(compact) == 8:
        keys.append(f"{compact}{BLUETOOTH_BASE_UUID_SUFFIX}")
    return keys


class BluetoothNumbers:
    def __init__(self, data_dir: Path = UUID_DATA_DIR) -> None:
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


BLUETOOTH_NUMBERS = BluetoothNumbers()


def friendly_uuid_name(uuid: str, fallback: str) -> str:
    return (
        BLUETOOTH_NUMBERS.service_name(uuid, "")
        or BLUETOOTH_NUMBERS.characteristic_name(uuid, "")
        or BLUETOOTH_NUMBERS.descriptor_name(uuid, "")
        or fallback
    )
