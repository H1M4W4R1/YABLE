from __future__ import annotations

from typing import Callable

import tkinter as tk
from tkinter import ttk

from config import COLORS


def build_main_header(app: tk.Tk) -> None:
    chrome = tk.Frame(app, bg=COLORS["bg"], height=38)
    chrome.pack(fill="x")
    chrome.pack_propagate(False)
    chrome.bind("<ButtonPress-1>", app._begin_window_drag)
    chrome.bind("<B1-Motion>", app._drag_window)

    logo = tk.Canvas(chrome, width=42, height=28, bg=COLORS["bg"], highlightthickness=0)
    logo.pack(side="left", padx=(16, 4), pady=5)
    logo.create_oval(5, 7, 19, 21, outline=COLORS["accent"], width=2)
    logo.create_oval(20, 7, 34, 21, outline=COLORS["accent_2"], width=2)
    logo.create_line(15, 14, 24, 14, fill=COLORS["text"], width=2)
    logo.create_line(28, 7, 34, 14, fill=COLORS["accent_2"], width=2)
    logo.create_line(28, 21, 34, 14, fill=COLORS["accent_2"], width=2)
    logo.bind("<ButtonPress-1>", app._begin_window_drag)
    logo.bind("<B1-Motion>", app._drag_window)

    app.status_label = ttk.Label(chrome, text="Ready", style="MutedBg.TLabel")
    app.status_label.pack(side="left", padx=(8, 0))
    app.status_label.bind("<ButtonPress-1>", app._begin_window_drag)
    app.status_label.bind("<B1-Motion>", app._drag_window)

    window_controls = tk.Frame(chrome, bg=COLORS["bg"])
    window_controls.pack(side="right", padx=(0, 8))
    make_window_button(window_controls, "-", app._minimize_window).pack(side="left")
    app.maximize_button = make_window_button(window_controls, "[]", app._toggle_maximize)
    app.maximize_button.pack(side="left")
    make_window_button(window_controls, "X", app.destroy, danger=True).pack(side="left")


def make_window_button(parent: tk.Frame, text: str, command: Callable[[], None], danger: bool = False) -> tk.Label:
    label = tk.Label(
        parent,
        text=text,
        width=4,
        height=1,
        bg=COLORS["bg"],
        fg=COLORS["danger"] if danger else COLORS["muted"],
        font=("Segoe UI Semibold", 12),
        cursor="hand2",
    )
    label.bind("<Button-1>", lambda _event: command())
    label.bind("<Enter>", lambda _event: label.configure(bg="#2b1518" if danger else COLORS["panel_3"], fg=COLORS["text"]))
    label.bind("<Leave>", lambda _event: label.configure(bg=COLORS["bg"], fg=COLORS["danger"] if danger else COLORS["muted"]))
    return label
