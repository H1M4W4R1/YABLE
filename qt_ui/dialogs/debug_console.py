from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from config import COLORS
from qt_ui.debug_log import DEFAULT_VISIBLE_LEVELS, LEVEL_ORDER, DebugLevel, DebugLog, DebugMessage


class DebugConsole(QDialog):
    def __init__(self, parent: QWidget, log: DebugLog) -> None:
        super().__init__(parent)
        self.log = log
        self.visible_levels = DEFAULT_VISIBLE_LEVELS
        self.level_checks: dict[DebugLevel, QCheckBox] = {}
        self.setWindowTitle("Debug console")
        self.resize(900, 460)
        self.build_ui()
        self.apply_styles()
        self.rebuild()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Debug console")
        title.setObjectName("DialogTitle")
        header.addWidget(title)
        header.addStretch(1)
        for level in LEVEL_ORDER:
            checkbox = QCheckBox(level.name)
            checkbox.setChecked(bool(self.visible_levels & level))
            checkbox.stateChanged.connect(lambda _state, selected=level: self.toggle_level(selected))
            self.level_checks[level] = checkbox
            header.addWidget(checkbox)
        clear_button = QPushButton("Clear")
        clear_button.setObjectName("GhostButton")
        clear_button.clicked.connect(self.clear_visible)
        header.addWidget(clear_button)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(self.log.max_entries)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.output.setObjectName("DebugOutput")

        layout.addLayout(header)
        layout.addWidget(self.output, 1)

    def apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {COLORS["bg"]};
                color: {COLORS["text"]};
                font-family: "Segoe UI";
                font-size: 10pt;
            }}
            QLabel#DialogTitle {{
                font-size: 13pt;
                font-weight: 700;
            }}
            QCheckBox {{
                color: {COLORS["text"]};
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
            }}
            QPushButton#GhostButton {{
                background: {COLORS["panel_3"]};
                color: {COLORS["text"]};
                border: 0;
                border-radius: 6px;
                padding: 7px 12px;
            }}
            QPushButton#GhostButton:hover {{
                background: #263244;
            }}
            QPlainTextEdit#DebugOutput {{
                background: {COLORS["panel_2"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["line"]};
                border-radius: 6px;
                padding: 8px;
                font-family: "Cascadia Mono", Consolas, monospace;
                selection-background-color: {COLORS["accent"]};
                selection-color: #061018;
            }}
            """
        )

    def toggle_level(self, level: DebugLevel) -> None:
        if self.level_checks[level].isChecked():
            self.visible_levels |= level
        else:
            self.visible_levels &= ~level
        self.rebuild()

    def accepts(self, entry: DebugMessage) -> bool:
        return bool(self.visible_levels & entry.level)

    def append(self, entry: DebugMessage) -> None:
        if not self.accepts(entry):
            return
        scrollbar = self.output.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        self.output.appendPlainText(entry.text())
        if at_bottom:
            self.output.moveCursor(QTextCursor.MoveOperation.End)

    def rebuild(self) -> None:
        lines = [entry.text() for entry in self.log.entries if self.accepts(entry)]
        self.output.setPlainText("\n".join(lines))
        self.output.moveCursor(QTextCursor.MoveOperation.End)

    def clear_visible(self) -> None:
        self.log.entries.clear()
        self.output.clear()
