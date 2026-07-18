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


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_notifies_when_below_threshold(mock_monotonic, mock_send, notification_service):
    notification_service.maybe_notify_posture(40)
    mock_send.assert_called_once_with(
        "Please sit up straight!", "Posture Alert!", "/mock/icon.png"
    )


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_respects_cooldown(mock_monotonic, mock_send, notification_service):
    notification_service.maybe_notify_posture(40)
    notification_service.maybe_notify_posture(40)
    # Second call should be suppressed by cooldown (time hasn't advanced)
    assert mock_send.call_count == 1


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_disabled_notifications_skip(
    mock_monotonic, mock_send, notification_service, settings_service
):
    settings_service.update_runtime(notifications_enabled=False)
    notification_service.maybe_notify_posture(40)
    mock_send.assert_not_called()


class _StubScores:
    def __init__(self, decline):
        self._decline = decline

    def recent_decline(self):
        return self._decline


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
