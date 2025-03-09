import platform
import os


def send_notification(message, title, icon_path):
    if platform.system() == "Darwin":  # macOS
        os.system(
            """
                osascript -e 'display notification "{}" with title "{}"'
            """.format(
                message, title
            )
        )
    elif platform.system() == "Linux":
        os.system(f'notify-send "{title}" "{message}" -i "{icon_path}"')
    else:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_icon=icon_path,
            timeout=10,
        )
