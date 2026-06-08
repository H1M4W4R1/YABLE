from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import COLORS
from helpers.formatting import bytes_to_text
from models import CharacteristicModel
from ui.icons import configure_icon_button, icon
from ui.panels.gatt.descriptor_card import render_descriptor_card


def render_characteristic_card(app: tk.Tk, parent: ttk.Frame, characteristic: CharacteristicModel) -> None:
    app.characteristics_by_handle[characteristic.handle] = characteristic
    row = tk.Frame(parent, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["line"])
    row.pack(fill="x", padx=0, pady=(6, 0))

    left = tk.Frame(row, bg=COLORS["panel"])
    left.grid(row=0, column=0, sticky="nsew", padx=12, pady=10)
    row.columnconfigure(0, weight=1)
    row.columnconfigure(1, minsize=300)

    name_row = tk.Frame(left, bg=COLORS["panel"])
    name_row.pack(anchor="w", fill="x")
    collapsed_icon = icon(app, "chevron-right", COLORS["accent"], 9, scale_to="height") if characteristic.descriptors else None
    expanded_icon = icon(app, "chevron-down", COLORS["accent"], 9, scale_to="height") if characteristic.descriptors else None
    descriptor_triangle = None
    if characteristic.descriptors:
        descriptor_triangle = tk.Label(
            name_row,
            image=collapsed_icon,
            text=">" if collapsed_icon is None else "",
            bg=COLORS["panel"],
            fg=COLORS["accent"],
            width=2 if collapsed_icon is None else 18,
            font=("Segoe UI", 9),
        )
        descriptor_triangle.pack(side="left")
    name_label = tk.Label(name_row, text=characteristic.name, bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI Semibold", 10), anchor="w")
    name_label.pack(side="left", fill="x", expand=True)
    prop_text = "  ".join(sorted(characteristic.properties)) or "no properties"
    tk.Label(left, text=f"{characteristic.uuid}  -  {prop_text}", bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="w").pack(anchor="w", pady=(3, 0))

    right = tk.Frame(row, bg=COLORS["panel"])
    right.grid(row=0, column=1, sticky="e", padx=12, pady=10)

    value = tk.Label(
        right,
        text=bytes_to_text(characteristic.value, characteristic.display_format, characteristic.display_endian) or "unread",
        bg=COLORS["panel_2"],
        fg=COLORS["accent_2"],
        font=("Cascadia Mono", 9),
        padx=10,
        pady=7,
        width=28,
        anchor="e",
    )
    value.pack(side="left", padx=(0, 8))
    value.bind("<Button-3>", lambda event, handle=characteristic.handle: app._show_format_menu(event, handle))

    if "read" in characteristic.properties:
        read_button = ttk.Button(right, text="Read", command=lambda char=characteristic: app.bridge.read_characteristic(char.characteristic), style="Ghost.TButton")
        configure_icon_button(app, read_button, "rotate-right", COLORS["text"])
        read_button.pack(side="left", padx=3)
    if "write" in characteristic.properties or "write-without-response" in characteristic.properties:
        write_button = ttk.Button(right, text="Write", command=lambda char=characteristic: app._open_write_dialog(char), style="Accent.TButton")
        configure_icon_button(app, write_button, "pen-to-square", "#061018")
        write_button.pack(side="left", padx=3)
    if "notify" in characteristic.properties or "indicate" in characteristic.properties:
        notify_button = ttk.Button(right, text="Notify", command=lambda char=characteristic: app._toggle_notify(char), style="Ghost.TButton")
        configure_icon_button(app, notify_button, "bell", COLORS["text"])
        notify_button.pack(side="left", padx=3)
    else:
        notify_button = None

    descriptor_content = ttk.Frame(parent, style="Panel.TFrame")

    def toggle_descriptors() -> None:
        if not characteristic.descriptors:
            return
        if descriptor_content.winfo_ismapped():
            descriptor_content.pack_forget()
            if collapsed_icon is None:
                descriptor_triangle.configure(text=">")
            else:
                descriptor_triangle.configure(image=collapsed_icon, text="")
        else:
            descriptor_content.pack(fill="x", after=row)
            if expanded_icon is None:
                descriptor_triangle.configure(text="v")
            else:
                descriptor_triangle.configure(image=expanded_icon, text="")

    if characteristic.descriptors:
        assert descriptor_triangle is not None
        for widget in (name_row, descriptor_triangle, name_label):
            widget.bind("<Button-1>", lambda _event: toggle_descriptors())
        for descriptor in characteristic.descriptors:
            render_descriptor_card(app, descriptor_content, descriptor, indent=28)

    app.char_widgets[characteristic.handle] = {"value": value, "notify": notify_button}
