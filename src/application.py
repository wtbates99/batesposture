from __future__ import annotations

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


class ApplicationFacade:
    """Coordinates services and UI wiring for the posture application."""

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

    def run(self) -> int:
        self.tray.show()
        return self._qt_app.exec()
