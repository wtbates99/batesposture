from datetime import datetime, timedelta
import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
)
from database import Database
from notifications import Notifications
from pose_detector import PoseDetector
from score_history import ScoreHistory
from webcam import Webcam
from settings import get_setting
from settings_interface import SettingsInterface
from util__create_score_icon import create_score_icon
import signal


class PostureTrackerTray(QSystemTrayIcon):
    def __init__(self):
        """Initialize the PostureTrackerTray system tray application."""
        super().__init__()
        self._initialize_application()
        self._initialize_components()
        self._setup_tray_menu()
        self._setup_timers()
        self._setup_signal_handling()

    def _initialize_application(self):
        """Set up the QApplication instance and basic properties."""
        app = QApplication.instance()
        app.setApplicationName("Posture Corrector")
        self.icon_path = get_setting("ICON_PATH")
        app.setWindowIcon(QIcon(self.icon_path))
        self.setIcon(QIcon(self.icon_path))

    def _initialize_components(self):
        """Initialize core components like webcam, detector, and managers."""
        self.frame_reader = Webcam()
        self.detector = PoseDetector()
        self.scores = ScoreHistory()
        self.notifier = Notifications(icon_path=self.icon_path)
        self.db = Database(get_setting("DEFAULT_DB_NAME"))
        self.db_enabled = get_setting("ENABLE_DATABASE_LOGGING")

        self.tracking_enabled = False
        self.video_window = None
        self.current_score = 0
        self.tracking_interval = 0
        self.last_tracking_time = None
        self.last_db_save = None

    def _setup_tray_menu(self):
        """Configure the system tray context menu."""
        menu = QMenu()

        self.toggle_tracking_action = QAction("Start Tracking")
        self.toggle_tracking_action.triggered.connect(self.toggle_tracking)

        self.toggle_video_action = QAction("Show Video")
        self.toggle_video_action.triggered.connect(self.toggle_video)
        self.toggle_video_action.setEnabled(False)

        # Store the interval menu and its action as instance variables
        self.interval_menu = self._create_interval_menu(menu)
        self.interval_menu_action = menu.addMenu(self.interval_menu)

        menu.addAction(self.toggle_tracking_action)
        menu.addAction(self.toggle_video_action)

        self.settings_action = QAction("Settings", menu)
        self.settings_action.triggered.connect(self.open_settings)
        menu.addAction(self.settings_action)

        menu.addSeparator()
        menu.addAction(
            QAction("Quit Application", menu, triggered=self.quit_application)
        )

        self.setContextMenu(menu)
        self.setVisible(True)

    def _create_interval_menu(self, parent_menu):
        """Create the tracking interval submenu."""
        interval_menu = QMenu("Tracking Interval", parent_menu)
        interval_group = QActionGroup(interval_menu)
        interval_group.setExclusive(True)

        tracking_intervals = get_setting("TRACKING_INTERVALS")
        for label, minutes in tracking_intervals.items():
            action = QAction(label, interval_menu, checkable=True)
            action.setData(minutes)
            action.triggered.connect(lambda checked, m=minutes: self.set_interval(m))
            interval_menu.addAction(action)
            interval_group.addAction(action)
            if minutes == 0:
                action.setChecked(True)

        return interval_menu

    def _setup_timers(self):
        """Initialize timers for tracking updates and interval checks."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tracking)
        self.timer.start(100)

        self.interval_timer = QTimer()
        self.interval_timer.timeout.connect(self.check_interval)
        self.interval_timer.start(1000)

    def _setup_signal_handling(self):
        """Configure signal handling for graceful shutdown."""
        signal.signal(signal.SIGINT, self.signal_handler)

    def toggle_tracking(self):
        """Toggle posture tracking on or off."""
        if not self.tracking_enabled:
            self._start_tracking()
        else:
            self._stop_tracking()

    def _start_tracking(self):
        """Begin tracking posture."""
        self.frame_reader.start(callback=self.detector.process_frame)
        self.tracking_enabled = True
        self.toggle_tracking_action.setText("Stop Tracking")
        self.toggle_video_action.setEnabled(True)
        self.setIcon(create_score_icon(0))

        if self.tracking_interval > 0:
            self.notifier.set_interval_message(
                f"Checking posture every {self.tracking_interval} minutes"
            )

    def _stop_tracking(self):
        """Stop tracking posture."""
        self.frame_reader.stop()
        self.tracking_enabled = False
        self.toggle_tracking_action.setText("Start Tracking")
        self.toggle_video_action.setEnabled(False)
        self.toggle_video_action.setText("Show Video")

        if self.video_window:
            self.video_window.close()
            self.video_window = None

        self.setIcon(QIcon(self.icon_path))

    def toggle_video(self):
        """Show or hide the video display window."""
        if self.video_window:
            self.video_window.close()
            self.video_window = None
            self.toggle_video_action.setText("Show Video")
        else:
            self._create_video_window()
            self.toggle_video_action.setText("Hide Video")

    def _create_video_window(self):
        """Create and display the video window."""
        self.video_window = QDialog()
        self.video_window.setWindowTitle("Posture Detection")
        self.video_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.video_label = QLabel("Waiting for first frame...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        self.video_window.setLayout(layout)

        self.video_window.destroyed.connect(self.on_video_window_closed)
        self.video_window.resize(640, 480)
        self.video_window.show()

    def update_tracking(self):
        """Process the latest frame and update tracking state."""
        if not self.tracking_enabled:
            return

        latest_frame = self.frame_reader.get_latest_frame()
        if not latest_frame or not latest_frame[0] is not None:
            return

        frame, score = latest_frame
        self.scores.add_score(score)
        average_score = self.scores.get_average_score()
        self.setIcon(create_score_icon(average_score))

        if self.db_enabled:
            self._save_to_db(average_score)

        self.notifier.check_and_notify(average_score)

        if self.video_window:
            self._update_video_display(frame)

    def _save_to_db(self, average_score):
        """Save pose data to the database if conditions are met."""
        current_time = datetime.now()
        db_interval_seconds = get_setting("DB_WRITE_INTERVAL_SECONDS")

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

        if (
            should_save
            and (results := self.frame_reader.get_latest_pose_results())
            and results.pose_landmarks
        ):
            self.db.save_pose_data(results.pose_landmarks, average_score)
            self.last_db_save = current_time

    def _update_video_display(self, frame):
        """Update the video window with the latest frame."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        q_img = QImage(
            rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
        )
        pixmap = QPixmap.fromImage(q_img)
        self.video_label.setPixmap(pixmap)

    def set_interval(self, minutes):
        """Set the tracking interval in minutes."""
        self.tracking_interval = minutes
        self.last_tracking_time = None if minutes > 0 else self.last_tracking_time
        if minutes == 0 and not self.tracking_enabled:
            self.toggle_tracking()
        elif minutes > 0 and self.tracking_enabled:
            self.toggle_tracking()

    def check_interval(self):
        """Check if it's time to start a new tracking interval."""
        if self.tracking_interval <= 0:
            return

        current_time = datetime.now()
        if not self.last_tracking_time:
            self.last_tracking_time = current_time
            self.start_interval_tracking()
        elif current_time - self.last_tracking_time >= timedelta(
            minutes=self.tracking_interval
        ):
            self.start_interval_tracking()

    def start_interval_tracking(self):
        self.last_tracking_time = datetime.now()
        self.last_db_save = None
        if not self.tracking_enabled:
            self.toggle_tracking()
        tracking_duration_minutes = get_setting("TRACKING_DURATION_MINUTES")
        QTimer.singleShot(
            tracking_duration_minutes * 60 * 1000, self.stop_interval_tracking
        )

    def stop_interval_tracking(self):
        """Stop tracking after the interval ends."""
        if self.tracking_enabled and self.tracking_interval > 0:
            self.toggle_tracking()

    def open_settings(self):
        """Open the settings dialog and reload settings if accepted."""
        if SettingsInterface().exec() == QDialog.DialogCode.Accepted:
            self.reload_settings()

    def reload_settings(self):
        """Reload settings and reinitialize components."""
        was_tracking = self.tracking_enabled
        previous_interval = self.tracking_interval

        if was_tracking:
            self.toggle_tracking()

        self.frame_reader = Webcam()
        self.db_enabled = get_setting("ENABLE_DATABASE_LOGGING")
        self.last_db_save = None if self.db_enabled else self.last_db_save

        menu = self.contextMenu()
        if menu:
            menu.removeAction(self.interval_menu_action)
            self.interval_menu = self._create_interval_menu(menu)
            self.interval_menu_action = menu.insertMenu(
                self.toggle_tracking_action, self.interval_menu
            )

        if was_tracking:
            self.toggle_tracking()

        if (
            was_tracking
            and previous_interval != self.tracking_interval
            and self.tracking_interval > 0
        ):
            self.notifier.set_interval_message(
                f"Checking posture every {self.tracking_interval} minutes"
            )

    def on_video_window_closed(self):
        """Handle video window closure."""
        self.video_window = None
        self.toggle_video_action.setText("Show Video")

    def quit_application(self):
        """Clean up resources and exit the application."""
        if self.tracking_enabled:
            self.toggle_tracking()

        if self.video_window:
            self.video_window.close()
            self.video_window = None

        self.timer.stop()
        self.interval_timer.stop()
        if hasattr(self, "db"):
            self.db.close()

        self.hide()
        QApplication.instance().quit()

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.quit_application()
