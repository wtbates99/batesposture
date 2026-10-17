from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from .theme import score_color_hex

ICON_SIZE = 64


def create_score_icon(score: float) -> QIcon:
    """Render a compact, color-coded posture score for the system tray."""
    return _render_score_icon(round(max(0.0, min(100.0, score))))


@lru_cache(maxsize=101)
def _render_score_icon(bounded_score: int) -> QIcon:
    color = QColor(score_color_hex(bounded_score))

    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 45))
    painter.drawEllipse(5, 7, 54, 54)
    painter.setBrush(color)
    painter.drawEllipse(5, 5, 54, 54)

    font = QFont()
    font.setBold(True)
    font.setPixelSize(24 if bounded_score < 100 else 20)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, str(bounded_score))
    painter.end()
    return QIcon(pixmap)
