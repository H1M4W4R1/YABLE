from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel


class StatusLabel(QLabel):
    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)
