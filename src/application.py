from __future__ import annotations

import logging
import os
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


def _is_low_end_hardware() -> bool:
    """Return True if the machine has limited CPU resources."""
    cpu_count = os.cpu_count() or 4
    try:
        import psutil

        ram_gb = psutil.virtual_memory().total / (1024**3)
        return cpu_count <= 4 or ram_gb < 8
    except ImportError:
        return cpu_count <= 4


class ApplicationFacade:
    """Wires all services together and owns their lifetimes.

    Construction order matters:
    1. SettingsService — loaded first; adaptive resolution may mutate it before any
       other service reads frame_width / frame_height.
    2. PoseDetector — reads resolution from settings at init time.
    3. Remaining services (CameraService, ScoreService, NotificationService).
    4. Optional Database — only created when enable_database_logging is True.
    5. PostureTrackerTray — receives all services and starts the Qt event loop.
    """

    def __init__(self, app: QApplication) -> None:
        self._qt_app = app
        self.settings = SettingsService()
        self._maybe_apply_adaptive_resolution()
        self.scheduler = TaskScheduler()
        self.pose_detector = PoseDetector(self.settings)
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
        """Drop to 640×480 on low-end hardware when adaptive_resolution is enabled or the
        user has not overridden the default 1280×720 resolution."""
        runtime = self.settings.runtime
        if (
            runtime.adaptive_resolution
            and runtime.frame_width == 1280
            and runtime.frame_height == 720
        ):
            if _is_low_end_hardware():
                self.settings.update_runtime(frame_width=640, frame_height=480)
                logger.info(
                    "Adaptive resolution: switched to 640×480 on low-end hardware"
                )

    def run(self) -> int:
        self.tray.show()
        return self._qt_app.exec()
