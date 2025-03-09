import os
import platform
import time
from settings import get_setting


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
            self.send_notification(message, "Tracking Interval Changed")

    def check_and_notify(self, posture_score):
        current_time = time.time()
        # only apply cooldown to posture notifications
        if posture_score < self.poor_posture_threshold:
            if current_time - self.last_notification_time > self.notification_cooldown:
                self.send_notification(self.posture_message, "Posture Alert!")
                self.last_notification_time = current_time

    def send_notification(self, message, title):
        if platform.system() == "Darwin":  # macOS
            os.system(
                """
                osascript -e 'display notification "{}" with title "{}"'
                """.format(
                    message, title
                )
            )
        elif platform.system() == "Linux":
            os.system(f'notify-send "{title}" "{message}" -i "{self.icon_path}"')
        else:
            from plyer import notification

            notification.notify(
                title=title,
                message=message,
                app_icon=self.icon_path,
                timeout=10,
            )
