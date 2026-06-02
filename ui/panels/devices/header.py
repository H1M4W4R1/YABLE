from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def build_devices_header(app: tk.Tk, parent: ttk.Frame) -> None:
    header = ttk.Frame(parent, style="Panel.TFrame")
    header.pack(fill="x", padx=14, pady=(14, 8))
    ttk.Label(header, text="Advertised devices", style="Title.TLabel").pack(side="left")
    app.scan_button = ttk.Button(header, text="Start scan", command=app._toggle_scan, style="Accent.TButton")
    app.scan_button.pack(side="right", padx=(8, 0))
    app.connect_button = ttk.Button(
        header,
        text="Connect + GATT",
        command=app._connect_selected,
        style="Ghost.TButton",
        state="disabled",
    )
    app.connect_button.pack(side="right")
