from __future__ import annotations

from typing import Any

from helpers.data.uuids import BLUETOOTH_NUMBERS


def manufacturer_names(advertisement: Any | None) -> list[str]:
    manufacturer_data = getattr(advertisement, "manufacturer_data", None) or {}
    return [BLUETOOTH_NUMBERS.company_name(int(company_id)) for company_id in sorted(manufacturer_data)]


def extract_gap_appearance(advertisement: Any | None) -> int | None:
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
