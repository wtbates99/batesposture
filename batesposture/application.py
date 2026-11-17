from __future__ import annotations

import logging

from PyQt6.QtWidgets import QApplication, QMessageBox

from .data.database import Database, DatabaseInitializationError
from .ml.pose_detector import PoseDetector
from .services.camera_service import CameraService
from .services.notification_service import NotificationService
from .services.score_service import ScoreService
from .services.settings_service import SettingsService
from .services.task_scheduler import TaskScheduler
from .ui.tray import PostureTrackerTray

logger = logging.getLogger(__name__)


class ApplicationFacade:
    """Wires all services together and owns their lifetimes.

    Construction order matters:
    1. SettingsService — loaded first so all services read a consistent config.
    2. PoseDetector — initialised (and pre-warmed) before anything streams frames.
    3. Remaining services (CameraService, ScoreService, NotificationService).
    4. Optional Database — only created when enable_database_logging is True.
    5. PostureTrackerTray — receives all services and starts the Qt event loop.
    """

    def __init__(self, app: QApplication) -> None:
        self._qt_app = app
        self.settings = SettingsService()
        self.scheduler = TaskScheduler()
        self.pose_detector = PoseDetector(self.settings)
        self.camera_service = CameraService(self.settings)
        self.score_service = ScoreService(self.settings)
        self.notification_service = NotificationService(
            self.settings, self.settings.resources.icon_path
        )
        self.database: Database | None = None
        if self.settings.runtime.enable_database_logging:
            try:
                self.database = Database.from_settings(self.settings)
            except DatabaseInitializationError as exc:
                logger.exception("Database logging could not be started")
                self.settings.update_runtime(enable_database_logging=False)
                QMessageBox.warning(
                    None,
                    "Database logging unavailable",
                    "Posture tracking will continue without database logging.\n\n"
                    f"{exc}",
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

    def run(self) -> int:
        self.tray.show()
        return self._qt_app.exec()
