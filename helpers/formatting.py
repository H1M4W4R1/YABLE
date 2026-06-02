from __future__ import annotations

import binascii
from datetime import datetime, timezone
from enum import Enum


class ValueFormat(str, Enum):
    HEX = "HEX"
    DEC = "DEC"
    OCT = "OCT"
    BIN = "BIN"
    ASCII = "ASCII"
    DATETIME = "DATETIME"


FORMAT_LABELS = [fmt.value for fmt in ValueFormat]


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
        return "----"
    if rssi >= -55:
        return "best"
    if rssi >= -70:
        return "good"
    if rssi >= -85:
        return "fair"
    return "weak"


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
