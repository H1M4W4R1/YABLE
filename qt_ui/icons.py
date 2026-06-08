from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QPushButton

from config import COLORS

APP_ICON_PATH = Path(__file__).resolve().parents[1] / "assets" / "icons" / "app.svg"

try:
    import qtawesome as qta

    from qtawesome.iconic_font import IconicFont
except ImportError:  # pragma: no cover - handled by requirements install
    qta = None
else:
    def _use_bundled_fonts(self: IconicFont, fonts_directory: str, system_wide: bool = False) -> str:
        return fonts_directory

    IconicFont._install_fonts = _use_bundled_fonts




def fa_icon(name: str, color: str | None = None) -> QIcon:
    if qta is None:
        return QIcon()
    return qta.icon(name, color=color or COLORS["text"])


def app_icon() -> QIcon:
    return QIcon(str(APP_ICON_PATH))




def set_button_icon(button: QPushButton, icon_name: str, color: str | None = None) -> None:
    button.setIcon(fa_icon(icon_name, color))
    button.setIconSize(QSize(14, 14))
    if button.text():
        set_icon_button_text(button, button.text())




def set_icon_button_text(button: QPushButton, text: str) -> None:
    button.setText(f" {text.strip()}")




def set_disclosure_icon(button: QPushButton, expanded: bool) -> None:
    button.setText("" if qta is not None else ("v" if expanded else ">"))
    set_button_icon(button, "fa5s.chevron-down" if expanded else "fa5s.chevron-right", COLORS["accent"])
