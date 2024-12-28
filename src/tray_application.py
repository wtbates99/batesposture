from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
)
from PyQt6.QtGui import QIcon, QAction, QImage, QPixmap, QActionGroup
from PyQt6.QtCore import QTimer
import cv2
from webcam import webcam
from pose_detector import pose_detector
from score_history import score_history
from notifications import notification_manager
import numpy as np
from datetime import datetime, timedelta


class PostureTrackerTray(QSystemTrayIcon):
    def __init__(self):
        super().__init__()

        self.frame_reader = webcam()
        self.detector = pose_detector()
        self.scores = score_history()
        self.notifier = notification_manager()

        self.tracking_enabled = False
        self.video_window = None
        self.current_score = 0
        self.tracking_interval = 0  # 0 means continuous tracking
        self.last_tracking_time = None
        self.interval_timer = QTimer()
        self.interval_timer.timeout.connect(self.check_interval)
        self.interval_timer.start(1000)  # Check every second

        self.setup_tray()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tracking)
        self.timer.start(100)  # Update every 100ms

    def setup_tray(self):
        self.setIcon(self.create_score_icon(0))

        menu = QMenu()

        self.toggle_tracking_action = QAction("Start Tracking")
        self.toggle_tracking_action.triggered.connect(self.toggle_tracking)

        self.toggle_video_action = QAction("Show Video")
        self.toggle_video_action.triggered.connect(self.toggle_video)
        self.toggle_video_action.setEnabled(False)

        interval_menu = QMenu("Tracking Interval", menu)
        interval_actions = {
            "Continuous": 0,
            "Every 15 minutes": 15,
            "Every 30 minutes": 30,
            "Every hour": 60,
            "Every 2 hours": 120,
            "Every 4 hours": 240,
        }

        interval_group = QActionGroup(interval_menu)
        interval_group.setExclusive(True)

        for label, minutes in interval_actions.items():
            action = QAction(label, interval_menu, checkable=True)
            action.setData(minutes)
            action.triggered.connect(lambda checked, m=minutes: self.set_interval(m))
            interval_menu.addAction(action)
            interval_group.addAction(action)
            if minutes == 0:
                action.setChecked(True)

        menu.addMenu(interval_menu)
        menu.addAction(self.toggle_tracking_action)
        menu.addAction(self.toggle_video_action)
        menu.addSeparator()
        menu.addAction(
            QAction("Quit Application", menu, triggered=self.quit_application)
        )

        self.setContextMenu(menu)
        self.setVisible(True)

    def create_score_icon(self, score):
        img = np.zeros((64, 64, 4), dtype=np.uint8)
        img[:, :, 3] = 0

        font = cv2.FONT_HERSHEY_DUPLEX
        text = f"{int(score)}"
        font_scale = 2.0 if len(text) == 1 else (1.5 if len(text) == 2 else 1.2)
        thickness = 3
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (64 - text_size[0]) // 2
        text_y = (64 + text_size[1]) // 2

        hue = int(score * 120 / 100)
        rgb_color = cv2.cvtColor(np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0]
        color = (int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]), 255)

        temp = img.copy()
        cv2.putText(temp, text, (text_x, text_y), font, font_scale, color, thickness)

        height, width, channel = temp.shape
        bytes_per_line = 4 * width
        q_img = QImage(
            temp.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888
        )
        return QIcon(QPixmap.fromImage(q_img))

    def toggle_tracking(self):
        if not self.tracking_enabled:
            self.frame_reader.start(callback=self.detector.process_frame)
            self.tracking_enabled = True
            self.toggle_tracking_action.setText("Stop Tracking")
            self.toggle_video_action.setEnabled(True)

            if self.tracking_interval > 0:
                self.notifier.set_message(
                    f"Checking posture (runs every {self.tracking_interval} minutes)"
                )
            else:
                self.notifier.set_message("Please sit up straight!")
        else:
            self.frame_reader.stop()
            self.tracking_enabled = False
            self.toggle_tracking_action.setText("Start Tracking")
            self.toggle_video_action.setEnabled(False)
            self.toggle_video_action.setText("Show Video")
            if self.video_window:
                cv2.destroyWindow("Posture Detection")
                self.video_window = None
            self.setIcon(self.create_score_icon(0))

    def toggle_video(self):
        if self.video_window:
            cv2.destroyWindow("Posture Detection")
            self.video_window = None
            self.toggle_video_action.setText("Show Video")
        else:
            self.video_window = True
            self.toggle_video_action.setText("Hide Video")

    def update_tracking(self):
        if self.tracking_enabled:
            frame, score = self.frame_reader.get_latest_frame()
            if frame is not None:
                self.scores.add_score(score)
                average_score = self.scores.get_average_score()

                self.setIcon(self.create_score_icon(average_score))

                self.notifier.check_and_notify(average_score)
                if self.video_window:
                    cv2.imshow("Posture Detection", frame)
                    cv2.waitKey(1)

    def quit_application(self):
        self.frame_reader.stop()
        if self.video_window:
            cv2.destroyWindow("Posture Detection")
        QApplication.quit()

    def set_interval(self, minutes):
        self.tracking_interval = minutes
        if minutes == 0:
            if not self.tracking_enabled:
                self.toggle_tracking()
        else:
            self.last_tracking_time = None
            if self.tracking_enabled:
                self.toggle_tracking()

    def check_interval(self):
        if self.tracking_interval <= 0:
            return

        current_time = datetime.now()

        if self.last_tracking_time is None:
            self.last_tracking_time = current_time
            self.start_interval_tracking()
            return

        if current_time - self.last_tracking_time >= timedelta(
            minutes=self.tracking_interval
        ):
            self.start_interval_tracking()

    def start_interval_tracking(self):
        self.last_tracking_time = datetime.now()

        if not self.tracking_enabled:
            self.toggle_tracking()

        QTimer.singleShot(60000, self.stop_interval_tracking)

    def stop_interval_tracking(self):
        if self.tracking_enabled and self.tracking_interval > 0:
            self.toggle_tracking()
