from __future__ import annotations

from collections import deque

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import dashboard_stylesheet, theme_colors


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values: list[float] = []
        self.fill_color = QColor(46, 125, 255, 60)
        self.background_color = QColor("#ffffff")
        self.setMinimumHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_colors(self, _line: QColor, fill: QColor, background: QColor) -> None:
        self.fill_color = fill
        self.background_color = background
        self.update()

    def update_values(self, values: list[float]) -> None:
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

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("statCard")
        self.setMinimumHeight(54)
        self.setWordWrap(True)
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
        history: list[float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("BatesPosture · Live Dashboard")
        self.setMinimumSize(620, 560)
        self.recent_scores: deque[float] = deque(maxlen=120)
        if history:
            self.recent_scores.extend(history)
        self.baseline_score = baseline_score
        self.baseline_neck_angle = baseline_neck_angle
        self.baseline_shoulder_level = baseline_shoulder_level
        self._theme_preference = preferred_theme

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(20, 18, 20, 20)
        outer_layout.setSpacing(14)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_column = QVBoxLayout()
        title_column.setSpacing(1)
        title = QLabel(self.tr("Live posture"))
        title.setObjectName("dashboardTitle")
        subtitle = QLabel(self.tr("Session in progress"))
        subtitle.setObjectName("dashboardSubtitle")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        header_layout.addLayout(title_column)
        header_layout.addStretch()
        self.score_label = QLabel("—")
        self.score_label.setObjectName("liveScore")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self.score_label)

        # Video feed
        self.video_label = QLabel(self.tr("Waiting for frames…"))
        self.video_label.setObjectName("videoFeed")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(320, 180)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Sparkline
        self.sparkline = SparklineWidget()

        # Stats row
        stats_row = QWidget()
        stats_layout = QGridLayout(stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setHorizontalSpacing(8)
        stats_layout.setVerticalSpacing(8)
        self._stat_current = _StatLabel(self.tr("Current"))
        self._stat_avg = _StatLabel(self.tr("Session Avg"))
        self._stat_min = _StatLabel(self.tr("Session Min"))
        self._stat_max = _StatLabel(self.tr("Session Max"))
        self._stat_streak = _StatLabel(self.tr("Best Streak"))
        self._stat_duration = _StatLabel(self.tr("Duration"))
        for index, stat in enumerate(
            (
                self._stat_current,
                self._stat_avg,
                self._stat_min,
                self._stat_max,
                self._stat_streak,
                self._stat_duration,
            )
        ):
            stats_layout.addWidget(stat, index // 3, index % 3)

        # Coaching / alert text
        self.feedback_label = QLabel(
            self.tr("Settle into a neutral posture while we gather readings.")
        )
        self.feedback_label.setObjectName("feedback")
        self.feedback_label.setWordWrap(True)

        outer_layout.addWidget(header)
        outer_layout.addWidget(self.video_label, 1)
        outer_layout.addWidget(self.sparkline)
        outer_layout.addWidget(stats_row)
        outer_layout.addWidget(self.feedback_label)
        self._apply_theme(preferred_theme)

    def _apply_theme(self, preference: str) -> None:
        colors = theme_colors(preference)
        self.setStyleSheet(dashboard_stylesheet(preference))
        accent = QColor(colors.accent)
        fill = QColor(accent.red(), accent.green(), accent.blue(), 55)
        self.sparkline.set_colors(accent, fill, QColor(colors.canvas))

    def get_history(self) -> list[float]:
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
        metrics: dict[str, float] | None = None,
        session_stats: dict | None = None,
    ) -> None:
        self.recent_scores.append(score)
        self.sparkline.update_values(list(self.recent_scores))
        self._update_feedback_text(score, metrics)
        self._update_stats(score, session_stats)

    def _update_stats(self, current: float, stats: dict | None) -> None:
        grade = score_grade(current)
        color = _score_color(current).name()
        self.score_label.setText(f"{current:.0f}%")
        self.score_label.setStyleSheet(f"color: {color};")
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
        self, score: float, metrics: dict[str, float] | None
    ) -> None:
        if score >= max(self.baseline_score - 5, 70):
            message = self.tr(
                "Nice alignment! Keep a relaxed breath and soft shoulders."
            )
        else:
            cues: list[str] = []
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
