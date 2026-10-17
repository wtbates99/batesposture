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
    # Poor posture must last this long before an alert: a quick lean to grab
    # a coffee shouldn't buzz anyone.
    SUSTAINED_POOR_S: float = 20.0

    def __init__(self, settings: SettingsService, icon_path: str) -> None:
        self._settings = settings
        self._icon_path = icon_path
        self._last_notification_time: float = 0.0
        self._last_trend_notification_time: float = 0.0
        self._poor_since: float | None = None
        self._snoozed_until: float = 0.0

    def snooze(self, seconds: float) -> None:
        """Silence posture and trend alerts for ``seconds`` (0 ends a snooze)."""
        self._snoozed_until = monotonic() + seconds if seconds > 0 else 0.0

    @property
    def snooze_remaining_s(self) -> float:
        return max(0.0, self._snoozed_until - monotonic())

    def _alerts_allowed(self) -> bool:
        runtime = self._settings.runtime
        return (
            runtime.notifications_enabled
            and not runtime.focus_mode_enabled
            and self.snooze_remaining_s == 0.0
        )

    def notify_interval_change(self, message: str) -> None:
        runtime = self._settings.runtime
        if message and runtime.notifications_enabled and not runtime.focus_mode_enabled:
            send_notification(message, "Tracking Interval Changed", self._icon_path)

    def maybe_notify_posture(self, posture_score: float) -> None:
        runtime = self._settings.runtime
        current_time = monotonic()
        if posture_score >= runtime.poor_posture_threshold:
            self._poor_since = None
            return
        if self._poor_since is None:
            self._poor_since = current_time
        if not self._alerts_allowed():
            return
        if current_time - self._poor_since >= self.SUSTAINED_POOR_S:
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
        if not self._alerts_allowed():
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
