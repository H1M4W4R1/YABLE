from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from config import APP_TITLE
from qt_ui.window import BleDebuggerWindow




def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = BleDebuggerWindow()
    window.show()
    return app.exec()
