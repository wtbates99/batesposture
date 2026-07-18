from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

ICON_SIZE = 64


def create_score_icon(score: float) -> QIcon:
    """Render a compact, color-coded posture score for the system tray."""
    bounded_score = max(0.0, min(100.0, score))
    color = QColor.fromHsv(round(bounded_score * 1.2), 185, 205)

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
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, str(round(bounded_score)))
    painter.end()
    return QIcon(pixmap)
