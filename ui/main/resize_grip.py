from __future__ import annotations

import tkinter as tk

from config import COLORS
from ui.resize_visibility import begin_panel_resize, schedule_panel_restore


def build_resize_grip(app: tk.Tk) -> None:
    grip = tk.Canvas(app, width=14, height=14, bg=COLORS["bg"], highlightthickness=0, cursor="bottom_right_corner")
    grip.place(relx=1.0, rely=1.0, x=-3, y=-3, anchor="se")
    grip.create_line(5, 12, 12, 5, fill=COLORS["panel_3"], width=1)
    grip.create_line(8, 12, 12, 8, fill=COLORS["line"], width=1)
    grip.create_line(11, 12, 12, 11, fill=COLORS["muted"], width=1)
    grip.bind("<ButtonPress-1>", lambda event: begin_resize(app, event))
    grip.bind("<B1-Motion>", lambda event: resize_window(app, event))
    grip.bind("<ButtonRelease-1>", lambda _event: schedule_panel_restore(app))


def begin_resize(app: tk.Tk, event: tk.Event) -> None:
    if app._is_maximized:
        return
    app._resize_start_x = event.x_root
    app._resize_start_y = event.y_root
    app._resize_start_width = app.winfo_width()
    app._resize_start_height = app.winfo_height()
    begin_panel_resize(app)


def resize_window(app: tk.Tk, event: tk.Event) -> None:
    if app._is_maximized:
        return
    begin_panel_resize(app)
    width, height = resize_dimensions(app, event)
    app.geometry(f"{width}x{height}")
    schedule_panel_restore(app)


def resize_dimensions(app: tk.Tk, event: tk.Event) -> tuple[int, int]:
    min_width, min_height = app.minsize()
    width = max(min_width, app._resize_start_width + event.x_root - app._resize_start_x)
    height = max(min_height, app._resize_start_height + event.y_root - app._resize_start_y)
    return width, height
