from __future__ import annotations

import sys
from functools import lru_cache

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

from .theme import score_color_hex

ICON_SIZE = 64
# macOS tints template ("mask") images to match the menu bar, like system icons.
# Other desktops have no such convention, so they always get the coloured ring.
_TEMPLATE_ICONS = sys.platform == "darwin"


def create_score_icon(score: float, alert: bool = False) -> QIcon:
    """Render the tray icon: a ring filled to the score with the score inside.

    On macOS the icon is a monochrome template while posture is fine and turns
    colour only when ``alert`` is set, so it stays calm until it matters.
    """
    colored = alert or not _TEMPLATE_ICONS
    return _render_score_icon(round(max(0.0, min(100.0, score))), colored)


@lru_cache(maxsize=202)
def _render_score_icon(score: int, colored: bool) -> QIcon:
    if not colored:
        ink = QColor("#000000")  # template: macOS supplies the real colour
    elif _TEMPLATE_ICONS:
        # Apple system orange/red read clearly on light and dark menu bars
        ink = QColor("#ff9f0a" if score >= 55 else "#ff3b30")
    else:
        ink = QColor(score_color_hex(score, "dark"))
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    ring = QRectF(5, 5, ICON_SIZE - 10, ICON_SIZE - 10)
    track = QColor(ink)
    track.setAlpha(70)
    pen = QPen(track, 7.0)
    painter.setPen(pen)
    painter.drawEllipse(ring)
    pen.setColor(ink)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    # Qt angles are 1/16 degree, counter-clockwise from 3 o'clock
    painter.drawArc(ring, 90 * 16, -round(score / 100 * 360 * 16))

    font = QFont()
    font.setBold(True)
    font.setPixelSize(26 if score < 100 else 21)
    painter.setFont(font)
    painter.setPen(ink)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, str(score))
    painter.end()

    icon = QIcon(pixmap)
    icon.setIsMask(not colored)
    return icon
