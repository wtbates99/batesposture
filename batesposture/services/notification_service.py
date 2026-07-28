from __future__ import annotations

from time import monotonic

from .platform_notification import send_notification
from .settings_service import SettingsService


class NotificationService:
    """Sends desktop notifications for posture alerts and tracking status changes.

    Respects ``notifications_enabled`` and ``focus_mode_enabled`` runtime settings.
    Implements a cooldown (``notification_cooldown`` seconds, default 300) to prevent
    repeated alerts during sustained poor posture.
    """

    TREND_DROP_POINTS: float = 12.0

    def __init__(self, settings: SettingsService, icon_path: str) -> None:
        self._settings = settings
        self._icon_path = icon_path
        self._last_notification_time: float = 0.0
        self._last_trend_notification_time: float = 0.0

    def notify_interval_change(self, message: str) -> None:
        runtime = self._settings.runtime
        if message and runtime.notifications_enabled and not runtime.focus_mode_enabled:
            send_notification(message, "Tracking Interval Changed", self._icon_path)

    def maybe_notify_posture(self, posture_score: float) -> None:
        runtime = self._settings.runtime
        if not runtime.notifications_enabled or runtime.focus_mode_enabled:
            return
        if posture_score < runtime.poor_posture_threshold:
            current_time = monotonic()
            if (
                current_time - self._last_notification_time
                > runtime.notification_cooldown
            ):
                send_notification(
                    runtime.default_posture_message,
                    "Posture Alert!",
                    self._icon_path,
                )
                self._last_notification_time = current_time

    def maybe_notify_trend(self, score_service) -> None:
        """Nudge the user when rolling posture has declined meaningfully.

        Catches gradual slumps that never cross the absolute threshold. Uses an
        independent cooldown from the threshold alert so the two don't interfere.
        """
        runtime = self._settings.runtime
        if not runtime.notifications_enabled or runtime.focus_mode_enabled:
            return
        decline = score_service.recent_decline()
        if decline is None or decline < self.TREND_DROP_POINTS:
            return
        current_time = monotonic()
        if (
            current_time - self._last_trend_notification_time
            <= runtime.notification_cooldown
        ):
            return
        send_notification(
            f"Your posture has slipped {decline:.0f} points — time to reset.",
            "Posture Trending Down",
            self._icon_path,
        )
        self._last_trend_notification_time = current_time
