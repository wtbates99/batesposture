from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Dict, Optional

import cv2
from PyQt6 import sip
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
    QMessageBox,
    QDialog,
)

from ml.pose_detector import PoseDetector
from services.settings_service import SettingsService


@dataclass
class CalibrationResult:
    posture_score: float
    neck_angle: float
    shoulder_delta: float


class CameraPreviewWidget(QLabel):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setText(self.tr("Camera preview will appear here"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_id = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self._capture: Optional[cv2.VideoCapture] = None

    def start(self, camera_id: int) -> None:
        self.stop()
        self._camera_id = camera_id
        capture = cv2.VideoCapture(self._camera_id)
        if not capture.isOpened() and sys.platform == "darwin":
            capture = cv2.VideoCapture(self._camera_id, cv2.CAP_AVFOUNDATION)
        if not capture or not capture.isOpened():
            self.setText(self.tr("Unable to open camera"))
            return
        self._capture = capture
        self._timer.start(40)

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        if self._capture:
            self._capture.release()
            self._capture = None
        self.clear()

    def _update_frame(self) -> None:
        if not self._capture:
            return
        ret, frame = self._capture.read()
        if not ret:
            self.setText(self.tr("Camera feed unavailable"))
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        image = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)

    def resizeEvent(self, event):  # noqa: N802 - Qt override
        super().resizeEvent(event)
        if self.pixmap():
            self.setPixmap(
                self.pixmap().scaled(
                    self.width(),
                    self.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )


class CalibrationWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, settings: SettingsService, duration_seconds: int = 6) -> None:
        super().__init__()
        self._settings = settings
        self._duration = duration_seconds
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    @property
    def duration(self) -> int:
        return self._duration

    @pyqtSlot()
    def run(self) -> None:
        capture = None
        try:
            camera_id = self._settings.runtime.default_camera_id
            capture = cv2.VideoCapture(camera_id)
            if not capture.isOpened() and sys.platform == "darwin":
                capture.release()
                capture = cv2.VideoCapture(camera_id, cv2.CAP_AVFOUNDATION)

            if not capture or not capture.isOpened():
                self.failed.emit(
                    QApplication.translate(
                        "CalibrationWorker", "Unable to access camera"
                    )
                )
                return

            detector = PoseDetector(self._settings)
            start_time = time.time()
            collected: Dict[str, list] = {
                "posture_score": [],
                "neck_angle": [],
                "shoulder_delta": [],
            }

            while not self._stop and time.time() - start_time < self._duration:
                ret, frame = capture.read()
                if not ret:
                    time.sleep(0.05)
                    continue
                _, score, result_bundle = detector.process_frame(frame)
                if not result_bundle:
                    time.sleep(0.05)
                    continue
                metrics = (
                    result_bundle.metrics if hasattr(result_bundle, "metrics") else {}
                )
                collected["posture_score"].append(metrics.get("posture_score", score))
                collected["neck_angle"].append(metrics.get("neck_angle", 0.0))
                collected["shoulder_delta"].append(
                    metrics.get("shoulder_vertical_delta", 0.0)
                )
                time.sleep(0.05)

        except Exception as exc:  # noqa: BLE001 - propagate error to UI
            self.failed.emit(str(exc))
            return
        finally:
            if capture:
                capture.release()

        if self._stop:
            self.failed.emit(
                QApplication.translate("CalibrationWorker", "Calibration cancelled")
            )
            return

        if not collected["posture_score"]:
            self.failed.emit(
                QApplication.translate("CalibrationWorker", "No posture data captured")
            )
            return

        result = CalibrationResult(
            posture_score=float(
                sum(collected["posture_score"]) / len(collected["posture_score"])
            ),
            neck_angle=float(
                sum(collected["neck_angle"]) / len(collected["neck_angle"])
            ),
            shoulder_delta=float(
                sum(collected["shoulder_delta"]) / len(collected["shoulder_delta"])
            ),
        )
        self.finished.emit(result)


class WelcomePage(QWizardPage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Welcome to Posture Coach"))
        self.setSubTitle(
            self.tr("We will calibrate your experience in three quick steps.")
        )

        hero = QLabel(
            self.tr(
                "Great posture starts with awareness. We'll help you dial in camera framing, learn posture cues, and capture your personal baseline so reminders feel tailored."
            )
        )
        hero.setWordWrap(True)
        hero_font = QFont()
        hero_font.setPointSize(hero_font.pointSize() + 2)
        hero_font.setBold(True)
        hero.setFont(hero_font)

        tips = QLabel(
            self.tr(
                "- Find a well-lit space\n"
                "- Position your camera at eye level\n"
                "- Sit naturally - no need to pose!"
            )
        )
        tips.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(hero)
        layout.addSpacing(12)
        layout.addWidget(tips)
        layout.addStretch(1)
        self.setLayout(layout)


class CameraSetupPage(QWizardPage):
    def __init__(
        self, settings: SettingsService, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setTitle(self.tr("Align your camera"))
        self.setSubTitle(
            self.tr("Center yourself and ensure your upper body is in frame.")
        )

        self.preview = CameraPreviewWidget()
        self.preview.setMinimumHeight(240)

        guidance = QLabel(
            self.tr(
                "Adjust your seating so your head and shoulders are visible. Use natural lighting when possible."
            )
        )
        guidance.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(self.preview)
        layout.addSpacing(8)
        layout.addWidget(guidance)
        layout.addStretch(1)
        self.setLayout(layout)

    def initializePage(self) -> None:  # noqa: N802 - Qt override
        self.preview.start(self._settings.runtime.default_camera_id)

    def cleanupPage(self) -> None:  # noqa: N802 - Qt override
        self.preview.stop()

    def stop_preview(self) -> None:
        """Ensures the preview capture is released when leaving the page."""
        self.preview.stop()


class CalibrationPage(QWizardPage):
    def __init__(
        self, settings: SettingsService, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setTitle(self.tr("Capture your baseline"))
        self.setSubTitle(
            self.tr(
                "We'll measure a short sample so posture insights match your neutral stance."
            )
        )

        self.status_label = QLabel(
            self.tr(
                'When you\'re ready, sit comfortably and press "Start calibration".'
            )
        )
        self.status_label.setWordWrap(True)

        self.results_label = QLabel("")
        self.results_label.setWordWrap(True)

        self.start_button = QPushButton(self.tr("Start calibration"))
        self.start_button.clicked.connect(self._begin_calibration)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addSpacing(12)
        layout.addWidget(self.start_button)
        layout.addSpacing(12)
        layout.addWidget(self.results_label)
        layout.addStretch(1)
        self.setLayout(layout)

        self._thread: Optional[QThread] = None
        self._worker: Optional[CalibrationWorker] = None
        self._metrics: Optional[CalibrationResult] = None
        self._timeout: Optional[QTimer] = None

    def _begin_calibration(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        self.start_button.setEnabled(False)
        self.status_label.setText(
            self.tr("Collecting data... Keep still for six seconds.")
        )

        worker = CalibrationWorker(self._settings)
        thread = QThread(self)
        worker.moveToThread(thread)

        worker.finished.connect(self._handle_success)
        worker.failed.connect(self._handle_failure)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.started.connect(worker.run)

        self._worker = worker
        self._thread = thread
        thread.start()

        if not self._timeout:
            self._timeout = QTimer(self)
            self._timeout.setSingleShot(True)
            self._timeout.timeout.connect(self._handle_timeout)
        self._timeout.start((worker.duration + 2) * 1000)

    def _handle_success(self, result: CalibrationResult) -> None:
        self._metrics = result
        self.start_button.setEnabled(True)
        self.status_label.setText(self.tr("Baseline captured."))
        self.results_label.setText(
            self.tr(
                "- Average posture score: {score:.1f}%\n"
                "- Neck angle: {neck:.1f} deg\n"
                "- Shoulder balance delta: {delta:.3f}"
            ).format(
                score=result.posture_score,
                neck=result.neck_angle,
                delta=result.shoulder_delta,
            )
        )
        self._cleanup_worker()
        self.completeChanged.emit()

    def _handle_failure(self, message: str) -> None:
        self.start_button.setEnabled(True)
        self.status_label.setText(self.tr("Calibration failed"))
        QMessageBox.warning(self, self.tr("Calibration"), message)
        self._cleanup_worker()

    def _handle_timeout(self) -> None:
        if self._worker:
            self._worker.cancel()
        else:
            self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        if self._timeout and self._timeout.isActive():
            self._timeout.stop()
        thread = self._thread
        worker = self._worker
        self._thread = None
        self._worker = None

        def _is_alive(obj: Optional[QObject]) -> bool:
            return obj is not None and not sip.isdeleted(obj)

        if _is_alive(thread):
            if thread.isRunning():
                thread.quit()
                thread.wait(2000)
            thread.deleteLater()
        if _is_alive(worker):
            worker.deleteLater()

    def isComplete(self) -> bool:  # noqa: N802 - Qt override
        return self._metrics is not None

    def metrics(self) -> Optional[CalibrationResult]:
        return self._metrics


class OnboardingWizard(QWizard):
    def __init__(
        self, settings_service: SettingsService, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings_service
        self.setWindowTitle(self.tr("Posture Coach Setup"))
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumWidth(500)

        self.welcome_page = WelcomePage()
        self.camera_page = CameraSetupPage(settings_service)
        self.calibration_page = CalibrationPage(settings_service)

        self._welcome_page_id = self.addPage(self.welcome_page)
        self._camera_page_id = self.addPage(self.camera_page)
        self._calibration_page_id = self.addPage(self.calibration_page)
        self._last_page_id = self.currentId()
        self.currentIdChanged.connect(self._handle_page_change)

        self._metrics: Optional[CalibrationResult] = None

    def accept(self) -> None:
        metrics = self.calibration_page.metrics()
        if metrics:
            self._settings.update_profile(
                has_completed_onboarding=True,
                baseline_posture_score=metrics.posture_score,
                baseline_neck_angle=metrics.neck_angle,
                baseline_shoulder_level=metrics.shoulder_delta,
            )
            self._settings.save_all()
            self._metrics = metrics
        super().accept()

    def collected_metrics(self) -> Optional[CalibrationResult]:
        return self._metrics

    def _handle_page_change(self, page_id: int) -> None:
        if self._last_page_id == self._camera_page_id and self.camera_page is not None:
            self.camera_page.stop_preview()
        self._last_page_id = page_id


def run_onboarding_if_needed(
    settings_service: SettingsService, parent: Optional[QWidget] = None
) -> bool:
    if settings_service.profile.has_completed_onboarding:
        return False
    wizard = OnboardingWizard(settings_service, parent)
    return wizard.exec() == QDialog.DialogCode.Accepted
