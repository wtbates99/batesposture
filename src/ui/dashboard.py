from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPalette,
)
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QDialog, QFrame, QWidget


class SparklineWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.values: List[float] = []
        self.line_color = QColor("#2e7dff")
        self.fill_color = QColor(46, 125, 255, 80)
        self.background_color = QColor("#ffffff")
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_colors(self, line: QColor, fill: QColor, background: QColor) -> None:
        self.line_color = line
        self.fill_color = fill
        self.background_color = background
        self.update()

    def update_values(self, values: List[float]) -> None:
        self.values = list(values)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.fillRect(rect, self.background_color)

        if len(self.values) < 2:
            painter.setPen(QPen(self.line_color, 2.0))
            painter.drawLine(
                rect.left(), rect.center().y(), rect.right(), rect.center().y()
            )
            return

        min_val = min(self.values)
        max_val = max(self.values)
        if abs(max_val - min_val) < 1e-5:
            min_val -= 1.0
            max_val += 1.0

        path = QPainterPath()
        for index, value in enumerate(self.values):
            x = rect.left() + (index / (len(self.values) - 1)) * rect.width()
            normalized = (value - min_val) / (max_val - min_val)
            y = rect.bottom() - normalized * rect.height()
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        fill_path = QPainterPath(path)
        fill_path.lineTo(rect.right(), rect.bottom())
        fill_path.lineTo(rect.left(), rect.bottom())
        fill_path.closeSubpath()

        painter.fillPath(fill_path, self.fill_color)
        painter.setPen(QPen(self.line_color, 2.0))
        painter.drawPath(path)


class PostureDashboard(QDialog):
    def __init__(
        self,
        baseline_score: float,
        preferred_theme: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.recent_scores: deque[float] = deque(maxlen=120)
        self.baseline_score = baseline_score

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.card = QFrame()
        self.card.setObjectName("dashboardCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        self.video_label = QLabel(self.tr("Waiting for frames..."))
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(560, 320)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.sparkline = SparklineWidget()

        self.coaching_label = QLabel(
            self.tr("Settle into a neutral posture while we gather readings.")
        )
        self.coaching_label.setWordWrap(True)

        card_layout.addWidget(self.video_label)
        card_layout.addWidget(self.sparkline)
        card_layout.addWidget(self.coaching_label)

        outer_layout.addWidget(self.card)
        self._apply_theme(preferred_theme)

    def _apply_theme(self, preference: str) -> None:
        palette = self.palette()
        if preference == "dark":
            is_dark = True
        elif preference == "light":
            is_dark = False
        else:
            window_color = palette.color(QPalette.ColorRole.Window)
            luminance = (
                0.299 * window_color.red()
                + 0.587 * window_color.green()
                + 0.114 * window_color.blue()
            )
            is_dark = luminance < 128

        if is_dark:
            background = QColor("#202124")
            foreground = QColor("#f1f3f4")
            accent = QColor("#8ab4f8")
            fill = QColor(138, 180, 248, 90)
        else:
            background = QColor("#ffffff")
            foreground = QColor("#1a1c23")
            accent = QColor("#2e7dff")
            fill = QColor(46, 125, 255, 80)

        self.card.setStyleSheet(
            "QFrame#dashboardCard {"
            f"background-color: {background.name()};"
            "border-radius: 16px;"
            "border: 1px solid rgba(0,0,0,30);"
            "}"
            f"QLabel {{ color: {foreground.name()}; }}"
        )
        self.coaching_label.setStyleSheet(
            f"color: {foreground.name()}; font-weight: 600;"
        )
        self.sparkline.set_colors(accent, fill, background)

    def update_frame(self, frame) -> None:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        image = QImage(rgb_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        ratio = self.devicePixelRatioF()
        pixmap.setDevicePixelRatio(ratio)
        scaled = pixmap.scaled(
            int(self.video_label.width() * ratio),
            int(self.video_label.height() * ratio),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)

    def update_score(
        self, score: float, metrics: Optional[Dict[str, float]] = None
    ) -> None:
        self.recent_scores.append(score)
        self.sparkline.update_values(list(self.recent_scores))
        self._update_coaching_text(score, metrics)

    def _update_coaching_text(
        self, score: float, metrics: Optional[Dict[str, float]]
    ) -> None:
        if score >= max(self.baseline_score - 5, 70):
            message = self.tr(
                "Nice alignment! Keep a relaxed breath and soft shoulders."
            )
        else:
            cues: List[str] = []
            if metrics:
                if metrics.get("neck_angle", 0.0) > 15.0:
                    cues.append(
                        self.tr("Gently draw your head back over your shoulders.")
                    )
                if metrics.get("shoulder_vertical_delta", 0.0) > 0.05:
                    cues.append(self.tr("Level your shoulders to center your posture."))
                if metrics.get("spine_angle", 0.0) > 10.0:
                    cues.append(self.tr("Lengthen through your spine and sit tall."))
            if not cues:
                cues.append(
                    self.tr(
                        "Reset by rolling your shoulders back and opening your chest."
                    )
                )
            message = " ".join(cues[:2])
        self.coaching_label.setText(message)
