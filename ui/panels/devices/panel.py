from __future__ import annotations

import time
from typing import Any

import tkinter as tk
from tkinter import ttk

from config import COLORS
from helpers.formatting import format_elapsed
from models import DiscoveredDevice
from ui.panels.devices.device_card import create_device_card, update_device_card
from ui.panels.devices.header import build_devices_header
from ui.resize_visibility import handle_canvas_resize
from ui.scrolling import bind_canvas_mousewheel


def build_devices_panel(app: tk.Tk, parent: ttk.Frame) -> None:
    build_devices_header(app, parent)

    app.device_canvas = tk.Canvas(parent, bg=COLORS["panel"], highlightthickness=0)
    app.device_canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 14))
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=app.device_canvas.yview)
    scrollbar.pack(side="right", fill="y", padx=(0, 14), pady=(0, 14))
    app.device_canvas.configure(yscrollcommand=scrollbar.set)
    app.device_frame = ttk.Frame(app.device_canvas, style="Panel.TFrame")
    app.device_canvas_window = app.device_canvas.create_window((0, 0), window=app.device_frame, anchor="nw")
    app.device_frame.bind("<Configure>", lambda _: app.device_canvas.configure(scrollregion=app.device_canvas.bbox("all")))
    app.device_canvas.bind("<Configure>", lambda event: handle_canvas_resize(app, app.device_canvas, app.device_canvas_window, event.width))
    bind_canvas_mousewheel(app.device_canvas)


def select_device(app: tk.Tk, address: str) -> None:
    app.selected_address = address
    app.connect_button.configure(state="normal")
    for card_address, widgets in app.device_cards.items():
        selected = card_address == address
        bg = COLORS["panel_3"] if selected else COLORS["panel_2"]
        border = COLORS["accent"] if selected else COLORS["line"]
        widgets["frame"].configure(bg=bg, highlightbackground=border)
        for widget in widgets.get("background_widgets", []):
            widget.configure(bg=bg)


def upsert_device(app: tk.Tk, record: DiscoveredDevice) -> None:
    app.devices[record.address] = record
    if record.address not in app.device_cards:
        app.device_cards[record.address] = create_device_card(app, record.address)
    update_device_card(app, app.device_cards[record.address], record, format_elapsed(time.time() - record.last_seen))


def tick_elapsed(app: tk.Tk) -> None:
    now = time.time()
    for address, record in app.devices.items():
        widgets: dict[str, Any] | None = app.device_cards.get(address)
        if widgets:
            widgets["last"].configure(text=format_elapsed(now - record.last_seen))
    app.after(1000, app._tick_elapsed)
