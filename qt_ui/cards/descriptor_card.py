from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from config import COLORS
from helpers.formatting import bytes_to_text
from models import DescriptorModel
from qt_ui.icons import set_button_icon
from qt_ui.widgets.value_label import ValueLabel

if TYPE_CHECKING:
    from qt_ui.window import BleDebuggerWindow


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
        self.value_label.endian_requested.connect(lambda endian: self.app.set_descriptor_endian(descriptor.handle, endian))
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
        self.value_label.setText(bytes_to_text(self.descriptor.value, self.descriptor.display_format, self.descriptor.display_endian) or "unread")
