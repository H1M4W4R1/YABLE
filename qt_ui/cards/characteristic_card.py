from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from config import COLORS
from helpers.formatting import bytes_to_text
from models import CharacteristicModel
from qt_ui.cards.descriptor_card import DescriptorCard
from qt_ui.icons import set_button_icon, set_disclosure_icon, set_icon_button_text
from qt_ui.widgets.value_label import ValueLabel

if TYPE_CHECKING:
    from qt_ui.window import BleDebuggerWindow


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
        self.value_label.endian_requested.connect(lambda endian: self.app.set_characteristic_endian(characteristic.handle, endian))

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
        self.value_label.setText(bytes_to_text(self.characteristic.value, self.characteristic.display_format, self.characteristic.display_endian) or "unread")

    def refresh_notify(self) -> None:
        if self.notify_button is not None:
            set_icon_button_text(self.notify_button, "Stop" if self.characteristic.notifying else "Notify")
