from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QSizeGrip


class VisibleSizeGrip(QSizeGrip):
    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.lightGray, 1))
        width = self.width()
        height = self.height()
        for offset in (5, 10, 15):
            painter.drawLine(width - offset, height - 2, width - 2, height - offset)
