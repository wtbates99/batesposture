"""Best-effort desktop notifications for macOS, Linux, and Windows."""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _plyer_notification_kwargs(
    message: str, title: str, icon_path: str
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "title": title,
        "message": message,
        "timeout": 10,
    }
    icon = Path(icon_path)
    if icon.is_file() and icon.suffix.lower() == ".ico":
        kwargs["app_icon"] = str(icon)
    return kwargs


def _send_macos(message: str, title: str, _icon_path: str) -> None:
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_message}" with title "{safe_title}"'
    subprocess.run(["osascript", "-e", script], check=False, timeout=5)


def _send_linux(message: str, title: str, icon_path: str) -> None:
    subprocess.run(
        ["notify-send", title, message, "-i", icon_path], check=False, timeout=5
    )


def _send_plyer(message: str, title: str, icon_path: str) -> None:
    from plyer import notification

    notification.notify(**_plyer_notification_kwargs(message, title, icon_path))


def send_notification(message: str, title: str, icon_path: str) -> None:
    """Send a notification without allowing OS integration failures to stop tracking."""
    handlers = {
        "Darwin": _send_macos,
        "Linux": _send_linux,
    }
    handler = handlers.get(platform.system(), _send_plyer)
    try:
        handler(message, title, icon_path)
    except Exception:  # noqa: BLE001 - optional OS integration must never stop tracking
        logger.warning("Desktop notification could not be delivered", exc_info=True)
