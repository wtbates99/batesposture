"""Platform-native desktop notification utilities.

Dispatch table:
- macOS  — AppleScript via ``osascript``
- Linux  — ``notify-send`` (libnotify)
- Other  — ``plyer.notification`` (covers Windows and fallback platforms)

All implementations use subprocess argument lists (never shell=True) to
prevent injection from untrusted message or title strings.
"""
import platform
import subprocess


def send_notification(message: str, title: str, icon_path: str) -> None:
    """Send a desktop notification using platform-native mechanisms.

    Args:
        message: Notification body text (single quotes and backslashes are escaped
                 for AppleScript on macOS).
        title:   Notification title.
        icon_path: Path to the app icon; used by notify-send (Linux) and plyer
                   (Windows). Ignored on macOS (AppleScript does not support icons).

    Fails silently (``check=False``) if the notification daemon is unavailable.
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
