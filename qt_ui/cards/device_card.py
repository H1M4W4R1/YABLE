from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from config import COLORS
from helpers.advertising import extract_gap_appearance, manufacturer_names
from helpers.data.uuids import BLUETOOTH_NUMBERS
from helpers.formatting import signal_icon
from models import DiscoveredDevice
from qt_ui.widgets.clickable_frame import ClickableFrame


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
        company_text = ", ".join(manufacturer_names(record.advertisement))
        appearance = BLUETOOTH_NUMBERS.appearance_name(extract_gap_appearance(record.advertisement)) or ""
        rssi = record.rssi if record.rssi is not None else "--"
        self.name_label.setText(record.name)
        self.address_label.setText(record.address)
        self.company_label.setText(company_text)
        self.company_label.setVisible(bool(company_text))
        self.appearance_label.setText(appearance)
        self.appearance_label.setVisible(bool(appearance))
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
