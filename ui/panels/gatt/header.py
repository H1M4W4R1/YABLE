from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import COLORS
from ui.icons import configure_icon_button


def build_gatt_header(app: tk.Tk, parent: ttk.Frame) -> None:
    header = ttk.Frame(parent, style="Panel.TFrame")
    header.pack(fill="x", padx=14, pady=(14, 8))
    ttk.Label(header, text="GATT", style="Title.TLabel").pack(side="left")
    app.disconnect_button = ttk.Button(header, text="Disconnect", command=app._disconnect, style="Ghost.TButton", state="disabled")
    configure_icon_button(app, app.disconnect_button, "power-off", COLORS["text"])
    app.disconnect_button.pack(side="right", padx=(8, 0))
    app.gatt_hint = ttk.Label(header, text="Connect to a device to discover services", style="Muted.TLabel")
    app.gatt_hint.pack(side="right")
