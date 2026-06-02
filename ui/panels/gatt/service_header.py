from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import COLORS
from models import ServiceModel
from ui.icons import icon


def render_service_header(app: tk.Tk, parent: ttk.Frame, service: ServiceModel) -> ttk.Frame:
    outer = ttk.Frame(parent, style="Panel.TFrame")
    outer.pack(fill="x", padx=0, pady=(0, 10))
    header = tk.Frame(outer, bg=COLORS["panel_2"], height=42)
    header.pack(fill="x")
    expanded_icon = icon(app, "chevron-down", COLORS["accent"], 10, scale_to="height")
    collapsed_icon = icon(app, "chevron-right", COLORS["accent"], 10, scale_to="height")
    triangle = tk.Label(
        header,
        image=expanded_icon,
        text="v" if expanded_icon is None else "",
        bg=COLORS["panel_2"],
        fg=COLORS["accent"],
        width=2 if expanded_icon is None else 28,
        font=("Segoe UI", 11),
    )
    triangle.pack(side="left")
    title = tk.Label(header, text=service.name, bg=COLORS["panel_2"], fg=COLORS["text"], font=("Segoe UI Semibold", 11), anchor="w")
    title.pack(side="left", fill="x", expand=True)
    uuid_label = tk.Label(header, text=service.uuid, bg=COLORS["panel_2"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="e")
    uuid_label.pack(side="right", padx=12)

    content = ttk.Frame(outer, style="Panel.TFrame")
    content.pack(fill="x")

    def toggle() -> None:
        if content.winfo_ismapped():
            content.pack_forget()
            if collapsed_icon is None:
                triangle.configure(text=">")
            else:
                triangle.configure(image=collapsed_icon, text="")
        else:
            content.pack(fill="x")
            if expanded_icon is None:
                triangle.configure(text="v")
            else:
                triangle.configure(image=expanded_icon, text="")

    for widget in (header, triangle, title, uuid_label):
        widget.bind("<Button-1>", lambda _event: toggle())

    return content
