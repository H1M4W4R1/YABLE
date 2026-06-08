from __future__ import annotations

import queue
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

from ble.bridge import AsyncBleBridge
from config import APP_TITLE, COLORS
from helpers.formatting import ValueFormat, bytes_to_text
from models import CharacteristicModel, DescriptorModel, DiscoveredDevice, ServiceModel
from ui.dialogs.write_dialog import WriteDialog
from ui.main.header import build_main_header
from ui.main.resize_grip import build_resize_grip
from ui.panels.devices.panel import build_devices_panel, refresh_device_card_states, select_device, tick_elapsed, upsert_device
from ui.panels.gatt.panel import build_gatt_panel, clear_gatt, render_service, render_services


class BleDebuggerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1220x760")
        self.minsize(980, 620)
        self._configure_borderless_window()
        self.configure(bg=COLORS["bg"])

        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.bridge = AsyncBleBridge(self._emit)
        self.devices: dict[str, DiscoveredDevice] = {}
        self.device_cards: dict[str, dict[str, Any]] = {}
        self.services: list[ServiceModel] = []
        self.characteristics_by_handle: dict[int, CharacteristicModel] = {}
        self.descriptors_by_handle: dict[int, DescriptorModel] = {}
        self.char_widgets: dict[int, dict[str, Any]] = {}
        self.descriptor_widgets: dict[int, dict[str, Any]] = {}
        self.scan_running = False
        self.connected = False
        self.selected_address: str | None = None
        self.connecting_address: str | None = None
        self.connected_address: str | None = None
        self._normal_geometry = ""
        self._is_maximized = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_width = 0
        self._resize_start_height = 0
        self._panel_resize_active = False
        self._panel_resize_restore_job: str | None = None
        self._borderless_restore_pending = False

        self._configure_styles()
        self._build_layout()
        self._poll_events()
        self._tick_elapsed()
        self.bind("<Map>", self._restore_frameless_chrome)

    def _configure_borderless_window(self) -> None:
        windowing_system = self.tk.call("tk", "windowingsystem")

        if windowing_system == "win32":
            try:
                self.wm_attributes("-toolwindow", False)
            except tk.TclError:
                pass
        elif windowing_system == "x11":
            try:
                self.wm_attributes("-type", "normal")
            except tk.TclError:
                pass

        self.overrideredirect(True)

    def _emit(self, event: str, payload: Any) -> None:
        self.events.put((event, payload))

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], fieldbackground=COLORS["panel_2"], font=("Segoe UI", 10))
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Surface.TFrame", background=COLORS["panel_2"])
        style.configure("TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("MutedBg.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI Semibold", 12))
        style.configure("Hero.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI Semibold", 18))
        style.configure("Accent.TButton", background=COLORS["accent"], foreground="#061018", borderwidth=0, focusthickness=0, padding=(14, 8), font=("Segoe UI Semibold", 10))
        style.map("Accent.TButton", background=[("active", COLORS["accent_2"]), ("disabled", COLORS["panel_3"])])
        style.configure("Ghost.TButton", background=COLORS["panel_3"], foreground=COLORS["text"], borderwidth=0, padding=(12, 7))
        style.map("Ghost.TButton", background=[("active", "#263244"), ("disabled", COLORS["panel_2"])])
        style.configure("Treeview", background=COLORS["panel_2"], foreground=COLORS["text"], fieldbackground=COLORS["panel_2"], borderwidth=0, rowheight=32)
        style.configure("Treeview.Heading", background=COLORS["panel"], foreground=COLORS["muted"], relief="flat", font=("Segoe UI Semibold", 9))
        style.map("Treeview", background=[("selected", "#12303b")], foreground=[("selected", COLORS["text"])])
        style.configure("Vertical.TScrollbar", background=COLORS["panel_3"], troughcolor=COLORS["panel"], arrowcolor=COLORS["accent"])
        style.configure("TCombobox", borderwidth=0, arrowsize=14, padding=6)

    def _build_layout(self) -> None:
        build_main_header(self)

        body = tk.PanedWindow(self, orient="horizontal", bg=COLORS["bg"], sashwidth=6, bd=0, relief="flat")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        left = ttk.Frame(body, style="Panel.TFrame")
        right = ttk.Frame(body, style="Panel.TFrame")
        body.add(left, minsize=390, width=430)
        body.add(right, minsize=540)

        build_devices_panel(self, left)
        build_gatt_panel(self, right)
        build_resize_grip(self)

    def _begin_window_drag(self, event: tk.Event) -> None:
        if self._is_maximized:
            return
        self._drag_start_x = event.x_root - self.winfo_x()
        self._drag_start_y = event.y_root - self.winfo_y()

    def _drag_window(self, event: tk.Event) -> None:
        if self._is_maximized:
            return
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.geometry(f"+{x}+{y}")

    def _minimize_window(self) -> None:
        self._borderless_restore_pending = True
        self.overrideredirect(False)
        self.update_idletasks()
        try:
            self.iconify()
        except tk.TclError:
            self._borderless_restore_pending = False
            self._configure_borderless_window()

    def _restore_frameless_chrome(self, _event: tk.Event | None = None) -> None:
        if not self._borderless_restore_pending:
            return
        if self.state() != "normal":
            return
        self._borderless_restore_pending = False
        self.after(10, self._configure_borderless_window)

    def _toggle_maximize(self) -> None:
        if self._is_maximized:
            self.geometry(self._normal_geometry)
            self._is_maximized = False
            if getattr(self, "maximize_icon", None) is None:
                self.maximize_button.configure(text="[]")
            else:
                self.maximize_button.configure(image=self.maximize_icon, text="")
            return
        self._normal_geometry = self.geometry()
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        self.geometry(f"{width}x{height}+0+0")
        self._is_maximized = True
        if getattr(self, "restore_icon", None) is None:
            self.maximize_button.configure(text="[ ]")
        else:
            self.maximize_button.configure(image=self.restore_icon, text="")

    def _toggle_scan(self) -> None:
        if self.scan_running:
            self.bridge.stop_scan()
        else:
            self.bridge.start_scan()
            self._set_status("Scanning for advertisements...")

    def _connect_selected(self) -> None:
        if not self.selected_address:
            return
        self.connect_button.configure(state="disabled")
        self.connecting_address = self.selected_address
        self.bridge.connect(self.selected_address)

    def _connect_device_card(self, address: str) -> None:
        self._select_device(address)
        self._connect_selected()

    def _disconnect(self) -> None:
        self.bridge.disconnect()

    def _select_device(self, address: str) -> None:
        select_device(self, address)

    def _poll_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event, payload)
        self.after(80, self._poll_events)

    def _handle_event(self, event: str, payload: Any) -> None:
        if event == "missing_dependency":
            self._set_status("Install dependencies with: python -m pip install -r requirements.txt")
            messagebox.showerror("Missing dependency", "The bleak package is required for BLE access.\n\nRun: python -m pip install -r requirements.txt", parent=self)
        elif event == "scan_state":
            self.scan_running = bool(payload)
            self.scan_button.configure(text="Stop scan" if self.scan_running else "Start scan")
        elif event == "device":
            self._upsert_device(payload)
        elif event == "connection_state":
            self._set_status(str(payload))
        elif event == "services":
            self.connected = True
            self.connected_address = self.connecting_address or self.selected_address
            self.connecting_address = None
            self.disconnect_button.configure(state="normal")
            refresh_device_card_states(self)
            self._render_services(payload)
        elif event == "characteristic_value":
            handle, data = payload
            self._update_characteristic_value(handle, data)
        elif event == "descriptor_value":
            handle, data = payload
            self._update_descriptor_value(handle, data)
        elif event == "notify_state":
            handle, enabled = payload
            self._set_notify_state(handle, enabled)
        elif event == "toast":
            self._set_status(str(payload))
        elif event == "disconnected":
            self.connected = False
            self.connected_address = None
            self.connecting_address = None
            self.disconnect_button.configure(state="disabled")
            self.connect_button.configure(state="normal" if self.selected_address else "disabled")
            refresh_device_card_states(self)
            self._set_status("Disconnected")
        elif event == "error":
            self._set_status(f"Error: {payload}")
            messagebox.showerror("BLE error", str(payload), parent=self)

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _create_device_card(self, address: str) -> dict[str, Any]:
        from ui.panels.devices.device_card import create_device_card

        return create_device_card(self, address)

    def _upsert_device(self, record: DiscoveredDevice) -> None:
        upsert_device(self, record)

    def _tick_elapsed(self) -> None:
        tick_elapsed(self)

    def _clear_gatt(self) -> None:
        clear_gatt(self)

    def _render_services(self, services: list[ServiceModel]) -> None:
        render_services(self, services)

    def _render_service(self, service: ServiceModel) -> None:
        render_service(self, service)

    def _show_format_menu(self, event: tk.Event, handle: int) -> None:
        menu = tk.Menu(self, tearoff=False, bg=COLORS["panel_2"], fg=COLORS["text"], activebackground=COLORS["accent"], activeforeground="#061018")
        for fmt in ValueFormat:
            menu.add_command(label=fmt.value, command=lambda chosen=fmt: self._set_characteristic_format(handle, chosen))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_descriptor_format_menu(self, event: tk.Event, handle: int) -> None:
        menu = tk.Menu(self, tearoff=False, bg=COLORS["panel_2"], fg=COLORS["text"], activebackground=COLORS["accent"], activeforeground="#061018")
        for fmt in ValueFormat:
            menu.add_command(label=fmt.value, command=lambda chosen=fmt: self._set_descriptor_format(handle, chosen))
        menu.tk_popup(event.x_root, event.y_root)

    def _set_characteristic_format(self, handle: int, fmt: ValueFormat) -> None:
        characteristic = self.characteristics_by_handle[handle]
        characteristic.display_format = fmt
        self._refresh_characteristic_label(handle)

    def _set_descriptor_format(self, handle: int, fmt: ValueFormat) -> None:
        descriptor = self.descriptors_by_handle[handle]
        descriptor.display_format = fmt
        self._refresh_descriptor_label(handle)

    def _refresh_characteristic_label(self, handle: int) -> None:
        characteristic = self.characteristics_by_handle[handle]
        widgets = self.char_widgets.get(handle)
        if widgets:
            widgets["value"].configure(text=bytes_to_text(characteristic.value, characteristic.display_format) or "unread")

    def _refresh_descriptor_label(self, handle: int) -> None:
        descriptor = self.descriptors_by_handle[handle]
        widgets = self.descriptor_widgets.get(handle)
        if widgets:
            widgets["value"].configure(text=bytes_to_text(descriptor.value, descriptor.display_format) or "unread")

    def _update_characteristic_value(self, handle: int, data: bytes) -> None:
        characteristic = self.characteristics_by_handle.get(handle)
        if not characteristic:
            return
        characteristic.value = data
        self._refresh_characteristic_label(handle)

    def _update_descriptor_value(self, handle: int, data: bytes) -> None:
        descriptor = self.descriptors_by_handle.get(handle)
        if not descriptor:
            return
        descriptor.value = data
        self._refresh_descriptor_label(handle)

    def _set_notify_state(self, handle: int, enabled: bool) -> None:
        characteristic = self.characteristics_by_handle.get(handle)
        if not characteristic:
            return
        characteristic.notifying = enabled
        widgets = self.char_widgets.get(handle)
        if widgets and widgets["notify"]:
            widgets["notify"].configure(text="Stop" if enabled else "Notify")

    def _toggle_notify(self, characteristic: CharacteristicModel) -> None:
        self.bridge.toggle_notify(characteristic.characteristic, not characteristic.notifying)

    def _open_write_dialog(self, characteristic: CharacteristicModel) -> None:
        WriteDialog(self, characteristic, lambda data: self.bridge.write_characteristic(characteristic.characteristic, data))

    def _open_descriptor_write_dialog(self, descriptor: DescriptorModel) -> None:
        WriteDialog(self, descriptor, lambda data: self.bridge.write_descriptor(descriptor.descriptor, data))


def main() -> None:
    app = BleDebuggerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
