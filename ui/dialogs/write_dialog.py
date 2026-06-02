from __future__ import annotations

from typing import Callable

import tkinter as tk
from tkinter import messagebox, ttk

from config import COLORS
from helpers.formatting import FORMAT_LABELS, ValueFormat, bytes_to_text, text_to_bytes
from models import CharacteristicModel, DescriptorModel


class WriteDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, target: CharacteristicModel | DescriptorModel, on_write: Callable[[bytes], None]) -> None:
        super().__init__(parent)
        self.target = target
        self.on_write = on_write
        self.title(f"Write {target.name}")
        self.configure(bg=COLORS["panel"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.format_var = tk.StringVar(value=target.display_format.value)
        self.value_var = tk.StringVar(value=bytes_to_text(target.value, target.display_format))

        ttk.Label(self, text=target.name, style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(18, 4))
        ttk.Label(self, text=target.uuid, style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 14))
        ttk.Label(self, text="Format").grid(row=2, column=0, sticky="w", padx=18, pady=6)
        format_box = ttk.Combobox(self, values=FORMAT_LABELS, textvariable=self.format_var, state="readonly", width=18)
        format_box.grid(row=2, column=1, sticky="ew", padx=18, pady=6)
        ttk.Label(self, text="Value").grid(row=3, column=0, sticky="nw", padx=18, pady=6)
        self.entry = tk.Text(
            self,
            height=5,
            width=48,
            bg=COLORS["panel_2"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat",
            padx=10,
            pady=10,
        )
        self.entry.grid(row=3, column=1, sticky="ew", padx=18, pady=6)
        self.entry.insert("1.0", self.value_var.get())
        self.entry.focus_set()

        button_row = ttk.Frame(self, style="Panel.TFrame")
        button_row.grid(row=4, column=0, columnspan=2, sticky="e", padx=18, pady=(12, 18))
        ttk.Button(button_row, text="Cancel", command=self.destroy, style="Ghost.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Write", command=self._write, style="Accent.TButton").pack(side="left")

    def _write(self) -> None:
        try:
            data = text_to_bytes(self.entry.get("1.0", "end").strip(), ValueFormat(self.format_var.get()))
        except Exception as exc:
            messagebox.showerror("Invalid value", str(exc), parent=self)
            return
        self.on_write(data)
        self.destroy()
