from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

try:
    from tkfontawesome import icon_to_image
except ImportError:  # pragma: no cover - app can still show text before deps install
    icon_to_image = None


def icon(app: tk.Misc, name: str, fill: str, size: int, scale_to: str = "width") -> Any | None:
    if icon_to_image is None:
        return None
    try:
        if scale_to == "height":
            image = icon_to_image(name, fill=fill, scale_to_height=size)
        else:
            image = icon_to_image(name, fill=fill, scale_to_width=size)
    except Exception:
        return None
    root = app.winfo_toplevel()
    if not hasattr(root, "_icon_images"):
        root._icon_images = []
    root._icon_images.append(image)
    return image


def configure_icon_button(
    app: tk.Misc,
    button: ttk.Button,
    icon_name: str,
    fill: str,
    size: int = 14,
    compound: str = "left",
    gap: bool = True,
) -> None:
    image = icon(app, icon_name, fill, size)
    if image is not None:
        if gap:
            text = str(button.cget("text"))
            if text and not text.startswith("  "):
                button.configure(text=f"  {text}")
        button.configure(image=image, compound=compound)


def icon_label(
    app: tk.Misc,
    parent: tk.Misc,
    icon_name: str,
    fill: str,
    size: int,
    fallback: str,
    **kwargs: Any,
) -> tk.Label:
    image = icon(app, icon_name, fill, size)
    if image is None:
        return tk.Label(parent, text=fallback, **kwargs)
    return tk.Label(parent, image=image, **kwargs)
