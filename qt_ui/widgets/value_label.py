from __future__ import annotations

from typing import Any

from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QMenu, QSizePolicy

from helpers.formatting import ValueEndian, ValueFormat


class ValueLabel(QLabel):
    format_requested = pyqtSignal(object)
    endian_requested = pyqtSignal(object)

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
        menu.addSeparator()
        for endian in ValueEndian:
            action = QAction(f"Endian: {endian.value}", self)
            action.triggered.connect(lambda _checked=False, chosen=endian: self.endian_requested.emit(chosen))
            menu.addAction(action)
        menu.exec(event.globalPos())
