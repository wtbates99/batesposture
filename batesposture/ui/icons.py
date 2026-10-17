from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_SIZE = 48  # drawn at 2x and scaled down by Qt for crisp edges


def _draw(name: str, painter: QPainter) -> None:
    """Draw a 24-unit line glyph (SF Symbols-like) into the painter."""
    if name == "appearance":  # contrast: circle, right half filled
        painter.drawEllipse(QRectF(4, 4, 16, 16))
        half = QPainterPath()
        half.moveTo(12, 4)
        half.arcTo(QRectF(4, 4, 16, 16), 90, -180)
        half.closeSubpath()
        painter.fillPath(half, painter.pen().color())
    elif name == "camera":  # video camera
        painter.drawRoundedRect(QRectF(3, 7, 13, 10), 2.5, 2.5)
        lens = QPainterPath()
        lens.moveTo(16, 10.5)
        lens.lineTo(21, 7.5)
        lens.lineTo(21, 16.5)
        lens.lineTo(16, 13.5)
        painter.drawPath(lens)
    elif name == "notifications":  # bell
        bell = QPainterPath()
        bell.moveTo(5, 17)
        bell.lineTo(19, 17)
        bell.cubicTo(17, 15, 17.5, 13, 17.5, 10.5)
        bell.cubicTo(17.5, 7, 15, 4.5, 12, 4.5)
        bell.cubicTo(9, 4.5, 6.5, 7, 6.5, 10.5)
        bell.cubicTo(6.5, 13, 7, 15, 5, 17)
        painter.drawPath(bell)
        painter.drawArc(QRectF(10, 17.5, 4, 3), 180 * 16, 180 * 16)
    elif name == "tracking":  # clock
        painter.drawEllipse(QRectF(4, 4, 16, 16))
        painter.drawLine(QPointF(12, 12), QPointF(12, 7.5))
        painter.drawLine(QPointF(12, 12), QPointF(15, 14))
    elif name == "data":  # database cylinder
        painter.drawEllipse(QRectF(5, 3.5, 14, 4.5))
        painter.drawLine(QPointF(5, 5.75), QPointF(5, 18.25))
        painter.drawLine(QPointF(19, 5.75), QPointF(19, 18.25))
        painter.drawArc(QRectF(5, 9.5, 14, 4.5), 180 * 16, 180 * 16)
        painter.drawArc(QRectF(5, 16, 14, 4.5), 180 * 16, 180 * 16)
    elif name == "advanced":  # sliders
        for y, knob in ((7, 9), (12, 15), (17, 7)):
            painter.drawLine(QPointF(4, y), QPointF(20, y))
            painter.setBrush(painter.pen().color())
            painter.drawEllipse(QPointF(knob, y), 2.2, 2.2)
            painter.setBrush(Qt.BrushStyle.NoBrush)


def _pixmap(name: str, color: QColor) -> QPixmap:
    pixmap = QPixmap(_SIZE, _SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(_SIZE / 24, _SIZE / 24)
    pen = QPen(color, 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    _draw(name, painter)
    painter.end()
    return pixmap


def line_icon(name: str, color: str, selected_color: str = "#ffffff") -> QIcon:
    """Monochrome line icon in ``color``, switching to ``selected_color`` when selected."""
    icon = QIcon()
    icon.addPixmap(_pixmap(name, QColor(color)), QIcon.Mode.Normal)
    icon.addPixmap(_pixmap(name, QColor(selected_color)), QIcon.Mode.Selected)
    return icon
