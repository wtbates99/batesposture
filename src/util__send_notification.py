import platform
import subprocess


def send_notification(message: str, title: str, icon_path: str) -> None:
    """Send a desktop notification using platform-native mechanisms.

    Uses subprocess with argument lists to avoid shell injection vulnerabilities.
    """
    system = platform.system()
    if system == "Darwin":
        # Escape single quotes in the strings for AppleScript
        safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        subprocess.run(["osascript", "-e", script], check=False)
    elif system == "Linux":
        subprocess.run(
            ["notify-send", title, message, "-i", icon_path],
            check=False,
        )
    else:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_icon=icon_path,
            timeout=10,
        )
