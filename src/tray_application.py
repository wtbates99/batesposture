from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction, QImage, QPixmap
from PyQt6.QtCore import QTimer, Qt
import cv2
from webcam import webcam
from pose_detector import pose_detector
from score_history import score_history
from notifications import notification_manager
import sys
import numpy as np


class PostureTrackerTray(QSystemTrayIcon):
    def __init__(self):
        super().__init__()

        # Initialize components
        self.frame_reader = webcam()
        self.detector = pose_detector()
        self.scores = score_history()
        self.notifier = notification_manager()

        # State variables
        self.tracking_enabled = False
        self.video_window = None
        self.current_score = 0

        # Setup tray icon and menu
        self.setup_tray()

        # Create update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tracking)
        self.timer.start(100)  # Update every 100ms

    def setup_tray(self):
        # Create the tray icon
        self.setIcon(self.create_score_icon(0))

        # Create the menu
        menu = QMenu()

        # Add toggle tracking action
        self.toggle_tracking_action = QAction("Start Tracking")
        self.toggle_tracking_action.triggered.connect(self.toggle_tracking)
        menu.addAction(self.toggle_tracking_action)

        # Add toggle video action
        self.toggle_video_action = QAction("Show Video")
        self.toggle_video_action.triggered.connect(self.toggle_video)
        self.toggle_video_action.setEnabled(False)  # Disabled until tracking starts
        menu.addAction(self.toggle_video_action)

        # Add quit action
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.setVisible(True)

    def create_score_icon(self, score):
        # Create a 64x64 image with the score
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        img.fill(255)  # White background

        # Add text centered in the image
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = f"{int(score)}"
        text_size = cv2.getTextSize(text, font, 1, 2)[0]
        text_x = (64 - text_size[0]) // 2
        text_y = (64 + text_size[1]) // 2

        # Color based on score (red to green)
        color = (0, min(255, score * 2.55), min(255, (100 - score) * 2.55))

        cv2.putText(img, text, (text_x, text_y), font, 1, color, 2)

        # Convert to QIcon
        height, width, channel = img.shape
        bytes_per_line = 3 * width
        q_img = QImage(
            img.data, width, height, bytes_per_line, QImage.Format.Format_RGB888
        )
        return QIcon(QPixmap.fromImage(q_img))

    def toggle_tracking(self):
        if not self.tracking_enabled:
            # Start tracking
            self.frame_reader.start(callback=self.detector.process_frame)
            self.tracking_enabled = True
            self.toggle_tracking_action.setText("Stop Tracking")
            self.toggle_video_action.setEnabled(True)
        else:
            # Stop tracking
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
                self.current_score = average_score

                # Update tray icon with current score
                self.setIcon(self.create_score_icon(average_score))

                # Check posture and notify if needed
                self.notifier.check_and_notify(average_score)

                # Update video window if open
                if self.video_window:
                    cv2.imshow("Posture Detection", frame)
                    cv2.waitKey(1)

    def quit_application(self):
        self.frame_reader.stop()
        if self.video_window:
            cv2.destroyWindow("Posture Detection")
        QApplication.quit()
