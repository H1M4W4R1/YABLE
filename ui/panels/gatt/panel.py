from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import COLORS
from models import ServiceModel
from ui.panels.gatt.characteristic_card import render_characteristic_card
from ui.panels.gatt.descriptor_card import render_descriptor_card
from ui.panels.gatt.header import build_gatt_header
from ui.panels.gatt.service_header import render_service_header
from ui.resize_visibility import handle_canvas_resize
from ui.scrolling import bind_canvas_mousewheel


def build_gatt_panel(app: tk.Tk, parent: ttk.Frame) -> None:
    build_gatt_header(app, parent)

    app.canvas = tk.Canvas(parent, bg=COLORS["panel"], highlightthickness=0)
    app.canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 14))
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=app.canvas.yview)
    scrollbar.pack(side="right", fill="y", padx=(0, 14), pady=(0, 14))
    app.canvas.configure(yscrollcommand=scrollbar.set)
    app.gatt_frame = ttk.Frame(app.canvas, style="Panel.TFrame")
    app.canvas_window = app.canvas.create_window((0, 0), window=app.gatt_frame, anchor="nw")
    app.gatt_frame.bind("<Configure>", lambda _: app.canvas.configure(scrollregion=app.canvas.bbox("all")))
    app.canvas.bind("<Configure>", lambda event: handle_canvas_resize(app, app.canvas, app.canvas_window, event.width))
    bind_canvas_mousewheel(app.canvas)


def clear_gatt(app: tk.Tk) -> None:
    for child in app.gatt_frame.winfo_children():
        child.destroy()
    app.characteristics_by_handle.clear()
    app.descriptors_by_handle.clear()
    app.char_widgets.clear()
    app.descriptor_widgets.clear()


def render_services(app: tk.Tk, services: list[ServiceModel]) -> None:
    app.services = services
    clear_gatt(app)
    app.gatt_hint.configure(text=f"{len(services)} services")
    for service in services:
        render_service(app, service)


def render_service(app: tk.Tk, service: ServiceModel) -> None:
    content = render_service_header(app, app.gatt_frame, service)
    for characteristic in service.characteristics:
        if characteristic.hidden:
            continue
        render_characteristic_card(app, content, characteristic)
    for descriptor in service.descriptors:
        render_descriptor_card(app, content, descriptor, indent=0)
