from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from config import COLORS
from helpers.formatting import FORMAT_LABELS, ValueFormat, bytes_to_text, text_to_bytes
from models import CharacteristicModel, DescriptorModel
from qt_ui.icons import set_button_icon


class WriteDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        target: CharacteristicModel | DescriptorModel,
        on_write: Callable[[bytes], None],
    ) -> None:
        super().__init__(parent)
        self.target = target
        self.on_write = on_write
        self.setWindowTitle(f"Write {target.name}")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel(target.name)
        title.setObjectName("DialogTitle")
        uuid = QLabel(target.uuid)
        uuid.setObjectName("Muted")

        self.format_box = QComboBox()
        self.format_box.addItems(FORMAT_LABELS)
        self.format_box.setCurrentText(target.display_format.value)

        self.editor = QTextEdit()
        self.editor.setObjectName("ValueEditor")
        self.editor.setMinimumHeight(120)
        self.editor.setPlainText(bytes_to_text(target.value, target.display_format, target.display_endian))

        row = QHBoxLayout()
        row.addWidget(QLabel("Format"))
        row.addWidget(self.format_box, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("GhostButton")
        set_button_icon(cancel_button, "fa5s.times", COLORS["text"])
        cancel_button.clicked.connect(self.reject)
        write_button = QPushButton("Write")
        write_button.setObjectName("AccentButton")
        set_button_icon(write_button, "fa5s.pen", "#061018")
        write_button.clicked.connect(self._write)
        buttons.addWidget(cancel_button)
        buttons.addWidget(write_button)

        layout.addWidget(title)
        layout.addWidget(uuid)
        layout.addLayout(row)
        layout.addWidget(QLabel("Value"))
        layout.addWidget(self.editor)
        layout.addLayout(buttons)

    def _write(self) -> None:
        try:
            byte_length = len(self.target.value) if self.target.value else None
            data = text_to_bytes(
                self.editor.toPlainText().strip(),
                ValueFormat(self.format_box.currentText()),
                self.target.display_endian,
                byte_length,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Invalid value", str(exc))
            return
        self.on_write(data)
        self.accept()
