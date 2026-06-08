from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from models import ServiceModel
from qt_ui.cards.characteristic_card import CharacteristicCard
from qt_ui.cards.descriptor_card import DescriptorCard
from qt_ui.icons import set_disclosure_icon

if TYPE_CHECKING:
    from qt_ui.window import BleDebuggerWindow


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
            if characteristic.hidden:
                continue
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
