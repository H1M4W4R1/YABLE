from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from config import COLORS
from helpers.formatting import bytes_to_text
from models import DescriptorModel
from ui.icons import configure_icon_button


def render_descriptor_card(app: tk.Tk, parent: ttk.Frame, descriptor: DescriptorModel, indent: int) -> None:
    app.descriptors_by_handle[descriptor.handle] = descriptor
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
        text=bytes_to_text(descriptor.value, descriptor.display_format, descriptor.display_endian) or "unread",
        bg=COLORS["panel"],
        fg=COLORS["accent_2"],
        font=("Cascadia Mono", 9),
        padx=10,
        pady=6,
        width=24,
        anchor="e",
    )
    value.pack(side="left", padx=(0, 8))
    value.bind("<Button-3>", lambda event, handle=descriptor.handle: app._show_descriptor_format_menu(event, handle))

    read_button = ttk.Button(right, text="Read", command=lambda desc=descriptor: app.bridge.read_descriptor(desc.descriptor), style="Ghost.TButton")
    configure_icon_button(app, read_button, "rotate-right", COLORS["text"])
    read_button.pack(side="left", padx=3)
    write_button = ttk.Button(right, text="Write", command=lambda desc=descriptor: app._open_descriptor_write_dialog(desc), style="Accent.TButton")
    configure_icon_button(app, write_button, "pen-to-square", "#061018")
    write_button.pack(side="left", padx=3)
    app.descriptor_widgets[descriptor.handle] = {"value": value}
