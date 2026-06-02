from __future__ import annotations

import tkinter as tk


RESTORE_DELAY_MS = 140


def begin_panel_resize(app: tk.Tk) -> None:
    app._panel_resize_active = True
    if app._panel_resize_restore_job is not None:
        app.after_cancel(app._panel_resize_restore_job)
        app._panel_resize_restore_job = None
    _set_panel_contents_state(app, "hidden")


def schedule_panel_restore(app: tk.Tk) -> None:
    if app._panel_resize_restore_job is not None:
        app.after_cancel(app._panel_resize_restore_job)
    app._panel_resize_restore_job = app.after(RESTORE_DELAY_MS, lambda: finish_panel_resize(app))


def finish_panel_resize(app: tk.Tk) -> None:
    app._panel_resize_restore_job = None
    app._panel_resize_active = False
    _set_panel_contents_state(app, "normal")
    _refresh_scrollregions(app)


def handle_canvas_resize(app: tk.Tk, canvas: tk.Canvas, window_id: int, width: int) -> None:
    begin_panel_resize(app)
    canvas.itemconfigure(window_id, width=width)
    schedule_panel_restore(app)


def _set_panel_contents_state(app: tk.Tk, state: str) -> None:
    for canvas_name, window_name in (("device_canvas", "device_canvas_window"), ("canvas", "canvas_window")):
        canvas = getattr(app, canvas_name, None)
        window_id = getattr(app, window_name, None)
        if canvas is not None and window_id is not None:
            canvas.itemconfigure(window_id, state=state)


def _refresh_scrollregions(app: tk.Tk) -> None:
    if hasattr(app, "device_canvas"):
        app.device_canvas.configure(scrollregion=app.device_canvas.bbox("all"))
    if hasattr(app, "canvas"):
        app.canvas.configure(scrollregion=app.canvas.bbox("all"))
