from __future__ import annotations

import binascii
from datetime import datetime, timezone
from enum import Enum


class ValueEndian(str, Enum):
    LITTLE = "LE"
    BIG = "BE"

    @property
    def byteorder(self) -> str:
        return "little" if self == ValueEndian.LITTLE else "big"


class ValueFormat(str, Enum):
    HEX = "HEX"
    RAW = "RAW"
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


def bytes_to_text(data: bytes | bytearray | None, fmt: ValueFormat, endian: ValueEndian = ValueEndian.LITTLE) -> str:
    if data is None:
        return ""
    raw = bytes(data)
    if not raw:
        return "(empty)"

    number = int.from_bytes(raw, endian.byteorder, signed=False)
    if fmt == ValueFormat.HEX:
        width = max(1, len(raw) * 2)
        return f"0x{number:0{width}X}"
    if fmt == ValueFormat.RAW:
        return " ".join(f"{byte:02X}" for byte in raw)
    if fmt == ValueFormat.DEC:
        return str(number)
    if fmt == ValueFormat.OCT:
        return f"0o{number:o}"
    if fmt == ValueFormat.BIN:
        width = max(1, len(raw) * 8)
        return f"0b{number:0{width}b}"
    if fmt == ValueFormat.ASCII:
        return "".join(chr(byte) if 32 <= byte < 127 else "." for byte in raw)
    if fmt == ValueFormat.DATETIME:
        if len(raw) in (4, 8):
            try:
                return datetime.fromtimestamp(number, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
            except (OverflowError, OSError, ValueError):
                pass
        return "not a Unix timestamp"
    return binascii.hexlify(raw).decode("ascii").upper()


def text_to_bytes(text: str, fmt: ValueFormat, endian: ValueEndian = ValueEndian.LITTLE, byte_length: int | None = None) -> bytes:
    value = text.strip()
    if fmt == ValueFormat.HEX:
        number = _parse_number(value, 16)
        return _number_to_bytes(number, endian, byte_length)
    if fmt == ValueFormat.RAW:
        compact = value.replace(" ", "").replace("0x", "").replace("0X", "").replace(",", "")
        if len(compact) % 2:
            compact = "0" + compact
        return bytes.fromhex(compact)
    if fmt == ValueFormat.DEC:
        number = _parse_number(value, 10)
        return _number_to_bytes(number, endian, byte_length)
    if fmt == ValueFormat.OCT:
        number = _parse_number(value, 8)
        return _number_to_bytes(number, endian, byte_length)
    if fmt == ValueFormat.BIN:
        number = _parse_number(value, 2)
        return _number_to_bytes(number, endian, byte_length)
    if fmt == ValueFormat.ASCII:
        return value.encode("utf-8")
    if fmt == ValueFormat.DATETIME:
        if value.isdigit():
            epoch = int(value)
        else:
            parsed = datetime.fromisoformat(value)
            epoch = int(parsed.timestamp())
        length = byte_length if byte_length in (4, 8) else 4
        return epoch.to_bytes(length, endian.byteorder, signed=False)
    raise ValueError(f"Unsupported format: {fmt}")


def _parse_number(value: str, base: int) -> int:
    prefixes = {2: "0b", 8: "0o", 16: "0x"}
    compact = value.replace("_", "").replace(" ", "").replace(",", "")
    prefix = prefixes.get(base)
    if prefix and compact.lower().startswith(prefix):
        compact = compact[2:]
    if not compact:
        return 0
    number = int(compact, base)
    if number < 0:
        raise ValueError("Negative values are not supported")
    return number


def _number_to_bytes(number: int, endian: ValueEndian, byte_length: int | None) -> bytes:
    length = byte_length or max(1, (number.bit_length() + 7) // 8)
    try:
        return number.to_bytes(length, endian.byteorder, signed=False)
    except OverflowError as exc:
        raise ValueError(f"Value does not fit in {length} byte(s)") from exc
