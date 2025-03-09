import time
from util__settings import get_setting
from util__send_notification import send_notification


class Notifications:
    def __init__(self, icon_path):
        self.last_notification_time = 0
        self.notification_cooldown = get_setting("NOTIFICATION_COOLDOWN")
        self.poor_posture_threshold = get_setting("POOR_POSTURE_THRESHOLD")
        self.posture_message = get_setting("DEFAULT_POSTURE_MESSAGE")
        self.icon_path = icon_path
        self.interval_message = None

    def set_interval_message(self, message):
        """Set and immediately send a one-time interval change notification"""
        self.interval_message = message
        if message:
            send_notification(message, "Tracking Interval Changed", self.icon_path)

    def check_and_notify(self, posture_score):
        current_time = time.time()
        # only apply cooldown to posture notifications
        if posture_score < self.poor_posture_threshold:
            if current_time - self.last_notification_time > self.notification_cooldown:
                send_notification(
                    self.posture_message, "Posture Alert!", self.icon_path
                )
                self.last_notification_time = current_time
