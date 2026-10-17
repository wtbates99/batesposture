from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from math import exp
from time import monotonic

import numpy as np
from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from ..ml.mediapipe_compat import PoseLandmark
from .theme import (
    dashboard_stylesheet,
    is_dark_theme,
    score_color_hex,
    score_grade,
    theme_colors,
)


def _score_color(score: float, preference: str = "light") -> QColor:
    """Return the shared (do not mutate) QColor for a score's band."""
    return _qcolor(score_color_hex(score, preference))


@lru_cache(maxsize=32)
def _qcolor(hex_color: str) -> QColor:
    return QColor(hex_color)


def _metric_mean(metrics: dict[str, float], *keys: str) -> float:
    return sum(metrics[key] for key in keys) / len(keys)


@dataclass(frozen=True)
class _Component:
    """One user-facing slice of the posture score."""

    key: str
    title: str
    cue: str
    metric_keys: tuple[str, ...]

    def value(self, metrics: dict[str, float] | None) -> float | None:
        """Return the 0–1 component score, or None when it can't be measured."""
        if not metrics or any(key not in metrics for key in self.metric_keys):
            return None
        if self.key == "spine" and not metrics.get("hips_visible", 1.0):
            return None
        return _metric_mean(metrics, *self.metric_keys)


COMPONENTS = (
    _Component(
        "head_forward",
        "Head forward",
        "Bring your chin back so your ears sit over your shoulders.",
        ("head_tilt_score",),
    ),
    _Component(
        "neck",
        "Neck",
        "Gently draw your head back over your shoulders.",
        ("neck_vertical_score",),
    ),
    _Component(
        "head_level",
        "Head level",
        "Face the screen squarely and level your head.",
        ("head_side_tilt_score", "head_rotation_score"),
    ),
    _Component(
        "shoulders",
        "Shoulders",
        "Level your shoulders and let them drop back.",
        ("shoulder_level_score", "shoulder_roll_score"),
    ),
    _Component(
        "spine",
        "Spine",
        "Lengthen through your spine and sit tall.",
        ("spine_alignment_score",),
    ),
)
_COMPONENTS_BY_KEY = {component.key: component for component in COMPONENTS}
# Components below this need attention; the worst ones become the coaching cue.
_COMPONENT_FLAG_BELOW = 0.75
# Breakdown bars ease toward per-frame values instead of jittering at 15 Hz.
_BAR_EASE_S = 0.35

# Auto-framing: the crop eases toward the person's head and shoulders, and back
# out to the whole frame when nobody is detected.
_FRAMING_EASE_S = 0.6
_FRAMING_NECKS_TALL = 4.5  # crop height in neck lengths (ear line → shoulders)
_FRAMING_MIN_HEIGHT = 0.5  # never zoom in past half the frame height


def _ease(dt: float, time_constant: float) -> float:
    """Fraction of the remaining distance to cover after ``dt`` seconds."""
    return 1.0 - exp(-max(dt, 0.0) / time_constant)


def _set_text(label: QLabel, text: str) -> None:
    # Skips the relayout a changed QLabel triggers when nothing changed.
    if label.text() != text:
        label.setText(text)


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
        self.muted_color = QColor("#657069")
        self.threshold = 60.0
        self.baseline = 75.0
        self.value_min = 0.0
        self.value_max = 100.0
        self._theme_preference = "light"
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_colors(
        self,
        fill: QColor,
        background: QColor,
        muted: QColor,
        preference: str,
    ) -> None:
        self.fill_color = fill
        self.background_color = background
        self.muted_color = muted
        self._theme_preference = preference
        self.update()

    def set_reference_lines(self, threshold: float, baseline: float) -> None:
        self.threshold = threshold
        self.baseline = baseline
        self.update()

    def set_value_range(self, low: float, high: float) -> None:
        self.value_min, self.value_max = low, max(high, low + 1.0)
        self.update()

    def update_values(self, values: list[float]) -> None:
        self.values = values
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.fillRect(rect, self.background_color)

        span = self.value_max - self.value_min

        def _y(value: float) -> float:
            value = max(self.value_min, min(self.value_max, value))
            return rect.bottom() - (value - self.value_min) / span * rect.height()

        painter.setPen(QPen(self.muted_color, 1.0, Qt.PenStyle.DotLine))
        painter.drawLine(
            rect.left(), int(_y(self.baseline)), rect.right(), int(_y(self.baseline))
        )
        painter.setPen(
            QPen(
                _score_color(self.threshold - 1, self._theme_preference),
                1.0,
                Qt.PenStyle.DashLine,
            )
        )
        painter.drawLine(
            rect.left(),
            int(_y(self.threshold)),
            rect.right(),
            int(_y(self.threshold)),
        )

        if len(self.values) < 2:
            painter.setPen(QPen(QColor("#aaaaaa"), 1.5))
            painter.drawLine(
                rect.left(), rect.center().y(), rect.right(), rect.center().y()
            )
            return

        n = len(self.values)

        def _xy(index: int, value: float):
            x = rect.left() + (index / (n - 1)) * rect.width()
            return x, _y(value)

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

        # Colour-coded line: one path per run of same-band segments
        pen = QPen(QColor(), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        run_color: QColor | None = None
        run_path = QPainterPath()
        for i in range(1, n):
            avg = (self.values[i - 1] + self.values[i]) / 2
            color = _score_color(avg, self._theme_preference)
            if color is not run_color:
                if run_color is not None:
                    pen.setColor(run_color)
                    painter.setPen(pen)
                    painter.drawPath(run_path)
                run_color = color
                run_path = QPainterPath()
                run_path.moveTo(*_xy(i - 1, self.values[i - 1]))
            run_path.lineTo(*_xy(i, self.values[i]))
        pen.setColor(run_color)
        painter.setPen(pen)
        painter.drawPath(run_path)


class VideoView(QWidget):
    """Camera frame with a posture skeleton drawn by Qt.

    Only the landmarks that feed the score are drawn, and each segment is
    coloured by the component it measures, so the overlay shows *why* the
    score moved. The view fills its rect and frames the person's head and
    shoulders. The frame is wrapped as a BGR QImage without copying.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._frame: np.ndarray | None = None
        self._image: QImage | None = None
        self._points: np.ndarray | None = None
        self._component_values: dict[str, float | None] = {}
        self._theme_preference = "light"
        self._border = QColor("#d9e1da")
        self._crop: QRectF | None = None  # in image pixels
        self._crop_at = 0.0
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_theme(self, preference: str, border: QColor) -> None:
        self._theme_preference = preference
        self._border = border
        self.update()

    def set_frame(
        self,
        frame: np.ndarray,
        points: np.ndarray | None = None,
        component_values: dict[str, float | None] | None = None,
    ) -> None:
        frame = np.ascontiguousarray(frame)
        h, w = frame.shape[:2]
        # The QImage borrows frame's buffer; keep the array alive alongside it.
        self._frame = frame
        self._image = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_BGR888)
        self._points = points
        self._component_values = component_values or {}
        self._ease_crop(self._desired_crop(w, h), monotonic())
        self.update()

    def _aspect(self) -> float:
        return max(self.width(), 1) / max(self.height(), 1)

    def _desired_crop(self, w: int, h: int) -> QRectF:
        points = self._points
        if points is None:
            crop_h, cx, cy = float(h), w / 2, h / 2
        else:
            ear_y = points[[PoseLandmark.LEFT_EAR, PoseLandmark.RIGHT_EAR], 1].mean()
            shoulders = points[
                [PoseLandmark.LEFT_SHOULDER, PoseLandmark.RIGHT_SHOULDER]
            ]
            neck = max(float(shoulders[:, 1].mean() - ear_y), 0.02)
            fraction = min(max(_FRAMING_NECKS_TALL * neck, _FRAMING_MIN_HEIGHT), 1.0)
            crop_h = fraction * h
            cx = float(shoulders[:, 0].mean()) * w
            cy = float(ear_y + 0.4 * neck) * h
        return _fit(
            QRectF(cx - crop_h / 2, cy - crop_h / 2, crop_h, crop_h),
            self._aspect(),
            w,
            h,
        )

    def _ease_crop(self, desired: QRectF, now: float) -> None:
        current = self._crop
        if current is None:
            self._crop = desired
        else:
            a = _ease(now - self._crop_at, _FRAMING_EASE_S)
            self._crop = QRectF(
                current.x() + (desired.x() - current.x()) * a,
                current.y() + (desired.y() - current.y()) * a,
                current.width() + (desired.width() - current.width()) * a,
                current.height() + (desired.height() - current.height()) * a,
            )
        self._crop_at = now

    def _to_widget(self, crop: QRectF, x: float, y: float) -> QPointF:
        image = self._image
        return QPointF(
            (x * image.width() - crop.x()) / crop.width() * self.width(),
            (y * image.height() - crop.y()) / crop.height() * self.height(),
        )

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        frame_path = QPainterPath()
        frame_path.addRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8
        )
        painter.fillPath(frame_path, QColor("#101411"))
        painter.setClipPath(frame_path)
        if self._image is not None and self._crop is not None:
            # Re-fit to the current aspect in case the widget was just resized
            crop = _fit(
                self._crop, self._aspect(), self._image.width(), self._image.height()
            )
            painter.drawImage(QRectF(self.rect()), self._image, crop)
            if self._points is not None:
                self._draw_skeleton(painter, crop)
        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self._border, 1.0))
        painter.drawPath(frame_path)

    def _draw_skeleton(self, painter: QPainter, crop: QRectF) -> None:
        points = self._points

        def _at(*indices: int) -> QPointF:
            x, y = points[list(indices), :2].mean(axis=0)
            return self._to_widget(crop, x, y)

        nose = _at(PoseLandmark.NOSE)
        left_ear, right_ear = _at(PoseLandmark.LEFT_EAR), _at(PoseLandmark.RIGHT_EAR)
        mid_ear = _at(PoseLandmark.LEFT_EAR, PoseLandmark.RIGHT_EAR)
        left_sh = _at(PoseLandmark.LEFT_SHOULDER)
        right_sh = _at(PoseLandmark.RIGHT_SHOULDER)
        mid_sh = _at(PoseLandmark.LEFT_SHOULDER, PoseLandmark.RIGHT_SHOULDER)
        segments = [
            (left_ear, right_ear, "head_level"),
            (nose, mid_ear, "head_forward"),
            (mid_ear, mid_sh, "neck"),
            (left_sh, right_sh, "shoulders"),
        ]
        joints = [nose, left_ear, right_ear, left_sh, right_sh]
        if self._component_values.get("spine") is not None:
            mid_hip = _at(PoseLandmark.LEFT_HIP, PoseLandmark.RIGHT_HIP)
            segments.append((mid_sh, mid_hip, "spine"))
            joints.append(mid_hip)

        pen = QPen(QColor(), 4.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        for start, end, key in segments:
            value = self._component_values.get(key)
            color = (
                QColor(255, 255, 255, 200)
                if value is None
                else _score_color(value * 100, "dark")
            )
            pen.setColor(color)
            painter.setPen(pen)
            painter.drawLine(start, end)
        painter.setPen(QPen(QColor(16, 20, 17, 220), 1.5))
        painter.setBrush(QColor("#ffffff"))
        for joint in joints:
            painter.drawEllipse(joint, 3.5, 3.5)


def _fit(rect: QRectF, aspect: float, w: int, h: int) -> QRectF:
    """Reshape ``rect`` to ``aspect`` about its centre, kept inside a w×h image."""
    crop_h = min(rect.height(), float(h))
    crop_w = crop_h * aspect
    if crop_w > w:
        crop_w, crop_h = float(w), w / aspect
    x = min(max(rect.center().x() - crop_w / 2, 0.0), w - crop_w)
    y = min(max(rect.center().y() - crop_h / 2, 0.0), h - crop_h)
    return QRectF(x, y, crop_w, crop_h)


class _ComponentRow(QWidget):
    """Label, value, and bar for one posture component."""

    def __init__(
        self, title: str, unavailable_text: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.title = title
        self._unavailable_text = unavailable_text
        self.value: float | None = None
        self.flagged = False
        self._theme_preference = "light"
        self._colors = theme_colors("light")
        self.setObjectName("componentRow")
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_theme(self, preference: str) -> None:
        self._theme_preference = preference
        self._colors = theme_colors(preference)
        self.update()

    def set_state(self, value: float | None, flagged: bool) -> None:
        if value == self.value and flagged == self.flagged:
            return
        self.value = value
        self.flagged = flagged
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._colors
        active = self.isEnabled() and self.value is not None
        rect = QRectF(self.rect())

        font = painter.font()
        font.setPointSizeF(max(font.pointSizeF(), 11.0))
        font.setBold(self.flagged and active)
        painter.setFont(font)
        text_rect = QRectF(rect.left(), rect.top(), rect.width(), 20)
        painter.setPen(QColor(c.text if active else c.muted))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title,
        )
        if self.value is None:
            detail = self._unavailable_text
        else:
            detail = f"{self.value * 100:.0f}"
        painter.setPen(QColor(c.muted))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            detail,
        )

        track = QRectF(rect.left(), rect.top() + 24, rect.width(), 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c.surface_alt))
        painter.drawRoundedRect(track, 3, 3)
        if active:
            fill = QRectF(track)
            fill.setWidth(max(track.height(), track.width() * self.value))
            painter.setBrush(_score_color(self.value * 100, self._theme_preference))
            painter.drawRoundedRect(fill, 3, 3)


class PostureDashboard(QDialog):
    # Shown, hidden, minimized, or restored — the owner adjusts the frame rate.
    on_screen_changed = pyqtSignal()

    def __init__(
        self,
        baseline_score: float,
        preferred_theme: str,
        baseline_neck_angle: float = 10.0,
        baseline_shoulder_level: float = 0.05,
        alert_threshold: float = 60.0,
        history: list[float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("BatesPosture · Live Dashboard")
        self.setMinimumSize(640, 560)
        self.recent_scores: deque[float] = deque(maxlen=120)
        if history:
            self.recent_scores.extend(history)
        self.baseline_score = baseline_score
        self.baseline_neck_angle = baseline_neck_angle
        self.baseline_shoulder_level = baseline_shoulder_level
        self.alert_threshold = alert_threshold
        self._theme_preference = preferred_theme
        self._last_chart_sample_at: float | None = None
        self._tracking_state = "starting"
        self._component_values: dict[str, float | None] = {}
        self._shown_values: dict[str, float | None] = {}
        self._shown_at = 0.0
        self._score_css = ""

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
        self.subtitle = QLabel(self.tr("Starting camera…"))
        self.subtitle.setObjectName("dashboardSubtitle")
        title_column.addWidget(title)
        title_column.addWidget(self.subtitle)
        header_layout.addLayout(title_column)
        header_layout.addStretch()
        score_column = QVBoxLayout()
        score_column.setSpacing(0)
        self.score_label = QLabel("—")
        self.score_label.setObjectName("liveScore")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.grade_label = QLabel("")
        self.grade_label.setObjectName("liveGrade")
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        score_column.addWidget(self.score_label)
        score_column.addWidget(self.grade_label)
        header_layout.addLayout(score_column)

        # Video feed with the "waiting" message stacked on top
        self.video_view = VideoView()
        self.video_overlay = QLabel(self.tr("Starting camera…"))
        self.video_overlay.setObjectName("videoOverlay")
        self.video_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_overlay.setWordWrap(True)
        video_container = QWidget()
        video_layout = QStackedLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        video_layout.addWidget(self.video_view)
        video_layout.addWidget(self.video_overlay)

        # Per-component breakdown beside the video
        breakdown = QWidget()
        breakdown.setObjectName("breakdownPanel")
        breakdown.setFixedWidth(210)
        breakdown_layout = QVBoxLayout(breakdown)
        breakdown_layout.setContentsMargins(14, 12, 14, 12)
        breakdown_layout.setSpacing(6)
        breakdown_title = QLabel(self.tr("BREAKDOWN"))
        breakdown_title.setObjectName("chartLabel")
        breakdown_layout.addWidget(breakdown_title)
        self.component_rows: dict[str, _ComponentRow] = {}
        for component in COMPONENTS:
            row = _ComponentRow(
                self.tr(component.title),
                self.tr("hips out of view") if component.key == "spine" else "—",
            )
            self.component_rows[component.key] = row
            breakdown_layout.addWidget(row)
        breakdown_layout.addStretch()
        self._breakdown = breakdown

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(video_container, 1)
        body.addWidget(breakdown)

        # Sparkline
        self.sparkline = SparklineWidget()
        self.sparkline.set_reference_lines(alert_threshold, baseline_score)
        chart_label = QLabel(
            self.tr("TREND · LAST 2 MINUTES · DOTTED: BASELINE · DASHED: ALERT")
        )
        chart_label.setObjectName("chartLabel")

        self.session_label = QLabel(self.tr("Session —"))
        self.session_label.setObjectName("sessionSummary")

        # Coaching / alert text
        self.feedback_label = QLabel(
            self.tr("Settle into a neutral posture while we gather readings.")
        )
        self.feedback_label.setObjectName("feedback")
        self.feedback_label.setWordWrap(True)

        outer_layout.addWidget(header)
        outer_layout.addLayout(body, 1)
        outer_layout.addWidget(chart_label)
        outer_layout.addWidget(self.sparkline)
        outer_layout.addWidget(self.session_label)
        outer_layout.addWidget(self.feedback_label)
        self._apply_theme(preferred_theme)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.on_screen_changed.emit()

    def hideEvent(self, event):  # noqa: N802
        super().hideEvent(event)
        self.on_screen_changed.emit()

    def changeEvent(self, event):  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.on_screen_changed.emit()

    def _apply_theme(self, preference: str) -> None:
        # Resolve "system" once so per-paint colour lookups skip the palette.
        preference = "dark" if is_dark_theme(preference) else "light"
        self._theme_preference = preference
        colors = theme_colors(preference)
        self.setStyleSheet(dashboard_stylesheet(preference))
        accent = QColor(colors.accent)
        fill = QColor(accent.red(), accent.green(), accent.blue(), 55)
        self.sparkline.set_colors(
            fill,
            QColor(colors.canvas),
            QColor(colors.muted),
            preference,
        )
        self.video_view.set_theme(preference, QColor(colors.border))
        for row in self.component_rows.values():
            row.set_theme(preference)

    def get_history(self) -> list[float]:
        """Return current sparkline scores for persistence."""
        return list(self.recent_scores)

    def update_frame(self, frame, points: np.ndarray | None = None) -> None:
        """Show a frame; pass pose points to draw the skeleton over it."""
        self.video_view.set_frame(
            frame, points, self._component_values if points is not None else None
        )

    def update_score(
        self,
        score: float,
        metrics: dict[str, float] | None = None,
        session_stats: dict | None = None,
    ) -> None:
        now = monotonic()
        if (
            self._last_chart_sample_at is None
            or now - self._last_chart_sample_at >= 1.0
        ):
            self.recent_scores.append(score)
            self.sparkline.update_values(list(self.recent_scores))
            self._last_chart_sample_at = now
        self._update_components(score, metrics)
        self._update_feedback_text(score, metrics)
        self._update_stats(score, session_stats)

    def _flagged_components(self, metrics: dict[str, float] | None) -> list[str]:
        """Return component keys needing attention, worst first.

        Neck and shoulders are judged against the calibrated baseline so a
        person's natural posture doesn't trigger constant corrections.
        """
        if not metrics:
            return []
        flagged = []
        for key, value in self._component_values.items():
            if value is None or value >= _COMPONENT_FLAG_BELOW:
                continue
            if key == "neck" and metrics.get("neck_angle", 0.0) <= (
                self.baseline_neck_angle + 5.0
            ):
                continue
            if key == "shoulders" and metrics.get("shoulder_vertical_delta", 0.0) <= (
                self.baseline_shoulder_level + 0.02
            ):
                continue
            flagged.append(key)
        return sorted(flagged, key=lambda key: self._component_values[key])

    def _is_good(self, score: float) -> bool:
        return score >= max(self.baseline_score - 5, 70)

    def _update_components(
        self, score: float, metrics: dict[str, float] | None
    ) -> None:
        self._component_values = {
            component.key: component.value(metrics) for component in COMPONENTS
        }
        flagged = [] if self._is_good(score) else self._flagged_components(metrics)
        worst = flagged[0] if flagged else None
        now = monotonic()
        a = _ease(now - self._shown_at, _BAR_EASE_S)
        self._shown_at = now
        for key, row in self.component_rows.items():
            target = self._component_values[key]
            shown = self._shown_values.get(key)
            if target is not None and shown is not None:
                target = shown + (target - shown) * a
            self._shown_values[key] = target
            row.set_state(target, key == worst)

    def _set_score_css(self, css: str) -> None:
        # setStyleSheet re-polishes the widget; only pay for it on a change.
        if css != self._score_css:
            self._score_css = css
            self.score_label.setStyleSheet(css)

    def _update_stats(self, current: float, stats: dict | None) -> None:
        color = _score_color(current, self._theme_preference).name()
        _set_text(self.score_label, f"{current:.0f}")
        self._set_score_css(f"color: {color};")
        _set_text(self.grade_label, score_grade(current))
        if stats and stats.get("count", 0) > 0:
            parts = [
                self.tr("Session {0}").format(
                    _format_duration(stats.get("duration_s", 0.0))
                ),
                self.tr("avg {0:.0f}").format(stats["avg"]),
            ]
            best = stats.get("best_streak_s", 0.0)
            if best >= 5:
                parts.append(self.tr("best streak {0}").format(_format_duration(best)))
            _set_text(self.session_label, "  ·  ".join(parts))
        else:
            _set_text(self.session_label, self.tr("Session —"))

    def set_tracking_state(self, state: str, detail: str | None = None) -> None:
        """Keep dashboard status, stale values, and video overlay in sync."""
        if state == self._tracking_state and detail is None:
            return
        self._tracking_state = state
        messages = {
            "starting": self.tr("Starting camera…"),
            "finding": self.tr("Finding you in frame…"),
            "tracking": self.tr("Tracking posture"),
            "paused": self.tr("Paused — step back into frame"),
            "scheduled": self.tr("Waiting for the next scheduled scan"),
            "camera_error": self.tr("Camera unavailable — check Settings"),
        }
        message = detail or messages.get(state, self.tr("Tracking paused"))
        self.subtitle.setText(message)
        active = state == "tracking"
        self.video_overlay.setVisible(not active)
        self.video_overlay.setText(message)
        self._breakdown.setEnabled(active)
        self.session_label.setEnabled(active)
        if not active:
            muted = theme_colors(self._theme_preference).muted
            self._set_score_css(f"color: {muted};")

    def _update_feedback_text(
        self, score: float, metrics: dict[str, float] | None
    ) -> None:
        good = self._is_good(score)
        if self.feedback_label.property("warn") != (not good):
            self.feedback_label.setProperty("warn", not good)
            self.feedback_label.style().unpolish(self.feedback_label)
            self.feedback_label.style().polish(self.feedback_label)
        if good:
            message = self.tr(
                "Nice alignment! Keep a relaxed breath and soft shoulders."
            )
        else:
            cues = [
                self.tr(_COMPONENTS_BY_KEY[key].cue)
                for key in self._flagged_components(metrics)
            ]
            if not cues:
                cues.append(
                    self.tr(
                        "Reset by rolling your shoulders back and opening your chest."
                    )
                )
            message = " ".join(cues[:2])
        _set_text(self.feedback_label, message)
