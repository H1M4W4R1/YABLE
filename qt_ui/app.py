from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QPoint, QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent, QIcon, QMouseEvent, QPainter, QPen, QResizeEvent
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ble.bridge import AsyncBleBridge
from config import APP_TITLE, COLORS
from helpers.advertising import extract_gap_appearance, manufacturer_names
from helpers.data.uuids import BLUETOOTH_NUMBERS
from helpers.formatting import FORMAT_LABELS, ValueFormat, bytes_to_text, format_elapsed, signal_icon, text_to_bytes
from models import CharacteristicModel, DescriptorModel, DiscoveredDevice, ServiceModel

try:
    import qtawesome as qta

    from qtawesome.iconic_font import IconicFont
except ImportError:  # pragma: no cover - handled by requirements install
    qta = None
else:
    def _use_bundled_fonts(self: IconicFont, fonts_directory: str, system_wide: bool = False) -> str:
        return fonts_directory

    IconicFont._install_fonts = _use_bundled_fonts


def fa_icon(name: str, color: str | None = None) -> QIcon:
    if qta is None:
        return QIcon()
    return qta.icon(name, color=color or COLORS["text"])


def set_button_icon(button: QPushButton, icon_name: str, color: str | None = None) -> None:
    button.setIcon(fa_icon(icon_name, color))
    button.setIconSize(QSize(14, 14))
    if button.text():
        set_icon_button_text(button, button.text())


def set_icon_button_text(button: QPushButton, text: str) -> None:
    button.setText(f" {text.strip()}")


def set_disclosure_icon(button: QPushButton, expanded: bool) -> None:
    button.setText("" if qta is not None else ("v" if expanded else ">"))
    set_button_icon(button, "fa5s.chevron-down" if expanded else "fa5s.chevron-right", COLORS["accent"])


class BleEventBus(QObject):
    event = pyqtSignal(str, object)

    def __init__(self) -> None:
        super().__init__()
        self.active = True

    def emit_event(self, name: str, payload: Any) -> None:
        if not self.active:
            return
        try:
            self.event.emit(name, payload)
        except RuntimeError:
            pass


class ClickableFrame(QFrame):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class ValueLabel(QLabel):
    format_requested = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ValueLabel")
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setMinimumWidth(210)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def contextMenuEvent(self, event: Any) -> None:
        menu = QMenu(self)
        for fmt in ValueFormat:
            action = QAction(fmt.value, self)
            action.triggered.connect(lambda _checked=False, chosen=fmt: self.format_requested.emit(chosen))
            menu.addAction(action)
        menu.exec(event.globalPos())


class VisibleSizeGrip(QSizeGrip):
    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.lightGray, 1))
        width = self.width()
        height = self.height()
        for offset in (5, 10, 15):
            painter.drawLine(width - offset, height - 2, width - 2, height - offset)


class TitleBar(QFrame):
    def __init__(self, window: "BleDebuggerWindow") -> None:
        super().__init__()
        self.window = window
        self.drag_origin: QPoint | None = None
        self.setObjectName("TitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 8)
        layout.setSpacing(8)

        title = QLabel(APP_TITLE)
        title.setObjectName("AppTitle")
        subtitle = QLabel("Bluetooth Low Energy debugger")
        subtitle.setObjectName("Muted")
        title_stack = QVBoxLayout()
        title_stack.setSpacing(1)
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)

        minimize_button = QPushButton("")
        minimize_button.setObjectName("WindowButton")
        minimize_button.setToolTip("Minimize")
        set_button_icon(minimize_button, "fa5s.window-minimize", COLORS["muted"])
        minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button = QPushButton("")
        self.maximize_button.setObjectName("WindowButton")
        self.maximize_button.setToolTip("Maximize")
        set_button_icon(self.maximize_button, "fa5s.window-maximize", COLORS["muted"])
        self.maximize_button.clicked.connect(self.toggle_maximize)
        close_button = QPushButton("")
        close_button.setObjectName("CloseButton")
        close_button.setToolTip("Close")
        set_button_icon(close_button, "fa5s.times", COLORS["muted"])
        close_button.clicked.connect(window.close)

        layout.addLayout(title_stack, 1)
        layout.addWidget(minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(close_button)

    def toggle_maximize(self) -> None:
        if self.window.isMaximized():
            self.window.showNormal()
            set_button_icon(self.maximize_button, "fa5s.window-maximize", COLORS["muted"])
        else:
            self.window.showMaximized()
            set_button_icon(self.maximize_button, "fa5s.window-restore", COLORS["muted"])

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_origin = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drag_origin is None or self.window.isMaximized():
            super().mouseMoveEvent(event)
            return
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self.drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.drag_origin = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()
        super().mouseDoubleClickEvent(event)


class WriteDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        target: CharacteristicModel | DescriptorModel,
        on_write: Callable[[bytes], None],
    ) -> None:
        super().__init__(parent)
        self.target = target
        self.on_write = on_write
        self.setWindowTitle(f"Write {target.name}")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel(target.name)
        title.setObjectName("DialogTitle")
        uuid = QLabel(target.uuid)
        uuid.setObjectName("Muted")

        self.format_box = QComboBox()
        self.format_box.addItems(FORMAT_LABELS)
        self.format_box.setCurrentText(target.display_format.value)

        self.editor = QTextEdit()
        self.editor.setObjectName("ValueEditor")
        self.editor.setMinimumHeight(120)
        self.editor.setPlainText(bytes_to_text(target.value, target.display_format))

        row = QHBoxLayout()
        row.addWidget(QLabel("Format"))
        row.addWidget(self.format_box, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("GhostButton")
        set_button_icon(cancel_button, "fa5s.times", COLORS["text"])
        cancel_button.clicked.connect(self.reject)
        write_button = QPushButton("Write")
        write_button.setObjectName("AccentButton")
        set_button_icon(write_button, "fa5s.pen", "#061018")
        write_button.clicked.connect(self._write)
        buttons.addWidget(cancel_button)
        buttons.addWidget(write_button)

        layout.addWidget(title)
        layout.addWidget(uuid)
        layout.addLayout(row)
        layout.addWidget(QLabel("Value"))
        layout.addWidget(self.editor)
        layout.addLayout(buttons)

    def _write(self) -> None:
        try:
            data = text_to_bytes(self.editor.toPlainText().strip(), ValueFormat(self.format_box.currentText()))
        except Exception as exc:
            QMessageBox.critical(self, "Invalid value", str(exc))
            return
        self.on_write(data)
        self.accept()


class DeviceCard(ClickableFrame):
    def __init__(self, address: str) -> None:
        super().__init__()
        self.address = address
        self.setObjectName("DeviceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        top = QHBoxLayout()
        self.name_label = QLabel("")
        self.name_label.setObjectName("DeviceName")
        self.connected_label = QLabel("Connected")
        self.connected_label.setObjectName("Connected")
        self.rssi_label = QLabel("")
        self.rssi_label.setObjectName("Rssi")
        top.addWidget(self.name_label, 1)
        top.addWidget(self.connected_label)
        top.addWidget(self.rssi_label)

        self.address_label = QLabel(address)
        self.address_label.setObjectName("MonoMuted")
        self.company_label = QLabel("")
        self.company_label.setObjectName("Muted")
        self.company_label.setWordWrap(True)
        self.appearance_label = QLabel("")
        self.appearance_label.setObjectName("Muted")
        self.appearance_label.setWordWrap(True)
        self.last_label = QLabel("")
        self.last_label.setObjectName("Muted")
        self.last_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        meta = QHBoxLayout()
        meta_text = QVBoxLayout()
        meta_text.addWidget(self.company_label)
        meta_text.addWidget(self.appearance_label)
        meta.addLayout(meta_text, 1)
        meta.addWidget(self.last_label)

        layout.addLayout(top)
        layout.addWidget(self.address_label)
        layout.addLayout(meta)
        self.set_selected(False, False)

    def update_record(self, record: DiscoveredDevice, last_text: str) -> None:
        company_text = ", ".join(manufacturer_names(record.advertisement)) or "Company unknown"
        appearance = BLUETOOTH_NUMBERS.appearance_name(extract_gap_appearance(record.advertisement)) or "Appearance unknown"
        rssi = record.rssi if record.rssi is not None else "--"
        self.name_label.setText(record.name)
        self.address_label.setText(record.address)
        self.company_label.setText(company_text)
        self.appearance_label.setText(appearance)
        self.last_label.setText(last_text)
        self.rssi_label.setText(f"{signal_icon(record.rssi)}  {rssi} dBm")

    def set_selected(self, selected: bool, connected: bool) -> None:
        self.connected_label.setVisible(connected)
        if connected:
            state = "connected"
        elif selected:
            state = "selected"
        else:
            state = "idle"
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class DescriptorCard(QFrame):
    def __init__(self, app: "BleDebuggerWindow", descriptor: DescriptorModel) -> None:
        super().__init__()
        self.app = app
        self.descriptor = descriptor
        self.setObjectName("DescriptorCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.app.descriptors_by_handle[descriptor.handle] = descriptor

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        text = QVBoxLayout()
        name = QLabel(descriptor.name)
        name.setObjectName("SmallTitle")
        uuid = QLabel(descriptor.uuid)
        uuid.setObjectName("Muted")
        uuid.setWordWrap(True)
        text.addWidget(name)
        text.addWidget(uuid)

        self.value_label = ValueLabel()
        self.value_label.format_requested.connect(lambda fmt: self.app.set_descriptor_format(descriptor.handle, fmt))
        read_button = QPushButton("Read")
        read_button.setObjectName("GhostButton")
        set_button_icon(read_button, "fa5s.sync-alt", COLORS["text"])
        read_button.clicked.connect(lambda: self.app.bridge.read_descriptor(descriptor.descriptor))
        write_button = QPushButton("Write")
        write_button.setObjectName("AccentButton")
        set_button_icon(write_button, "fa5s.pen", "#061018")
        write_button.clicked.connect(lambda: self.app.open_descriptor_write_dialog(descriptor))

        actions = QHBoxLayout()
        actions.addWidget(self.value_label)
        actions.addWidget(read_button)
        actions.addWidget(write_button)

        layout.addLayout(text, 1)
        layout.addLayout(actions)
        self.app.descriptor_widgets[descriptor.handle] = self
        self.refresh_value()

    def refresh_value(self) -> None:
        self.value_label.setText(bytes_to_text(self.descriptor.value, self.descriptor.display_format) or "unread")


class CharacteristicCard(QFrame):
    def __init__(self, app: "BleDebuggerWindow", characteristic: CharacteristicModel) -> None:
        super().__init__()
        self.app = app
        self.characteristic = characteristic
        self.descriptor_container: QWidget | None = None
        self.setObjectName("CharacteristicCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.app.characteristics_by_handle[characteristic.handle] = characteristic

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row_widget = QWidget()
        row_widget.setObjectName("CardBody")
        row_widget.setLayout(row)
        text = QVBoxLayout()
        name_row = QHBoxLayout()
        self.toggle_button: QPushButton | None = None
        if characteristic.descriptors:
            self.toggle_button = QPushButton("")
            self.toggle_button.setObjectName("DisclosureButton")
            set_disclosure_icon(self.toggle_button, False)
            self.toggle_button.clicked.connect(self.toggle_descriptors)
            name_row.addWidget(self.toggle_button)
        name = QLabel(characteristic.name)
        name.setObjectName("CardTitle")
        name_row.addWidget(name, 1)
        properties = "  ".join(sorted(characteristic.properties)) or "no properties"
        meta = QLabel(f"{characteristic.uuid}  -  {properties}")
        meta.setObjectName("Muted")
        meta.setWordWrap(True)
        text.addLayout(name_row)
        text.addWidget(meta)

        self.value_label = ValueLabel()
        self.value_label.format_requested.connect(lambda fmt: self.app.set_characteristic_format(characteristic.handle, fmt))

        actions = QHBoxLayout()
        actions.addWidget(self.value_label)
        if "read" in characteristic.properties:
            read_button = QPushButton("Read")
            read_button.setObjectName("GhostButton")
            set_button_icon(read_button, "fa5s.sync-alt", COLORS["text"])
            read_button.clicked.connect(lambda: self.app.bridge.read_characteristic(characteristic.characteristic))
            actions.addWidget(read_button)
        if "write" in characteristic.properties or "write-without-response" in characteristic.properties:
            write_button = QPushButton("Write")
            write_button.setObjectName("AccentButton")
            set_button_icon(write_button, "fa5s.pen", "#061018")
            write_button.clicked.connect(lambda: self.app.open_write_dialog(characteristic))
            actions.addWidget(write_button)
        self.notify_button: QPushButton | None = None
        if "notify" in characteristic.properties or "indicate" in characteristic.properties:
            self.notify_button = QPushButton("Notify")
            self.notify_button.setObjectName("GhostButton")
            set_button_icon(self.notify_button, "fa5s.bell", COLORS["text"])
            self.notify_button.clicked.connect(lambda: self.app.toggle_notify(characteristic))
            actions.addWidget(self.notify_button)

        row.addLayout(text, 1)
        row.addLayout(actions)
        layout.addWidget(row_widget)

        if characteristic.descriptors:
            self.descriptor_container = QWidget()
            self.descriptor_container.setObjectName("DescriptorContainer")
            descriptor_layout = QVBoxLayout(self.descriptor_container)
            descriptor_layout.setContentsMargins(28, 0, 0, 0)
            descriptor_layout.setSpacing(4)
            for descriptor in characteristic.descriptors:
                descriptor_layout.addWidget(DescriptorCard(app, descriptor))
            self.descriptor_container.hide()
            layout.addWidget(self.descriptor_container)

        self.app.char_widgets[characteristic.handle] = self
        self.refresh_value()
        self.refresh_notify()

    def toggle_descriptors(self) -> None:
        if self.descriptor_container is None or self.toggle_button is None:
            return
        visible = not self.descriptor_container.isVisible()
        self.descriptor_container.setVisible(visible)
        set_disclosure_icon(self.toggle_button, visible)

    def refresh_value(self) -> None:
        self.value_label.setText(bytes_to_text(self.characteristic.value, self.characteristic.display_format) or "unread")

    def refresh_notify(self) -> None:
        if self.notify_button is not None:
            set_icon_button_text(self.notify_button, "Stop" if self.characteristic.notifying else "Notify")


class ServiceSection(QFrame):
    def __init__(self, app: "BleDebuggerWindow", service: ServiceModel) -> None:
        super().__init__()
        self.setObjectName("ServiceSection")
        self.content = QWidget()
        self.content.setObjectName("ServiceContent")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("ServiceHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 12, 8)
        self.toggle_button = QPushButton("")
        self.toggle_button.setObjectName("DisclosureButton")
        set_disclosure_icon(self.toggle_button, True)
        title = QLabel(service.name)
        title.setObjectName("ServiceTitle")
        uuid = QLabel(service.uuid)
        uuid.setObjectName("Muted")
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(title, 1)
        header_layout.addWidget(uuid)

        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 6, 0, 0)
        content_layout.setSpacing(6)
        for characteristic in service.characteristics:
            content_layout.addWidget(CharacteristicCard(app, characteristic))
        for descriptor in service.descriptors:
            content_layout.addWidget(DescriptorCard(app, descriptor))

        self.toggle_button.clicked.connect(self.toggle)
        layout.addWidget(header)
        layout.addWidget(self.content)

    def toggle(self) -> None:
        visible = not self.content.isVisible()
        self.content.setVisible(visible)
        set_disclosure_icon(self.toggle_button, visible)


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
                background: {COLORS["panel_2"]};
                border: 1px solid {COLORS["line"]};
                border-radius: 8px;
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

    def set_descriptor_format(self, handle: int, fmt: ValueFormat) -> None:
        descriptor = self.descriptors_by_handle[handle]
        descriptor.display_format = fmt
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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = BleDebuggerWindow()
    window.show()
    return app.exec()
