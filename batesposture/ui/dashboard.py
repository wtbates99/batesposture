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
from PyQt6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QHBoxLayout,
    QDialog,
    QFrame,
    QWidget,
)


def _score_color(score: float) -> QColor:
    """Interpolate red→amber→green for a score 0–100."""
    s = max(0.0, min(100.0, score)) / 100.0
    if s < 0.5:
        t = s / 0.5
        r, g, b = int(220 * (1 - t) + 240 * t), int(50 * (1 - t) + 160 * t), 40
    else:
        t = (s - 0.5) / 0.5
        r, g, b = (
            int(240 * (1 - t) + 52 * t),
            int(160 * (1 - t) + 199 * t),
            int(40 * (1 - t) + 89 * t),
        )
    return QColor(r, g, b)


def score_grade(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Fair"
    return "Poor"


def _format_duration(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


class SparklineWidget(QWidget):
    """Score history area chart with per-segment colour coding.

    Displays up to 120 recent posture scores as a filled area chart. Each line
    segment is coloured by interpolating red (0) → amber (50) → green (100) based
    on the average of its two endpoints. Pre-populated from persisted database
    history when the dashboard reopens, so the chart isn't blank after a restart.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.values: List[float] = []
        self.fill_color = QColor(46, 125, 255, 60)
        self.background_color = QColor("#ffffff")
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_colors(self, _line: QColor, fill: QColor, background: QColor) -> None:
        self.fill_color = fill
        self.background_color = background
        self.update()

    def update_values(self, values: List[float]) -> None:
        self.values = values
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.fillRect(rect, self.background_color)

        if len(self.values) < 2:
            painter.setPen(QPen(QColor("#aaaaaa"), 1.5))
            painter.drawLine(
                rect.left(), rect.center().y(), rect.right(), rect.center().y()
            )
            return

        min_val = min(self.values)
        max_val = max(self.values)
        if abs(max_val - min_val) < 1e-5:
            min_val = max(0.0, min_val - 5)
            max_val = min(100.0, max_val + 5)

        n = len(self.values)

        def _xy(index: int, value: float):
            x = rect.left() + (index / (n - 1)) * rect.width()
            norm = (value - min_val) / (max_val - min_val)
            y = rect.bottom() - norm * rect.height()
            return x, y

        # Filled area
        fill_path = QPainterPath()
        x0, y0 = _xy(0, self.values[0])
        fill_path.moveTo(x0, rect.bottom())
        fill_path.lineTo(x0, y0)
        for i in range(1, n):
            xi, yi = _xy(i, self.values[i])
            fill_path.lineTo(xi, yi)
        fill_path.lineTo(_xy(n - 1, self.values[-1])[0], rect.bottom())
        fill_path.closeSubpath()
        painter.fillPath(fill_path, self.fill_color)

        # Colour-coded line segments — reuse one QPen, only swap the colour
        pen = QPen(QColor(), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        for i in range(1, n):
            x1, y1 = _xy(i - 1, self.values[i - 1])
            x2, y2 = _xy(i, self.values[i])
            avg = (self.values[i - 1] + self.values[i]) / 2
            pen.setColor(_score_color(avg))
            painter.setPen(pen)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class _StatLabel(QLabel):
    """Compact card-style label for a single statistic."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._title = title
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_text("—")

    def set_value(self, value: str) -> None:
        self._update_text(value)

    def _update_text(self, value: str) -> None:
        self.setText(
            f"<small style='opacity:0.6'>{self._title}</small><br><b>{value}</b>"
        )


class PostureDashboard(QDialog):
    def __init__(
        self,
        baseline_score: float,
        preferred_theme: str,
        baseline_neck_angle: float = 10.0,
        baseline_shoulder_level: float = 0.05,
        history: Optional[List[float]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Posture Dashboard")
        self.recent_scores: deque[float] = deque(maxlen=120)
        if history:
            self.recent_scores.extend(history)
        self.baseline_score = baseline_score
        self.baseline_neck_angle = baseline_neck_angle
        self.baseline_shoulder_level = baseline_shoulder_level

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        self.card = QFrame()
        self.card.setObjectName("dashboardCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        # Video feed
        self.video_label = QLabel(self.tr("Waiting for frames…"))
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(560, 320)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Sparkline
        self.sparkline = SparklineWidget()

        # Stats row
        stats_row = QWidget()
        stats_layout = QHBoxLayout(stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(6)
        self._stat_current = _StatLabel(self.tr("Current"))
        self._stat_avg = _StatLabel(self.tr("Session Avg"))
        self._stat_min = _StatLabel(self.tr("Session Min"))
        self._stat_max = _StatLabel(self.tr("Session Max"))
        self._stat_streak = _StatLabel(self.tr("Best Streak"))
        self._stat_duration = _StatLabel(self.tr("Duration"))
        for stat in (
            self._stat_current,
            self._stat_avg,
            self._stat_min,
            self._stat_max,
            self._stat_streak,
            self._stat_duration,
        ):
            stats_layout.addWidget(stat)

        # Coaching / alert text
        self.feedback_label = QLabel(
            self.tr("Settle into a neutral posture while we gather readings.")
        )
        self.feedback_label.setWordWrap(True)

        card_layout.addWidget(self.video_label)
        card_layout.addWidget(self.sparkline)
        card_layout.addWidget(stats_row)
        card_layout.addWidget(self.feedback_label)

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
            fill = QColor(138, 180, 248, 60)
            stat_bg = "#2d2f33"
            stat_border = "rgba(255,255,255,12)"
        else:
            background = QColor("#ffffff")
            foreground = QColor("#1a1c23")
            accent = QColor("#2e7dff")
            fill = QColor(46, 125, 255, 60)
            stat_bg = "#f8f9fa"
            stat_border = "rgba(0,0,0,10)"

        self.setStyleSheet(f"QDialog {{ background-color: {background.name()}; }}")
        self.card.setStyleSheet(
            f"QFrame#dashboardCard {{"
            f"  background-color: {background.name()};"
            f"  border-radius: 12px;"
            f"  border: 1px solid rgba(0,0,0,25);"
            f"}}"
            f"QLabel {{ color: {foreground.name()}; }}"
        )
        self.feedback_label.setStyleSheet(
            f"color: {foreground.name()}; font-weight: 600; font-size: 13px;"
        )
        stat_style = (
            f"background: {stat_bg}; color: {foreground.name()}; font-size: 11px;"
            f"border: 1px solid {stat_border}; border-radius: 8px; padding: 6px 8px;"
        )
        for stat in (
            self._stat_current,
            self._stat_avg,
            self._stat_min,
            self._stat_max,
            self._stat_streak,
            self._stat_duration,
        ):
            stat.setStyleSheet(stat_style)
        self.sparkline.set_colors(accent, fill, background)

    def get_history(self) -> List[float]:
        """Return current sparkline scores for persistence."""
        return list(self.recent_scores)

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
        self,
        score: float,
        metrics: Optional[Dict[str, float]] = None,
        session_stats: Optional[dict] = None,
    ) -> None:
        self.recent_scores.append(score)
        self.sparkline.update_values(list(self.recent_scores))
        self._update_feedback_text(score, metrics)
        self._update_stats(score, session_stats)

    def _update_stats(self, current: float, stats: Optional[dict]) -> None:
        grade = score_grade(current)
        color = _score_color(current).name()
        self._stat_current.set_value(
            f"<span style='color:{color}'>{current:.0f}</span> <small>({grade})</small>"
        )
        if stats and stats.get("count", 0) > 0:
            self._stat_avg.set_value(f"{stats['avg']:.0f}")
            self._stat_min.set_value(
                f"<span style='color:#e05050'>{stats['min']:.0f}</span>"
            )
            self._stat_max.set_value(
                f"<span style='color:#4caf50'>{stats['max']:.0f}</span>"
            )
            best = stats.get("best_streak_s", 0.0)
            streak_str = _format_duration(best) if best >= 5 else "—"
            self._stat_streak.set_value(streak_str)
            self._stat_duration.set_value(
                _format_duration(stats.get("duration_s", 0.0))
            )
        else:
            for stat in (
                self._stat_avg,
                self._stat_min,
                self._stat_max,
                self._stat_streak,
                self._stat_duration,
            ):
                stat.set_value("—")

    def _update_feedback_text(
        self, score: float, metrics: Optional[Dict[str, float]]
    ) -> None:
        if score >= max(self.baseline_score - 5, 70):
            message = self.tr(
                "Nice alignment! Keep a relaxed breath and soft shoulders."
            )
        else:
            cues: List[str] = []
            if metrics:
                neck_threshold = self.baseline_neck_angle + 5.0
                shoulder_threshold = self.baseline_shoulder_level + 0.02
                if metrics.get("neck_angle", 0.0) > neck_threshold:
                    cues.append(
                        self.tr("Gently draw your head back over your shoulders.")
                    )
                if metrics.get("shoulder_vertical_delta", 0.0) > shoulder_threshold:
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
        self.feedback_label.setText(message)
