from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import QApplication

from data.database import Database
from ml.pose_detector import PoseDetector
from services.camera_service import CameraService
from services.notification_service import NotificationService
from services.score_service import ScoreService
from services.settings_service import SettingsService
from services.task_scheduler import TaskScheduler
from ui.tray import PostureTrackerTray

logger = logging.getLogger(__name__)


class ApplicationFacade:
    """Wires all services together and owns their lifetimes.

    Construction order matters:
    1. SettingsService — loaded first so all services read a consistent config.
    2. PoseDetector — initialised next; its pre-warm timing drives the adaptive
       resolution decision in step 3.
    3. Adaptive resolution check — may lower frame_width/height in settings and on
       the detector before CameraService or any other consumer reads them.
    4. Remaining services (CameraService, ScoreService, NotificationService).
    5. Optional Database — only created when enable_database_logging is True.
    6. PostureTrackerTray — receives all services and starts the Qt event loop.
    """

    def __init__(self, app: QApplication) -> None:
        self._qt_app = app
        self.settings = SettingsService()
        self.scheduler = TaskScheduler()
        self.pose_detector = PoseDetector(self.settings)
        self._maybe_apply_adaptive_resolution()
        self.camera_service = CameraService(self.settings)
        self.score_service = ScoreService(self.settings)
        self.notification_service = NotificationService(
            self.settings, self.settings.resources.icon_path
        )
        self.database: Optional[Database] = None
        if self.settings.runtime.enable_database_logging:
            self.database = Database(
                self.settings.resources.default_db_name,
                self.settings.get_posture_landmarks(),
            )

        self.tray = PostureTrackerTray(
            settings=self.settings,
            detector=self.pose_detector,
            camera_service=self.camera_service,
            score_service=self.score_service,
            notification_service=self.notification_service,
            scheduler=self.scheduler,
            database=self.database,
        )

    def _maybe_apply_adaptive_resolution(self) -> None:
        """Drop to 640×480 when adaptive_resolution is enabled and the MediaPipe pre-warm
        took longer than 100 ms — a reliable proxy for whether this hardware can sustain
        real-time inference at 1280×720.  Updates both the persisted settings and the
        already-constructed PoseDetector so it preprocesses at the lower resolution."""
        runtime = self.settings.runtime
        if not (
            runtime.adaptive_resolution
            and runtime.frame_width == 1280
            and runtime.frame_height == 720
        ):
            return
        prewarm_ms = self.pose_detector.prewarm_duration_ms
        if prewarm_ms <= 100.0:
            return
        self.settings.update_runtime(frame_width=640, frame_height=480)
        self.pose_detector.frame_width = 640
        self.pose_detector.frame_height = 480
        logger.info(
            "Adaptive resolution: switched to 640×480 (pre-warm %.0f ms)", prewarm_ms
        )

    def run(self) -> int:
        self.tray.show()
        return self._qt_app.exec()
