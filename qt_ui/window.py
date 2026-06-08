from __future__ import annotations

import time
from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QResizeEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget

from ble.bridge import AsyncBleBridge
from config import APP_TITLE, COLORS
from helpers.formatting import ValueEndian, ValueFormat, format_elapsed
from models import CharacteristicModel, DescriptorModel, DiscoveredDevice, ServiceModel
from qt_ui.cards.characteristic_card import CharacteristicCard
from qt_ui.cards.descriptor_card import DescriptorCard
from qt_ui.cards.device_card import DeviceCard
from qt_ui.cards.service_section import ServiceSection
from qt_ui.dialogs.write_dialog import WriteDialog
from qt_ui.event_bus import BleEventBus
from qt_ui.icons import set_button_icon, set_icon_button_text
from qt_ui.widgets.title_bar import TitleBar
from qt_ui.widgets.visible_size_grip import VisibleSizeGrip


class BleDebuggerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowTitle(APP_TITLE)
        self.resize(1220, 760)
        self.setMinimumSize(980, 620)

        self.events = BleEventBus()
        self.events.event.connect(self.handle_event)
        self.bridge = AsyncBleBridge(self.events.emit_event)
        self.devices: dict[str, DiscoveredDevice] = {}
        self.device_cards: dict[str, DeviceCard] = {}
        self.services: list[ServiceModel] = []
        self.characteristics_by_handle: dict[int, CharacteristicModel] = {}
        self.descriptors_by_handle: dict[int, DescriptorModel] = {}
        self.char_widgets: dict[int, CharacteristicCard] = {}
        self.descriptor_widgets: dict[int, DescriptorCard] = {}
        self.scan_running = False
        self.connected = False
        self.selected_address: str | None = None
        self.connecting_address: str | None = None
        self.connected_address: str | None = None

        self.build_ui()
        self.apply_styles()

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self.tick_elapsed)
        self.elapsed_timer.start(1000)

    def build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(12)
        self.setCentralWidget(root)

        self.title_bar = TitleBar(self)

        content = QWidget()
        content.setObjectName("Content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 0, 14, 14)
        content_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("Status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.scan_button = QPushButton("Start scan")
        self.scan_button.setObjectName("AccentButton")
        set_button_icon(self.scan_button, "fa5s.play", "#061018")
        self.scan_button.clicked.connect(self.toggle_scan)
        self.connect_button = QPushButton("Connect + GATT")
        self.connect_button.setObjectName("GhostButton")
        set_button_icon(self.connect_button, "fa5s.plug", COLORS["text"])
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self.connect_selected)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("GhostButton")
        set_button_icon(self.disconnect_button, "fa5s.unlink", COLORS["text"])
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.clicked.connect(self.disconnect)

        header.addWidget(self.status_label, 1)
        header.addWidget(self.scan_button)
        header.addWidget(self.connect_button)
        header.addWidget(self.disconnect_button)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("MainSplitter")
        splitter.setHandleWidth(12)
        splitter.addWidget(self.build_devices_panel())
        splitter.addWidget(self.build_gatt_panel())
        splitter.setSizes([430, 760])

        content_layout.addLayout(header)
        content_layout.addWidget(splitter, 1)
        root_layout.addWidget(self.title_bar)
        root_layout.addWidget(content, 1)
        self.resize_grip = VisibleSizeGrip(self)
        self.resize_grip.setObjectName("ResizeGrip")
        self.resize_grip.setFixedSize(18, 18)
        self.position_resize_grip()

    def build_devices_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        row = QHBoxLayout()
        title = QLabel("Devices")
        title.setObjectName("PanelTitle")
        self.device_hint = QLabel("No advertisements")
        self.device_hint.setObjectName("Muted")
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(self.device_hint)

        self.device_list = QVBoxLayout()
        self.device_list.setSpacing(8)
        self.device_list.addStretch(1)
        scroll_body = QWidget()
        scroll_body.setObjectName("PanelBody")
        scroll_body.setLayout(self.device_list)
        scroll = QScrollArea()
        scroll.setObjectName("PanelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(scroll_body)

        layout.addLayout(row)
        layout.addWidget(scroll, 1)
        return panel

    def build_gatt_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        row = QHBoxLayout()
        title = QLabel("GATT")
        title.setObjectName("PanelTitle")
        self.gatt_hint = QLabel("Connect to a device")
        self.gatt_hint.setObjectName("Muted")
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(self.gatt_hint)

        self.gatt_list = QVBoxLayout()
        self.gatt_list.setSpacing(10)
        self.gatt_list.addStretch(1)
        scroll_body = QWidget()
        scroll_body.setObjectName("PanelBody")
        scroll_body.setLayout(self.gatt_list)
        scroll = QScrollArea()
        scroll.setObjectName("PanelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(scroll_body)

        layout.addLayout(row)
        layout.addWidget(scroll, 1)
        return panel

    def apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget#Root, QWidget#Content {{
                background: {COLORS["bg"]};
                color: {COLORS["text"]};
                font-family: "Segoe UI";
                font-size: 10pt;
            }}
            QFrame#TitleBar {{
                background: {COLORS["bg"]};
                border-bottom: 1px solid {COLORS["line"]};
            }}
            QWidget, QFrame {{
                color: {COLORS["text"]};
                font-family: "Segoe UI";
                font-size: 10pt;
            }}
            QFrame#Panel {{
                background: {COLORS["panel"]};
                border: 1px solid {COLORS["line"]};
                border-radius: 8px;
            }}
            QWidget#PanelBody, QWidget#ServiceContent, QWidget#DescriptorContainer, QWidget#CardBody {{
                background: transparent;
            }}
            QLabel#AppTitle {{
                font-size: 18pt;
                font-weight: 700;
            }}
            QLabel#PanelTitle {{
                font-size: 12pt;
                font-weight: 700;
            }}
            QLabel#DialogTitle, QLabel#CardTitle, QLabel#DeviceName, QLabel#ServiceTitle {{
                font-weight: 700;
                color: {COLORS["text"]};
            }}
            QLabel#SmallTitle {{
                font-weight: 700;
            }}
            QLabel#Muted, QLabel#MonoMuted {{
                color: {COLORS["muted"]};
                font-size: 9pt;
            }}
            QLabel#MonoMuted, QLabel#ValueLabel {{
                font-family: "Cascadia Mono", Consolas, monospace;
            }}
            QLabel#Status {{
                color: {COLORS["muted"]};
                padding: 0;
            }}
            QLabel#Rssi, QLabel#ValueLabel {{
                color: {COLORS["accent_2"]};
            }}
            QLabel#Connected {{
                color: {COLORS["success"]};
                font-size: 8pt;
                font-weight: 700;
            }}
            QLabel#ValueLabel {{
                background: {COLORS["panel_2"]};
                border-radius: 6px;
                padding: 7px 10px;
            }}
            QFrame#DeviceCard, QFrame#CharacteristicCard, QFrame#DescriptorCard {{
                background: {COLORS["panel_2"]};
                border: 1px solid {COLORS["line"]};
                border-radius: 8px;
            }}
            QFrame#ServiceSection {{
                background: transparent;
                border: 0;
            }}
            QFrame#DeviceCard[state="selected"] {{
                background: {COLORS["panel_3"]};
                border-color: {COLORS["accent"]};
            }}
            QFrame#DeviceCard[state="connected"] {{
                background: {COLORS["panel_3"]};
                border-color: {COLORS["success"]};
            }}
            QFrame#ServiceHeader {{
                background: transparent;
                border: 0;
                border-radius: 0;
            }}
            QPushButton {{
                border: 0;
                border-radius: 6px;
                padding: 7px 12px;
                min-height: 18px;
                text-align: left;
            }}
            QPushButton#AccentButton {{
                background: {COLORS["accent"]};
                color: #061018;
                font-weight: 700;
            }}
            QPushButton#AccentButton:hover {{
                background: {COLORS["accent_2"]};
            }}
            QPushButton#GhostButton {{
                background: {COLORS["panel_3"]};
                color: {COLORS["text"]};
            }}
            QPushButton#GhostButton:hover {{
                background: #263244;
            }}
            QPushButton#DisclosureButton {{
                background: transparent;
                color: {COLORS["accent"]};
                padding: 0;
                min-width: 22px;
                max-width: 22px;
                font-weight: 700;
            }}
            QPushButton:disabled {{
                background: {COLORS["panel_2"]};
                color: {COLORS["muted"]};
            }}
            QPushButton#WindowButton, QPushButton#CloseButton {{
                background: transparent;
                color: {COLORS["muted"]};
                border-radius: 4px;
                min-width: 34px;
                max-width: 34px;
                min-height: 28px;
                max-height: 28px;
                padding: 0;
                font-size: 12pt;
                text-align: center;
            }}
            QPushButton#WindowButton:hover {{
                background: {COLORS["panel_3"]};
                color: {COLORS["text"]};
            }}
            QPushButton#CloseButton:hover {{
                background: {COLORS["danger"]};
                color: #061018;
            }}
            QScrollArea, QScrollArea#PanelScroll, QScrollArea#PanelScroll > QWidget, QScrollArea#PanelScroll > QWidget > QWidget {{
                background: transparent;
                border: 0;
            }}
            QSplitter#MainSplitter {{
                background: {COLORS["bg"]};
            }}
            QSplitter#MainSplitter::handle {{
                background: {COLORS["bg"]};
                border: 0;
            }}
            QSplitter#MainSplitter::handle:hover {{
                background: {COLORS["line"]};
            }}
            QSizeGrip#ResizeGrip {{
                width: 18px;
                height: 18px;
                background: {COLORS["panel_3"]};
                border-left: 1px solid {COLORS["line"]};
                border-top: 1px solid {COLORS["line"]};
                border-bottom-right-radius: 6px;
            }}
            QComboBox, QTextEdit {{
                background: {COLORS["panel_2"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["line"]};
                border-radius: 6px;
                padding: 7px;
                selection-background-color: {COLORS["accent"]};
                selection-color: #061018;
            }}
            QMenu {{
                background: {COLORS["panel_2"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["line"]};
            }}
            QMenu::item:selected {{
                background: {COLORS["accent"]};
                color: #061018;
            }}
            """
        )

    def toggle_scan(self) -> None:
        if self.scan_running:
            self.bridge.stop_scan()
        else:
            self.bridge.start_scan()
            self.set_status("Scanning for advertisements...")

    def connect_selected(self) -> None:
        if not self.selected_address:
            return
        self.connect_button.setEnabled(False)
        self.connecting_address = self.selected_address
        self.bridge.connect(self.selected_address)

    def connect_device_card(self, address: str) -> None:
        self.select_device(address)
        self.connect_selected()

    def disconnect(self) -> None:
        self.bridge.disconnect()

    def select_device(self, address: str) -> None:
        self.selected_address = address
        self.connect_button.setEnabled(True)
        self.refresh_device_card_states()

    def handle_event(self, event: str, payload: Any) -> None:
        if event == "missing_dependency":
            self.set_status("Install dependencies with: python -m pip install -r requirements.txt")
            QMessageBox.critical(self, "Missing dependency", "The bleak package is required for BLE access.\n\nRun: python -m pip install -r requirements.txt")
        elif event == "scan_state":
            self.scan_running = bool(payload)
            set_icon_button_text(self.scan_button, "Stop scan" if self.scan_running else "Start scan")
            set_button_icon(self.scan_button, "fa5s.stop" if self.scan_running else "fa5s.play", "#061018")
        elif event == "device":
            self.upsert_device(payload)
        elif event == "connection_state":
            self.set_status(str(payload))
        elif event == "services":
            self.connected = True
            self.connected_address = self.connecting_address or self.selected_address
            self.connecting_address = None
            self.disconnect_button.setEnabled(True)
            self.refresh_device_card_states()
            self.render_services(payload)
        elif event == "characteristic_value":
            handle, data = payload
            self.update_characteristic_value(handle, data)
        elif event == "descriptor_value":
            handle, data = payload
            self.update_descriptor_value(handle, data)
        elif event == "notify_state":
            handle, enabled = payload
            self.set_notify_state(handle, enabled)
        elif event == "toast":
            self.set_status(str(payload))
        elif event == "disconnected":
            self.connected = False
            self.connected_address = None
            self.connecting_address = None
            self.disconnect_button.setEnabled(False)
            self.connect_button.setEnabled(self.selected_address is not None)
            self.refresh_device_card_states()
            self.set_status("Disconnected")
        elif event == "error":
            self.set_status(f"Error: {payload}")
            QMessageBox.critical(self, "BLE error", str(payload))

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.position_resize_grip()

    def position_resize_grip(self) -> None:
        grip = getattr(self, "resize_grip", None)
        if grip is None:
            return
        grip.move(self.width() - grip.width(), self.height() - grip.height())
        grip.raise_()

    def upsert_device(self, record: DiscoveredDevice) -> None:
        self.devices[record.address] = record
        card = self.device_cards.get(record.address)
        if card is None:
            card = DeviceCard(record.address)
            card.clicked.connect(lambda address=record.address: self.select_device(address))
            card.double_clicked.connect(lambda address=record.address: self.connect_device_card(address))
            self.device_cards[record.address] = card
            self.device_list.insertWidget(max(0, self.device_list.count() - 1), card)
        card.update_record(record, format_elapsed(time.time() - record.last_seen))
        self.device_hint.setText(f"{len(self.devices)} devices")
        self.refresh_device_card_states()

    def tick_elapsed(self) -> None:
        now = time.time()
        for address, record in self.devices.items():
            card = self.device_cards.get(address)
            if card is not None:
                card.last_label.setText(format_elapsed(now - record.last_seen))

    def refresh_device_card_states(self) -> None:
        for address, card in self.device_cards.items():
            card.set_selected(address == self.selected_address, address == self.connected_address)

    def clear_gatt(self) -> None:
        while self.gatt_list.count() > 1:
            item = self.gatt_list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.characteristics_by_handle.clear()
        self.descriptors_by_handle.clear()
        self.char_widgets.clear()
        self.descriptor_widgets.clear()

    def render_services(self, services: list[ServiceModel]) -> None:
        self.services = services
        self.clear_gatt()
        self.gatt_hint.setText(f"{len(services)} services")
        for service in services:
            self.gatt_list.insertWidget(max(0, self.gatt_list.count() - 1), ServiceSection(self, service))

    def set_characteristic_format(self, handle: int, fmt: ValueFormat) -> None:
        characteristic = self.characteristics_by_handle[handle]
        characteristic.display_format = fmt
        widget = self.char_widgets.get(handle)
        if widget is not None:
            widget.refresh_value()

    def set_characteristic_endian(self, handle: int, endian: ValueEndian) -> None:
        characteristic = self.characteristics_by_handle[handle]
        characteristic.display_endian = endian
        widget = self.char_widgets.get(handle)
        if widget is not None:
            widget.refresh_value()

    def set_descriptor_format(self, handle: int, fmt: ValueFormat) -> None:
        descriptor = self.descriptors_by_handle[handle]
        descriptor.display_format = fmt
        widget = self.descriptor_widgets.get(handle)
        if widget is not None:
            widget.refresh_value()

    def set_descriptor_endian(self, handle: int, endian: ValueEndian) -> None:
        descriptor = self.descriptors_by_handle[handle]
        descriptor.display_endian = endian
        widget = self.descriptor_widgets.get(handle)
        if widget is not None:
            widget.refresh_value()

    def update_characteristic_value(self, handle: int, data: bytes) -> None:
        characteristic = self.characteristics_by_handle.get(handle)
        if characteristic is None:
            return
        characteristic.value = data
        widget = self.char_widgets.get(handle)
        if widget is not None:
            widget.refresh_value()

    def update_descriptor_value(self, handle: int, data: bytes) -> None:
        descriptor = self.descriptors_by_handle.get(handle)
        if descriptor is None:
            return
        descriptor.value = data
        widget = self.descriptor_widgets.get(handle)
        if widget is not None:
            widget.refresh_value()

    def set_notify_state(self, handle: int, enabled: bool) -> None:
        characteristic = self.characteristics_by_handle.get(handle)
        if characteristic is None:
            return
        characteristic.notifying = enabled
        widget = self.char_widgets.get(handle)
        if widget is not None:
            widget.refresh_notify()

    def toggle_notify(self, characteristic: CharacteristicModel) -> None:
        self.bridge.toggle_notify(characteristic.characteristic, not characteristic.notifying)

    def open_write_dialog(self, characteristic: CharacteristicModel) -> None:
        WriteDialog(self, characteristic, lambda data: self.bridge.write_characteristic(characteristic.characteristic, data)).exec()

    def open_descriptor_write_dialog(self, descriptor: DescriptorModel) -> None:
        WriteDialog(self, descriptor, lambda data: self.bridge.write_descriptor(descriptor.descriptor, data)).exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.events.active = False
        self.bridge.disconnect()
        self.bridge.stop_scan()
        super().closeEvent(event)
