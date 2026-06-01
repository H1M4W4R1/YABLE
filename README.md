<div align="center">
  <h1>Yet Another Bluetooth Low Energy (Debugger)</h1>
  <img src="https://github.com/H1M4W4R1/YABLE/blob/master/gh_images/screenshot.png" alt="Preview screenshot"/>
</div>


YABLE is a small desktop BLE debugging application for scanning nearby Bluetooth Low Energy devices, connecting to them, discovering GATT, and inspecting or changing characteristic values.

## Features

- Live BLE advertisement scanning.
- Device list with last advertisement age, RSSI value, and signal strength icon.
- Connect and discover GATT services from the selected device.
- Foldout service groups with characteristics listed below each service.
- Friendly service and characteristic names when standard UUIDs or user description descriptors are available.
- Read characteristic values when `read` is supported.
- Write characteristic values when `write` or `write-without-response` is supported.
- Enable and stop notifications or indications when available.
- Switch displayed value format from the characteristic context menu:
  - `HEX`
  - `DEC`
  - `OCT`
  - `BIN`
  - `ASCII`
  - `DATETIME`
- Use the same formats in the write dialog.
- Modern dark interface with cyan accents.

## Requirements

- Windows with Bluetooth LE support.
- Python 3.11 or newer.
- Python packages from `requirements.txt`.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Usage

```powershell
.\.venv\Scripts\python.exe main.py
```

Then:

1. Click `Start scan`.
2. Select an advertised BLE device.
3. Click `Connect + GATT`.
4. Expand services and inspect characteristics.
5. Right-click a characteristic value to change its display format.

## Notes

- BLE access depends on the operating system Bluetooth stack and adapter permissions.
- Some devices do not expose readable names or readable characteristic values.
- Writes and notifications are only shown when the characteristic properties advertise support for them.

## License

This project is licensed under the [WTFPL](LICENSE.md).
