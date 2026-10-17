from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .dashboard import SparklineWidget
from .theme import is_dark_theme, score_color_hex, theme_colors

POPOVER_WIDTH = 300


class ScoreRing(QWidget):
    """Activity-style ring filled to the score, with the number in the middle."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.score: float | None = None
        self._ink = QColor("#46b96b")
        self._track = QColor(128, 128, 128, 60)
        self._text = QColor("#ffffff")
        self.setFixedSize(76, 76)

    def set_colors(self, track: QColor, text: QColor) -> None:
        self._track = track
        self._text = text
        self.update()

    def set_score(self, score: float | None, ink: QColor) -> None:
        self.score = score
        self._ink = ink
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        pen = QPen(self._track, 8.0)
        painter.setPen(pen)
        painter.drawEllipse(ring)
        if self.score is not None:
            pen.setColor(self._ink)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(ring, 90 * 16, -round(self.score / 100 * 360 * 16))
        font = painter.font()
        font.setPixelSize(24)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self._text)
        text = "—" if self.score is None else f"{self.score:.0f}"
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)


class TrayPopover(QWidget):
    """Menu-bar panel: score at a glance plus the handful of actions people use.

    The owner wires the buttons and pushes state with ``set_state``; the full
    menu stays one click away behind "More".
    """

    def __init__(self, preference: str, parent: QWidget | None = None) -> None:
        super().__init__(
            parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("trayPopover")
        self.setFixedWidth(POPOVER_WIDTH)

        self.ring = ScoreRing()
        self.headline = QLabel("Not tracking")
        self.headline.setObjectName("popoverHeadline")
        self.status = QLabel("")
        self.status.setObjectName("popoverStatus")
        self.status.setWordWrap(True)
        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        text_column.addStretch()
        text_column.addWidget(self.headline)
        text_column.addWidget(self.status)
        text_column.addStretch()
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self.ring)
        top.addLayout(text_column, 1)

        self.trend_label = QLabel("LAST 10 MINUTES")
        self.trend_label.setObjectName("popoverCaption")
        self.trend = SparklineWidget()
        self.trend.setMinimumHeight(44)
        self.trend.setMaximumHeight(44)

        self.tracking_button = QPushButton("Start tracking")
        self.tracking_button.setObjectName("primaryButton")
        self.dashboard_button = QPushButton("Dashboard")
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.tracking_button, 1)
        actions.addWidget(self.dashboard_button, 1)

        self.snooze_button = self._link_button("Snooze alerts for 1 hour")
        self.settings_button = self._link_button("Settings…")
        self.more_button = self._link_button("More")
        self.quit_button = self._link_button("Quit")
        footer = QHBoxLayout()
        footer.setSpacing(4)
        footer.addWidget(self.settings_button)
        footer.addWidget(self.more_button)
        footer.addStretch()
        footer.addWidget(self.quit_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self.trend_label)
        layout.addWidget(self.trend)
        layout.addLayout(actions)
        layout.addWidget(self.snooze_button)
        layout.addWidget(_Divider())
        layout.addLayout(footer)
        self.apply_theme(preference)

    @staticmethod
    def _link_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("linkButton")
        button.setFlat(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        return button

    def apply_theme(self, preference: str) -> None:
        self._preference = "dark" if is_dark_theme(preference) else "light"
        c = theme_colors(self._preference)
        self._background = QColor(c.surface)
        self._border = QColor(c.border)
        track = QColor(c.muted)
        track.setAlpha(60)
        self.ring.set_colors(track, QColor(c.text))
        accent = QColor(c.accent)
        self.trend.set_colors(
            QColor(accent.red(), accent.green(), accent.blue(), 45),
            QColor(c.surface),
            QColor(c.muted),
            self._preference,
        )
        # The dark theme's bright accent needs dark text to stay legible
        on_accent = "#0f2416" if self._preference == "dark" else "#ffffff"
        self.setStyleSheet(f"""
QLabel {{ color: {c.text}; background: transparent; }}
QLabel#popoverHeadline {{ font-size: 16px; font-weight: 700; }}
QLabel#popoverStatus {{ color: {c.muted}; font-size: 12px; }}
QLabel#popoverCaption {{ color: {c.muted}; font-size: 10px; font-weight: 600; }}
QPushButton {{ background: {c.surface_alt}; color: {c.text}; border: 1px solid {c.border};
    border-radius: 7px; padding: 6px 12px; min-height: 26px; font-weight: 600; }}
QPushButton:hover {{ border-color: {c.muted}; }}
QPushButton:disabled {{ color: {c.muted}; }}
QPushButton#primaryButton {{ background: {c.accent}; color: {on_accent}; border-color: {c.accent}; }}
QPushButton#primaryButton:hover {{ background: {c.accent_hover}; }}
QPushButton#linkButton {{ background: transparent; border: none; color: {c.text};
    padding: 3px 6px; min-height: 0; font-weight: 500; text-align: left; }}
QPushButton#linkButton:hover {{ color: {c.accent}; }}
QPushButton#linkButton:checked {{ color: {c.highlight}; }}
""")

    def set_state(
        self,
        score: float | None,
        headline: str,
        status: str,
        trend: list[float],
        tracking: bool,
        dashboard_available: bool,
        snooze_label: str,
        alert_threshold: float,
        baseline: float,
    ) -> None:
        ink = QColor(score_color_hex(score or 0.0, self._preference))
        self.ring.set_score(score, ink)
        self.headline.setText(headline)
        self.status.setText(status)
        self.trend.set_reference_lines(alert_threshold, baseline)
        # Zoom the mini chart to the data so a 10-point dip is visible
        floor = min([*trend, alert_threshold], default=alert_threshold)
        self.trend.set_value_range(max(0.0, floor - 8.0), 100.0)
        self.trend.update_values(trend)
        if self.isVisible():
            self.fit_to_content()
        self.tracking_button.setText("Pause tracking" if tracking else "Start tracking")
        self.dashboard_button.setEnabled(dashboard_available)
        self.snooze_button.setText(snooze_label)

    def fit_to_content(self) -> None:
        # adjustSize() ignores word-wrapped labels; ask the layout for the
        # height it needs at the popover's fixed width.
        self.resize(POPOVER_WIDTH, self.layout().totalHeightForWidth(POPOVER_WIDTH))

    def show_near(self, anchor: QRect) -> None:
        """Open under a top menu bar or above a bottom taskbar, kept on screen."""
        self.fit_to_content()
        screen = QGuiApplication.screenAt(anchor.center()) or (
            QGuiApplication.primaryScreen()
        )
        area = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        if anchor.isEmpty():
            anchor = QRect(area.right() - 40, area.top(), 1, 1)
        x = anchor.center().x() - self.width() // 2
        if anchor.center().y() < area.center().y():
            y = max(anchor.bottom(), area.top()) + 6
        else:
            y = min(anchor.top(), area.bottom()) - self.height() - 6
        x = max(area.left() + 6, min(x, area.right() - self.width() - 6))
        self.move(QPoint(x, y))
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        painter.fillPath(path, self._background)
        painter.setPen(QPen(self._border, 1.0))
        painter.drawPath(path)


class _Divider(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(1)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(128, 128, 128, 60);")
