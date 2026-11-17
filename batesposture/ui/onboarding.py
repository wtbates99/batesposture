from __future__ import annotations

import time
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from ..ml.mediapipe_compat import PoseLandmark
from ..ml.pose_detector import PoseDetector
from ..services.camera_service import CameraService
from ..services.settings_service import (
    CALIBRATION_DURATION_SECONDS,
    SettingsService,
)
from .dashboard import VideoView
from .theme import theme_colors, wizard_stylesheet


@dataclass
class CalibrationResult:
    posture_score: float
    neck_angle: float
    shoulder_delta: float
    sample_count: int = 0


# Landmarks this close to the edge are usually extrapolated, not seen.
_FRAME_MARGIN = 0.03


def framing_hint(points) -> str:
    """Return what to fix so the head and shoulders are measurable, or ""."""
    if points is None:
        return QApplication.translate(
            "Onboarding", "Looking for you — face the camera in good light"
        )
    shoulders = points[[PoseLandmark.LEFT_SHOULDER, PoseLandmark.RIGHT_SHOULDER], :2]
    ears = points[[PoseLandmark.LEFT_EAR, PoseLandmark.RIGHT_EAR], :2]
    if (shoulders < _FRAME_MARGIN).any() or (shoulders > 1 - _FRAME_MARGIN).any():
        return QApplication.translate(
            "Onboarding", "Move back so both shoulders are in view"
        )
    if (ears[:, 1] < _FRAME_MARGIN).any():
        return QApplication.translate(
            "Onboarding", "Tilt the camera down so your whole head is in view"
        )
    return ""


class CameraPreviewWidget(VideoView):
    """Live camera preview with the detected skeleton and a framing hint.

    Frames and pose detection run on CameraService's thread, not here.
    ``framing_changed`` carries ``framing_hint`` text ("" when well framed).
    """

    camera_failed = pyqtSignal()
    framing_changed = pyqtSignal(str)
    sampled = pyqtSignal(object)  # PoseDetectionResult or None, per new frame

    def __init__(
        self, settings: SettingsService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent, auto_frame=False)
        self.setObjectName("cameraPreview")
        self._settings = settings
        self._message = self.tr("Camera preview will appear here")
        self._camera = CameraService(settings)
        self._camera.set_background(False)
        self._detector: PoseDetector | None = None
        self._last_seq = 0
        self._hint: str | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self.camera_failed.connect(self._show_camera_failed)

    def start(self) -> None:
        self.stop()
        self._set_message(self.tr("Starting camera…"))
        self._camera.start(self._detect, on_failed=self.camera_failed.emit)
        self._timer.start(40)

    def _detect(self, frame):
        # Runs on the camera thread; loading the model there keeps start() instant.
        if self._detector is None:
            self._detector = PoseDetector(self._settings)
        return self._detector.process_frame(frame)

    def _show_camera_failed(self) -> None:
        self._timer.stop()
        self._set_message(self.tr("Unable to open camera"))

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        self._camera.stop()
        self._hint = None
        self._set_message("")

    def _set_message(self, message: str) -> None:
        self._message = message
        self._image = None
        self._frame = None
        self.update()

    def _update_frame(self) -> None:
        seq, frame, _, result = self._camera.get_latest()
        if frame is None or seq == self._last_seq:
            return
        self._last_seq = seq
        self.show_frame(frame, getattr(result, "points", None))
        self.sampled.emit(result)

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    def show_frame(self, frame, points=None) -> None:
        """Show a BGR frame and the pose detected in it."""
        self.set_frame(frame, points)
        hint = framing_hint(points)
        if hint != self._hint:
            self._hint = hint
            self.framing_changed.emit(hint)

    def paintEvent(self, event):  # noqa: N802 - Qt override
        super().paintEvent(event)
        if self._image is None and self._message:
            painter = QPainter(self)
            painter.setPen(QColor(255, 255, 255, 170))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)


class WelcomePage(QWizardPage):
    """Opening wizard page — introduces the three-step onboarding flow."""

    def __init__(self, icon_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Welcome"))
        self.setSubTitle(
            self.tr("A short calibration personalizes your posture score.")
        )

        brand_icon = QLabel()
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            brand_icon.setPixmap(
                pixmap.scaled(
                    56,
                    56,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        brand_name = QLabel("BatesPosture")
        brand_name.setObjectName("brandName")
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_row.addWidget(brand_icon)
        brand_row.addWidget(brand_name)
        brand_row.addStretch()

        hero = QLabel(
            self.tr(
                "Sit naturally while BatesPosture learns your neutral alignment. Your camera stays local to this device."
            )
        )
        hero.setObjectName("heroText")
        hero.setWordWrap(True)

        tips = QLabel(
            self.tr(
                "1. Use a well-lit space\n"
                "2. Position the camera near eye level\n"
                "3. Keep your head and shoulders in frame"
            )
        )
        tips.setObjectName("supportText")
        tips.setWordWrap(True)

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.addLayout(brand_row)
        layout.addSpacing(8)
        layout.addWidget(hero)
        layout.addWidget(tips)
        layout.addStretch(1)
        self.setLayout(layout)


class CameraSetupPage(QWizardPage):
    """Wizard page showing a live camera preview for framing guidance.

    Starts CameraPreviewWidget when the page is entered and stops it on exit
    to release the capture handle before the calibration page opens the camera.
    """

    def __init__(
        self, settings: SettingsService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setTitle(self.tr("Align your camera"))
        self.setSubTitle(
            self.tr("Center yourself and ensure your upper body is in frame.")
        )

        self.preview = CameraPreviewWidget(settings)
        self.preview.setMinimumHeight(240)

        guidance = QLabel(
            self.tr(
                "Adjust your seating so your head and shoulders are visible. Use natural lighting when possible."
            )
        )
        guidance.setObjectName("supportText")
        guidance.setWordWrap(True)

        self.framing_label = QLabel("")
        self.framing_label.setObjectName("framingStatus")
        self.framing_label.setWordWrap(True)
        self.preview.framing_changed.connect(self._show_framing)

        layout = QVBoxLayout()
        layout.addWidget(self.preview)
        layout.addSpacing(8)
        layout.addWidget(self.framing_label)
        layout.addWidget(guidance)
        layout.addStretch(1)
        self.setLayout(layout)

    def initializePage(self) -> None:  # noqa: N802 - Qt override
        self.preview.start()

    def cleanupPage(self) -> None:  # noqa: N802 - Qt override
        self.preview.stop()

    def stop_preview(self) -> None:
        """Ensures the preview capture is released when leaving the page."""
        self.preview.stop()

    def _show_framing(self, hint: str) -> None:
        self.framing_label.setText(
            hint or self.tr("✓ Head and shoulders in view — looks good")
        )
        self.framing_label.setProperty("warn", bool(hint))
        self.framing_label.style().polish(self.framing_label)


class CalibrationPage(QWizardPage):
    """Wizard page that captures a 6-second neutral-posture baseline.

    Samples come from the live preview, which already runs pose detection, so
    starting is instant and the camera is never reopened. Only well-framed
    samples count. The page is "complete" (Next/Finish enabled) once a
    CalibrationResult has been captured.
    """

    def __init__(
        self,
        settings: SettingsService,
        parent: QWidget | None = None,
        duration_seconds: int = CALIBRATION_DURATION_SECONDS,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._duration = duration_seconds
        self.setTitle(self.tr("Capture your baseline"))
        self.setSubTitle(
            self.tr(
                "We'll measure a short sample so posture insights match your neutral stance."
            )
        )

        self.preview = CameraPreviewWidget(settings)
        self.preview.setMinimumHeight(260)

        self.status_label = QLabel(
            self.tr(
                'When you\'re ready, sit comfortably and press "Start calibration".'
            )
        )
        self.status_label.setObjectName("supportText")
        self.status_label.setWordWrap(True)

        self.results_label = QLabel("")
        self.results_label.setObjectName("resultPanel")
        self.results_label.setWordWrap(True)
        self.results_label.setVisible(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)

        self.start_button = QPushButton(self.tr("Start calibration"))
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._begin_calibration)
        self.preview.framing_changed.connect(self._show_framing)
        self.preview.sampled.connect(self._add_sample)
        self.preview.camera_failed.connect(self._handle_camera_failed)

        layout = QVBoxLayout()
        layout.addWidget(self.preview)
        layout.addSpacing(8)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addSpacing(12)
        layout.addWidget(self.start_button)
        layout.addSpacing(12)
        layout.addWidget(self.results_label)
        layout.addStretch(1)
        self.setLayout(layout)

        self._metrics: CalibrationResult | None = None
        self._samples: list[dict[str, float]] | None = None  # None when idle
        self._started_at = 0.0
        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self._finish_calibration)

    def initializePage(self) -> None:  # noqa: N802 - Qt override
        self.preview.start()

    def cleanupPage(self) -> None:  # noqa: N802 - Qt override
        self.stop()

    @property
    def calibrating(self) -> bool:
        return self._samples is not None

    def _show_framing(self, hint: str) -> None:
        """Before calibrating, only allow starting once the person is framed."""
        if self.calibrating:
            return
        self.start_button.setEnabled(not hint)
        if self._metrics is None:
            self.status_label.setText(
                hint
                or self.tr(
                    "Looking good. Sit the way you normally do when you're "
                    'comfortable and upright, then press "Start calibration".'
                )
            )

    def _begin_calibration(self) -> None:
        if self.calibrating:
            return
        if not self.preview.is_running:  # the camera failed earlier; retry it
            self.preview.start()
        self._metrics = None
        self.completeChanged.emit()
        self._samples = []
        self._started_at = time.monotonic()
        self._finish_timer.start(self._duration * 1000)
        self.start_button.setEnabled(False)
        self.start_button.setText(self.tr("Calibrating…"))
        self.results_label.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self._update_progress(0, self._duration, self.tr("Hold still"))

    def _add_sample(self, result) -> None:
        if self._samples is None:
            return
        elapsed = time.monotonic() - self._started_at
        # Only well-framed samples count: a cut-off shoulder skews the baseline
        hint = framing_hint(getattr(result, "points", None))
        if not hint:
            self._samples.append(result.metrics)
        self._update_progress(
            min(99, int(elapsed / self._duration * 100)),
            max(0, self._duration - int(elapsed)),
            hint,
        )

    def _update_progress(self, percent: int, remaining_seconds: int, hint: str) -> None:
        self.progress_bar.setValue(percent)
        detection = hint or self.tr("Hold still")
        self.status_label.setText(
            self.tr("Calibrating · {remaining}s remaining · {detection}").format(
                remaining=remaining_seconds,
                detection=detection,
            )
        )

    def _finish_calibration(self) -> None:
        samples, self._samples = self._samples or [], None
        if not samples:
            self._handle_failure(self.tr("No posture data captured"))
            return

        def _mean(key: str) -> float:
            return float(sum(m.get(key, 0.0) for m in samples) / len(samples))

        self._handle_success(
            CalibrationResult(
                posture_score=_mean("posture_score"),
                neck_angle=_mean("neck_angle"),
                shoulder_delta=_mean("shoulder_vertical_delta"),
                sample_count=len(samples),
            )
        )

    def _handle_camera_failed(self) -> None:
        if self.calibrating:
            self._finish_timer.stop()
            self._samples = None
            self._handle_failure(self.tr("Unable to access camera"))
        else:
            self.start_button.setEnabled(True)

    def _handle_success(self, result: CalibrationResult) -> None:
        self._metrics = result
        self.start_button.setEnabled(True)
        self.start_button.setText(self.tr("Calibrate again"))
        self.progress_bar.setValue(100)
        self.status_label.setText(self.tr("Baseline captured — you're ready to go."))
        quality = self.tr("Good") if result.sample_count >= 20 else self.tr("Limited")
        self.results_label.setText(
            self.tr(
                "Baseline score: {score:.0f}%\n"
                "Calibration quality: {quality} · {samples} samples"
            ).format(
                score=result.posture_score,
                quality=quality,
                samples=result.sample_count,
            )
        )
        self.results_label.setVisible(True)
        self.completeChanged.emit()

    def _handle_failure(self, message: str) -> None:
        self.start_button.setEnabled(True)
        self.start_button.setText(self.tr("Try calibration again"))
        self.progress_bar.setVisible(False)
        self.status_label.setText(self.tr("Calibration couldn't be completed."))
        self.results_label.setText(
            self.tr(
                "{message}\n\nCheck your framing and lighting, then try again."
            ).format(message=message)
        )
        self.results_label.setVisible(True)

    def isComplete(self) -> bool:  # noqa: N802 - Qt override
        return self._metrics is not None

    def metrics(self) -> CalibrationResult | None:
        return self._metrics

    def stop(self) -> None:
        self._finish_timer.stop()
        self._samples = None
        self.preview.stop()


class OnboardingWizard(QWizard):
    def __init__(
        self, settings_service: SettingsService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings_service
        self.setWindowTitle(self.tr("BatesPosture Setup"))
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(560, 600)
        self.resize(620, 680)

        self.welcome_page = WelcomePage(settings_service.resources.icon_path)
        self.camera_page = CameraSetupPage(settings_service)
        self.calibration_page = CalibrationPage(settings_service)

        self._welcome_page_id = self.addPage(self.welcome_page)
        self._camera_page_id = self.addPage(self.camera_page)
        self._calibration_page_id = self.addPage(self.calibration_page)
        self._last_page_id = self.currentId()
        self.currentIdChanged.connect(self._handle_page_change)

        self.button(QWizard.WizardButton.NextButton).setObjectName("primaryButton")
        self.button(QWizard.WizardButton.FinishButton).setObjectName("primaryButton")
        self.button(QWizard.WizardButton.FinishButton).setText(
            self.tr("Finish & start tracking")
        )
        theme = settings_service.profile.preferred_theme
        self.setStyleSheet(wizard_stylesheet(theme))
        self._header_color = QColor(theme_colors(theme).canvas)

    def showEvent(self, event):  # noqa: N802 - Qt override
        super().showEvent(event)
        self._theme_header()

    def _theme_header(self) -> None:
        """Paint the page-title header in the theme colour.

        The header is a private plain QWidget, created lazily, that fills with
        the Base colour. Neither the stylesheet nor the wizard's palette reaches
        it, so it stays white in dark mode unless recoloured directly.
        """
        color = self._header_color
        for widget in self.findChildren(QWidget):
            if (
                type(widget) is QWidget
                and widget.autoFillBackground()
                and widget.backgroundRole() == QPalette.ColorRole.Base
            ):
                palette = widget.palette()
                palette.setColor(QPalette.ColorRole.Base, color)
                widget.setPalette(palette)

    def accept(self) -> None:
        metrics = self.calibration_page.metrics()
        if metrics:
            self._settings.update_profile(
                has_completed_onboarding=True,
                baseline_posture_score=metrics.posture_score,
                baseline_neck_angle=metrics.neck_angle,
                baseline_shoulder_level=metrics.shoulder_delta,
            )
        self._stop_camera_activity()
        super().accept()

    def reject(self) -> None:
        self._stop_camera_activity()
        super().reject()

    def _stop_camera_activity(self) -> None:
        self.camera_page.stop_preview()
        self.calibration_page.stop()

    def _handle_page_change(self, page_id: int) -> None:
        if self._last_page_id == self._camera_page_id and self.camera_page is not None:
            self.camera_page.stop_preview()
        self._last_page_id = page_id
        self._theme_header()


def run_onboarding_if_needed(
    settings_service: SettingsService,
    parent: QWidget | None = None,
    force: bool = False,
) -> bool:
    if settings_service.profile.has_completed_onboarding and not force:
        return False
    wizard = OnboardingWizard(settings_service, parent)
    return wizard.exec() == QDialog.DialogCode.Accepted
