from __future__ import annotations

import json
from typing import Dict, Iterable, Mapping, Optional
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QDialog, QStyle

from data.database import Database
from ml.pose_detector import PoseDetectionResult, PoseDetector
from services.camera_service import CameraService
from services.notification_service import NotificationService
from services.score_service import ScoreService
from services.settings_service import SettingsService, _default_tracking_intervals
from services.task_scheduler import TaskScheduler
from ui.dashboard import PostureDashboard
from ui.onboarding import run_onboarding_if_needed
from ui.settings_dialog import SettingsDialog
from util__create_score_icon import create_score_icon


class PostureTrackerTray(QSystemTrayIcon):
    def __init__(
        self,
        settings: SettingsService,
        detector: PoseDetector,
        camera_service: CameraService,
        score_service: ScoreService,
        notification_service: NotificationService,
        scheduler: TaskScheduler,
        database: Optional[Database] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._detector = detector
        self._camera_service = camera_service
        self._scores = score_service
        self._notifications = notification_service
        self._scheduler = scheduler
        self._database = database

        self.tracking_enabled = False
        self.video_window: Optional[PostureDashboard] = None
        self.tracking_interval = 0
        self.last_tracking_time: Optional[datetime] = None
        self.last_db_save: Optional[datetime] = None

        self._initialize_application()
        self._run_onboarding_if_needed()
        self._setup_tray_menu()
        self._scheduler.schedule("frame", 100, self._update_tracking)
        self._scheduler.schedule("interval", 1000, self._check_interval)
        self._setup_signal_handling()

    def _initialize_application(self) -> None:
        app = QApplication.instance()
        app.setApplicationName("Posture Corrector")
        icon_path = self._settings.resources.icon_path
        self.icon_path = icon_path
        icon = QIcon(icon_path)
        app.setWindowIcon(icon)
        self.setIcon(icon)

    def _run_onboarding_if_needed(self) -> None:
        if run_onboarding_if_needed(self._settings):
            self._settings.save_all()

    def _setup_tray_menu(self) -> None:
        menu = QMenu()
        style = QApplication.style()

        self.toggle_tracking_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
            "Start Tracking",
            self,
        )
        self.toggle_tracking_action.setShortcut("Ctrl+Shift+T")
        self.toggle_tracking_action.triggered.connect(self.toggle_tracking)
        self.toggle_tracking_action.setShortcutVisibleInContextMenu(True)

        self.toggle_dashboard_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DesktopIcon),
            "Show Dashboard",
            self,
        )
        self.toggle_dashboard_action.setShortcut("Ctrl+Shift+D")
        self.toggle_dashboard_action.setShortcutVisibleInContextMenu(True)
        self.toggle_dashboard_action.triggered.connect(self.toggle_dashboard)
        self.toggle_dashboard_action.setEnabled(False)

        menu.addSection("Session")
        menu.addAction(self.toggle_tracking_action)
        menu.addAction(self.toggle_dashboard_action)

        self.interval_menu = self._create_interval_menu(menu)
        self.interval_menu.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.interval_menu_action = menu.addMenu(self.interval_menu)

        runtime = self._settings.runtime
        menu.addSection("Quick toggles")
        self.notifications_toggle_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
            "Notifications",
            self,
            checkable=True,
        )
        self.notifications_toggle_action.setChecked(runtime.notifications_enabled)
        self.notifications_toggle_action.triggered.connect(self._toggle_notifications)
        self._set_notification_label(runtime.notifications_enabled)

        self.logging_toggle_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon),
            "Database Logging",
            self,
            checkable=True,
        )
        self.logging_toggle_action.setChecked(runtime.enable_database_logging)
        self.logging_toggle_action.triggered.connect(self._toggle_logging)
        self._set_logging_label(runtime.enable_database_logging)

        self.focus_mode_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogNoButton),
            "Focus Mode",
            self,
            checkable=True,
        )
        self.focus_mode_action.setChecked(runtime.focus_mode_enabled)
        self.focus_mode_action.triggered.connect(self._toggle_focus_mode)
        self._set_focus_label(runtime.focus_mode_enabled)

        menu.addAction(self.notifications_toggle_action)
        menu.addAction(self.logging_toggle_action)
        menu.addAction(self.focus_mode_action)

        menu.addSeparator()

        self.settings_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "Settings",
            menu,
        )
        self.settings_action.setShortcut("Ctrl+,")
        self.settings_action.setShortcutVisibleInContextMenu(True)
        self.settings_action.triggered.connect(self.open_settings)
        menu.addAction(self.settings_action)

        menu.addSeparator()
        quit_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton),
            "Quit",
            menu,
            triggered=self.quit_application,
        )
        quit_action.setShortcut("Ctrl+Q")
        quit_action.setShortcutVisibleInContextMenu(True)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.setVisible(True)

    def _create_interval_menu(self, parent_menu: QMenu) -> QMenu:
        interval_menu = QMenu("Tracking Interval", parent_menu)
        interval_group = QActionGroup(interval_menu)
        interval_group.setExclusive(True)

        intervals = self._normalize_tracking_intervals(
            self._settings.runtime.tracking_intervals
        )
        for label, minutes in intervals.items():
            action = QAction(label, interval_menu, checkable=True)
            action.setData(minutes)
            action.triggered.connect(lambda checked, m=minutes: self.set_interval(m))
            interval_menu.addAction(action)
            interval_group.addAction(action)
            if minutes == 0:
                action.setChecked(True)
        return interval_menu

    def _normalize_tracking_intervals(self, raw_intervals: object) -> Dict[str, int]:
        normalized = self._coerce_interval_mapping(raw_intervals)
        if not normalized:
            normalized = dict(_default_tracking_intervals())

        if normalized != raw_intervals:
            self._settings.runtime.tracking_intervals = dict(normalized)
            try:
                self._settings.save_all()
            except Exception:
                pass
        return normalized

    def _coerce_interval_mapping(self, raw: object) -> Dict[str, int]:
        if isinstance(raw, Mapping):
            result: Dict[str, int] = {}
            for label, value in raw.items():
                minutes = self._coerce_interval_minutes(value)
                if minutes is None:
                    continue
                result[str(label).strip()] = minutes
            return result

        if isinstance(raw, str):
            parsed = self._parse_interval_string(raw)
            if parsed:
                return parsed
            return {}

        if isinstance(raw, Iterable):
            result: Dict[str, int] = {}
            for item in raw:
                if isinstance(item, Mapping):
                    result.update(self._coerce_interval_mapping(item))
                    continue
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    label = str(item[0]).strip()
                    minutes = self._coerce_interval_minutes(item[1])
                    if minutes is not None:
                        result[label] = minutes
            return result

        return {}

    def _parse_interval_string(self, payload: str) -> Dict[str, int]:
        payload = payload.strip()
        if not payload:
            return {}
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            result: Dict[str, int] = {}
            fragments = [frag for frag in payload.split(",") if frag.strip()]
            for fragment in fragments:
                separator = ":" if ":" in fragment else "="
                if separator not in fragment:
                    continue
                label_part, minutes_part = fragment.split(separator, 1)
                label = label_part.strip().strip("\"'")
                minutes = self._coerce_interval_minutes(minutes_part)
                if minutes is not None:
                    result[label] = minutes
            return result
        else:
            return self._coerce_interval_mapping(decoded)

    def _coerce_interval_minutes(self, value: object) -> Optional[int]:
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            return None
        return minutes

    def _setup_signal_handling(self) -> None:
        import signal

        signal.signal(signal.SIGINT, self._signal_handler)

    # ------------------------
    # Tracking lifecycle
    # ------------------------
    def toggle_tracking(self) -> None:
        if not self.tracking_enabled:
            self._start_tracking()
        else:
            self._stop_tracking()

    def _start_tracking(self) -> None:
        started = self._camera_service.start(self._detector.process_frame)
        if not started:
            return
        self.tracking_enabled = True
        self.toggle_tracking_action.setText("Stop Tracking")
        self.toggle_dashboard_action.setEnabled(True)
        self.setIcon(create_score_icon(0))

    def _stop_tracking(self) -> None:
        self._camera_service.stop()
        self.tracking_enabled = False
        self.toggle_tracking_action.setText("Start Tracking")
        self.toggle_dashboard_action.setEnabled(False)
        self.toggle_dashboard_action.setText("Show Dashboard")
        if self.video_window:
            self.video_window.close()
            self.video_window = None
        self.setIcon(QIcon(self.icon_path))

    def toggle_dashboard(self) -> None:
        if self.video_window:
            self.video_window.close()
            self.video_window = None
            self.toggle_dashboard_action.setText("Show Dashboard")
        else:
            profile = self._settings.profile
            self.video_window = PostureDashboard(
                baseline_score=profile.baseline_posture_score,
                preferred_theme=profile.preferred_theme,
            )
            self.video_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self.video_window.destroyed.connect(self._on_dashboard_closed)
            self.video_window.resize(720, 520)
            self.video_window.show()
            self.toggle_dashboard_action.setText("Hide Dashboard")

    def _on_dashboard_closed(self) -> None:
        self.video_window = None
        self.toggle_dashboard_action.setText("Show Dashboard")

    def _update_tracking(self) -> None:
        if not self.tracking_enabled:
            return
        frame, score = self._camera_service.get_latest_frame()
        if frame is None:
            return
        self._scores.add_score(score)
        average_score = self._scores.average()
        self.setIcon(create_score_icon(average_score))

        results_bundle = self._camera_service.get_latest_pose_results()
        metrics: Optional[Dict[str, float]] = None
        if isinstance(results_bundle, PoseDetectionResult):
            metrics = results_bundle.metrics

        if self._database and self._settings.runtime.enable_database_logging:
            self._save_to_db(average_score, results_bundle)

        self._notifications.maybe_notify_posture(average_score)

        if isinstance(self.video_window, PostureDashboard):
            self.video_window.update_frame(frame)
            self.video_window.update_score(average_score, metrics)

    # ------------------------
    # Interval Scheduling
    # ------------------------
    def set_interval(self, minutes: int) -> None:
        self.tracking_interval = minutes
        if minutes > 0:
            self._notifications.notify_interval_change(
                f"Checking posture every {minutes} minutes"
            )
        self.last_tracking_time = None if minutes > 0 else self.last_tracking_time
        if minutes == 0 and not self.tracking_enabled:
            self.toggle_tracking()
        elif minutes > 0 and self.tracking_enabled:
            self.toggle_tracking()

    def _check_interval(self) -> None:
        if self.tracking_interval <= 0:
            return
        current_time = datetime.now()
        if not self.last_tracking_time:
            self.last_tracking_time = current_time
            self._start_interval_tracking()
        elif current_time - self.last_tracking_time >= timedelta(
            minutes=self.tracking_interval
        ):
            self._start_interval_tracking()

    def _start_interval_tracking(self) -> None:
        self.last_tracking_time = datetime.now()
        self.last_db_save = None
        if not self.tracking_enabled:
            self.toggle_tracking()
        duration_minutes = self._settings.runtime.tracking_duration_minutes
        self._scheduler.single_shot(
            duration_minutes * 60 * 1000, self._stop_interval_tracking
        )

    def _stop_interval_tracking(self) -> None:
        if self.tracking_enabled and self.tracking_interval > 0:
            self.toggle_tracking()

    # ------------------------
    # Persistence
    # ------------------------
    def _save_to_db(
        self,
        average_score: float,
        results_bundle: Optional[PoseDetectionResult],
    ) -> None:
        if not self._database:
            return
        current_time = datetime.now()
        db_interval_seconds = self._settings.runtime.db_write_interval_seconds

        should_save = (
            self.tracking_interval > 0
            and self.last_tracking_time
            and self.last_db_save is None
            and (current_time - self.last_tracking_time).total_seconds()
            <= db_interval_seconds
        ) or (
            self.tracking_interval == 0
            and (
                self.last_db_save is None
                or (current_time - self.last_db_save).total_seconds()
                >= db_interval_seconds
            )
        )

        if not should_save or not results_bundle:
            return
        pose_results = results_bundle.pose_landmarks
        if pose_results:
            self._database.save_pose_data(pose_results, average_score)
            self.last_db_save = current_time

    # ------------------------
    # Menu callbacks
    # ------------------------
    def _toggle_notifications(self, checked: bool) -> None:
        self._settings.update_runtime(notifications_enabled=checked)
        self._settings.save_all()
        self._set_notification_label(checked)

    def _toggle_logging(self, checked: bool) -> None:
        self._settings.update_runtime(enable_database_logging=checked)
        self._settings.save_all()
        self._set_logging_label(checked)
        if checked and self._database is None:
            self._database = Database(
                self._settings.resources.default_db_name,
                self._settings.get_posture_landmarks(),
            )
        elif not checked and self._database:
            self._database.close()
            self._database = None

    def _toggle_focus_mode(self, checked: bool) -> None:
        self._settings.update_runtime(focus_mode_enabled=checked)
        self._settings.save_all()
        self._set_focus_label(checked)

    def _set_notification_label(self, enabled: bool) -> None:
        label = "Notifications (On)" if enabled else "Notifications (Off)"
        self.notifications_toggle_action.setText(label)

    def _set_logging_label(self, enabled: bool) -> None:
        label = "Database Logging (On)" if enabled else "Database Logging (Off)"
        self.logging_toggle_action.setText(label)

    def _set_focus_label(self, enabled: bool) -> None:
        label = "Focus Mode (On)" if enabled else "Focus Mode (Off)"
        self.focus_mode_action.setText(label)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self._settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:  # type: ignore
            self._refresh_after_settings_change()

    def _refresh_after_settings_change(self) -> None:
        runtime = self._settings.runtime
        self._set_notification_label(runtime.notifications_enabled)
        self.notifications_toggle_action.setChecked(runtime.notifications_enabled)
        self._set_logging_label(runtime.enable_database_logging)
        self.logging_toggle_action.setChecked(runtime.enable_database_logging)
        self._set_focus_label(runtime.focus_mode_enabled)
        self.focus_mode_action.setChecked(runtime.focus_mode_enabled)

        menu = self.contextMenu()
        if menu:
            menu.removeAction(self.interval_menu_action)
            self.interval_menu = self._create_interval_menu(menu)
            self.interval_menu_action = menu.insertMenu(
                self.toggle_tracking_action, self.interval_menu
            )

        self._camera_service.reload_settings()
        self._scores.reload(self._settings)

    # ------------------------
    # Shutdown
    # ------------------------
    def quit_application(self) -> None:
        if self.tracking_enabled:
            self.toggle_tracking()
        if self.video_window:
            self.video_window.close()
            self.video_window = None
        self._scheduler.shutdown()
        if self._database:
            self._database.close()
        self.hide()
        QApplication.instance().quit()

    def _signal_handler(self, signum, frame):  # noqa: D401, N803
        self.quit_application()
