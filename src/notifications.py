import time
import os
import platform


class notification_manager:
    def __init__(self):
        self.last_notification_time = 0
        self.notification_cooldown = 300  # 5 minutes between notifications
        self.poor_posture_threshold = 0.6  # Adjust this threshold as needed

    def check_and_notify(self, posture_score):
        current_time = time.time()

        if (
            posture_score < self.poor_posture_threshold
            and current_time - self.last_notification_time > self.notification_cooldown
        ):
            self.send_notification()
            self.last_notification_time = current_time

    def send_notification(self):
        if platform.system() == "Darwin":  # macOS
            title = "Posture Alert!"
            message = "Please sit up straight! Your posture needs attention."
            os.system(
                """
                osascript -e 'display notification "{}" with title "{}"'
                """.format(
                    message, title
                )
            )
        else:
            # Fall back to plyer for other operating systems
            from plyer import notification

            notification.notify(
                title="Posture Alert!",
                message="Please sit up straight! Your posture needs attention.",
                app_icon=None,
                timeout=10,
            )


# Add test code
if __name__ == "__main__":
    # Create an instance of the notification manager
    notifier = notification_manager()

    # Simulate poor posture detection
    print("Testing notification system...")
    print("Simulating poor posture (score: 0.5)")

    # Test with a poor posture score (0.5 is below the threshold of 0.6)
    notifier.check_and_notify(0.5)

    # Wait for 2 seconds
    time.sleep(2)

    print("\nTesting notification cooldown...")
    print("Attempting second notification...")

    # Try to send another notification (should be blocked by cooldown)
    notifier.check_and_notify(0.5)

    print("\nTest complete!")
