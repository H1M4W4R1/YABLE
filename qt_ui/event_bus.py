from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal


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
