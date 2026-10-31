from __future__ import annotations

from unittest.mock import patch

import pytest

from ..services.notification_service import NotificationService
from ..services.settings_service import SettingsService


@pytest.fixture
def settings_service(tmp_path):
    service = SettingsService.for_testing(tmp_path / "settings.ini")
    service.update_runtime(notifications_enabled=True, focus_mode_enabled=False)
    return service


@pytest.fixture
def notification_service(settings_service):
    return NotificationService(settings_service, "/mock/icon.png")


class _StubScores:
    def __init__(self, decline):
        self._decline = decline

    def recent_decline(self):
        return self._decline


_MONOTONIC = "batesposture.services.notification_service.monotonic"


def _poor_for(service, seconds, score=40, start=1000.0):
    """Report a poor score at ``start`` and again ``seconds`` later."""
    with patch(_MONOTONIC, return_value=start):
        service.maybe_notify_posture(score)
    with patch(_MONOTONIC, return_value=start + seconds):
        service.maybe_notify_posture(score)


@patch("batesposture.services.notification_service.send_notification")
def test_notifies_when_poor_posture_is_sustained(mock_send, notification_service):
    _poor_for(notification_service, NotificationService.SUSTAINED_POOR_S)
    mock_send.assert_called_once_with(
        "Please sit up straight!", "Posture Alert!", "/mock/icon.png"
    )


@patch("batesposture.services.notification_service.send_notification")
def test_brief_slump_does_not_notify(mock_send, notification_service):
    _poor_for(notification_service, NotificationService.SUSTAINED_POOR_S - 1)
    mock_send.assert_not_called()


@patch("batesposture.services.notification_service.send_notification")
def test_recovering_resets_the_sustain_timer(mock_send, notification_service):
    with patch(_MONOTONIC, return_value=1000.0):
        notification_service.maybe_notify_posture(40)
    with patch(_MONOTONIC, return_value=1010.0):
        notification_service.maybe_notify_posture(90)
    _poor_for(notification_service, 15, start=1015.0)
    mock_send.assert_not_called()


@patch("batesposture.services.notification_service.send_notification")
def test_respects_cooldown(mock_send, notification_service):
    _poor_for(notification_service, NotificationService.SUSTAINED_POOR_S)
    with patch(_MONOTONIC, return_value=1000.0 + NotificationService.SUSTAINED_POOR_S):
        notification_service.maybe_notify_posture(40)
    # Second alert is suppressed by the cooldown (time hasn't advanced)
    assert mock_send.call_count == 1


@patch("batesposture.services.notification_service.send_notification")
def test_snooze_silences_alerts_until_it_expires(mock_send, notification_service):
    with patch(_MONOTONIC, return_value=1000.0):
        notification_service.snooze(3600)
    _poor_for(notification_service, 60)
    with patch(_MONOTONIC, return_value=1060.0):
        notification_service.maybe_notify_trend(_StubScores(decline=30.0))
    mock_send.assert_not_called()

    _poor_for(notification_service, 60, start=4700.0)
    assert mock_send.call_count == 1


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_disabled_notifications_skip(
    mock_monotonic, mock_send, notification_service, settings_service
):
    settings_service.update_runtime(notifications_enabled=False)
    notification_service.maybe_notify_posture(40)
    mock_send.assert_not_called()


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_trend_notification_fires_on_meaningful_drop(
    mock_monotonic, mock_send, notification_service
):
    notification_service.maybe_notify_trend(_StubScores(decline=20.0))
    assert mock_send.call_count == 1
    args = mock_send.call_args[0]
    assert args[1] == "Posture Trending Down"


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_trend_notification_skips_small_drop(
    mock_monotonic, mock_send, notification_service
):
    notification_service.maybe_notify_trend(_StubScores(decline=5.0))
    mock_send.assert_not_called()


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_trend_notification_skips_when_baseline_unavailable(
    mock_monotonic, mock_send, notification_service
):
    notification_service.maybe_notify_trend(_StubScores(decline=None))
    mock_send.assert_not_called()


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_trend_notification_respects_cooldown(
    mock_monotonic, mock_send, notification_service
):
    notification_service.maybe_notify_trend(_StubScores(decline=20.0))
    notification_service.maybe_notify_trend(_StubScores(decline=20.0))
    assert mock_send.call_count == 1


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_trend_notification_disabled_in_focus_mode(
    mock_monotonic, mock_send, notification_service, settings_service
):
    settings_service.update_runtime(focus_mode_enabled=True)
    notification_service.maybe_notify_trend(_StubScores(decline=30.0))
    mock_send.assert_not_called()
