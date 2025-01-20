import os
import platform
import time


class NotificationManager:
    def __init__(self):
        self.last_notification_time = 0
        self.notification_cooldown = 300  # 5 minutes between notifications
        self.poor_posture_threshold = 60  # Adjust this threshold as needed
        self.posture_message = "Please sit up straight!"
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
            os.system(f'notify-send "{title}" "{message}"')
        else:
            from plyer import notification

            notification.notify(
                title=title,
                message=message,
                app_icon=None,
                timeout=10,
            )


if __name__ == "__main__":
    notifier = NotificationManager()

    notifier.set_interval_message("Checking posture every 5 minutes")
    time.sleep(1)
    notifier.set_interval_message("Checking posture every 3 minutes")
    time.sleep(1)
    notifier.set_interval_message("Checking posture every 1 minute")

    notifier.check_and_notify(50)  # Should trigger notification

    notifier.check_and_notify(50)  # Should not trigger (cooldown period)

    notifier.set_interval_message("Checking posture every 10 minutes")

    print("\nWaiting 5 seconds...")
    time.sleep(5)
    print("This posture alert should appear (after cooldown):")
    notifier.check_and_notify(50)  # Should trigger (cooldown expired)
