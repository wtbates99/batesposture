import time
import os
import platform


class notification_manager:
    def __init__(self):
        self.last_notification_time = 0
        self.notification_cooldown = 300  # 5 minutes between notifications
        self.poor_posture_threshold = 60  # Adjust this threshold as needed
        self.message = "Sit up or you will regret it!"

    def set_message(self, message):
        self.message = message

    def check_and_notify(self, posture_score):
        current_time = time.time()

        if (
            posture_score < self.poor_posture_threshold
            and current_time - self.last_notification_time > self.notification_cooldown
        ):
            self.send_notification()
            self.last_notification_time = current_time

    def send_notification(self):
        title = "Posture Alert!"
        if platform.system() == "Darwin":  # macOS
            os.system(
                """
                osascript -e 'display notification "{}" with title "{}"'
                """.format(
                    self.message, title
                )
            )
        elif platform.system() == "Linux":
            os.system(f'notify-send "{title}" "{self.message}"')
        else:
            # Fall back to plyer for other operating systems
            from plyer import notification

            notification.notify(
                title=title,
                message=self.message,
                app_icon=None,
                timeout=10,
            )


if __name__ == "__main__":
    notifier = notification_manager()
    notifier.check_and_notify(50)
