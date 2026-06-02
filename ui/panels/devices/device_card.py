from __future__ import annotations

from typing import Any

import tkinter as tk

from config import COLORS
from helpers.advertising import extract_gap_appearance, manufacturer_names
from helpers.data.uuids import BLUETOOTH_NUMBERS
from helpers.formatting import signal_icon
from models import DiscoveredDevice
from ui.icons import icon


def create_device_card(app: tk.Tk, address: str) -> dict[str, Any]:
    frame = tk.Frame(app.device_frame, bg=COLORS["panel_2"], highlightthickness=1, highlightbackground=COLORS["line"], cursor="hand2")
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
        widget.bind("<Button-1>", lambda _event, selected=address: app._select_device(selected))
        widget.bind("<Double-Button-1>", lambda _event, selected=address: app._connect_device_card(selected))

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


def update_device_card(app: tk.Tk, widgets: dict[str, Any], record: DiscoveredDevice, last_text: str) -> None:
    company_text = ", ".join(manufacturer_names(record.advertisement)) or "Company unknown"
    appearance = BLUETOOTH_NUMBERS.appearance_name(extract_gap_appearance(record.advertisement)) or "Appearance unknown"
    rssi_text = f"{signal_icon(record.rssi)}  {record.rssi if record.rssi is not None else '--'} dBm"

    widgets["name"].configure(text=record.name)
    widgets["address"].configure(text=record.address)
    widgets["last"].configure(text=last_text)
    signal_image = icon(app, "signal", COLORS["accent_2"], 12)
    if signal_image is None:
        widgets["rssi"].configure(text=rssi_text)
    else:
        widgets["rssi"].configure(image=signal_image, text=f" {record.rssi if record.rssi is not None else '--'} dBm", compound="left")
    widgets["company"].configure(text=company_text)
    widgets["appearance"].configure(text=appearance)
