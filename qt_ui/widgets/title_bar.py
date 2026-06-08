from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from config import APP_TITLE, COLORS
from qt_ui.icons import app_icon, set_button_icon

if TYPE_CHECKING:
    from qt_ui.window import BleDebuggerWindow


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

        icon_label = QLabel()
        icon_label.setPixmap(app_icon().pixmap(QSize(34, 34)))
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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

        layout.addWidget(icon_label)
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
