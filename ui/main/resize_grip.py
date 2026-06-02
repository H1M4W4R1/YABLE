from __future__ import annotations

import tkinter as tk

from config import COLORS


def build_resize_grip(app: tk.Tk) -> None:
    grip = tk.Canvas(app, width=20, height=20, bg=COLORS["bg"], highlightthickness=0, cursor="bottom_right_corner")
    grip.place(relx=1.0, rely=1.0, anchor="se")
    grip.create_line(9, 17, 17, 9, fill=COLORS["line"], width=1)
    grip.create_line(13, 17, 17, 13, fill=COLORS["muted"], width=1)
    grip.create_line(5, 17, 17, 5, fill=COLORS["panel_3"], width=1)
    grip.bind("<ButtonPress-1>", lambda event: begin_resize(app, event))
    grip.bind("<B1-Motion>", lambda event: resize_window(app, event))


def begin_resize(app: tk.Tk, event: tk.Event) -> None:
    if app._is_maximized:
        return
    app._resize_start_x = event.x_root
    app._resize_start_y = event.y_root
    app._resize_start_width = app.winfo_width()
    app._resize_start_height = app.winfo_height()


def resize_window(app: tk.Tk, event: tk.Event) -> None:
    if app._is_maximized:
        return
    min_width, min_height = app.minsize()
    width = max(min_width, app._resize_start_width + event.x_root - app._resize_start_x)
    height = max(min_height, app._resize_start_height + event.y_root - app._resize_start_y)
    app.geometry(f"{width}x{height}")
