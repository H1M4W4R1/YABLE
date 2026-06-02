from __future__ import annotations

import tkinter as tk


def bind_canvas_mousewheel(canvas: tk.Canvas) -> None:
    canvas.bind_all("<MouseWheel>", lambda event: _scroll_if_pointer_inside(canvas, event), add=True)
    canvas.bind_all("<Button-4>", lambda event: _scroll_if_pointer_inside(canvas, event), add=True)
    canvas.bind_all("<Button-5>", lambda event: _scroll_if_pointer_inside(canvas, event), add=True)


def _scroll_if_pointer_inside(canvas: tk.Canvas, event: tk.Event) -> str | None:
    if not _pointer_inside(canvas, event):
        return None

    if getattr(event, "num", None) == 4:
        units = -1
    elif getattr(event, "num", None) == 5:
        units = 1
    else:
        delta = getattr(event, "delta", 0)
        units = -1 if delta > 0 else 1

    canvas.yview_scroll(units, "units")
    return "break"


def _pointer_inside(widget: tk.Widget, event: tk.Event) -> bool:
    x = event.x_root
    y = event.y_root
    left = widget.winfo_rootx()
    top = widget.winfo_rooty()
    return left <= x < left + widget.winfo_width() and top <= y < top + widget.winfo_height()
