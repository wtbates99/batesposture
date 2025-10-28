from __future__ import annotations

from unittest.mock import patch

import pytest

from ..services.notification_service import NotificationService
from ..services.settings_service import SettingsService


@pytest.fixture
def settings_service(tmp_path):
    service = SettingsService.for_testing(tmp_path / "settings.ini")
    service.update_runtime(notifications_enabled=True, focus_mode_enabled=False)
    service.save_all()
    return service


@pytest.fixture
def notification_service(settings_service):
    return NotificationService(settings_service, "/mock/icon.png")


@patch("src.services.notification_service.send_notification")
@patch("time.time", return_value=1000)
def test_notifies_when_below_threshold(mock_time, mock_send, notification_service):
    notification_service.maybe_notify_posture(40)
    mock_send.assert_called_once_with(
        "Please sit up straight!", "Posture Alert!", "/mock/icon.png"
    )


@patch("src.services.notification_service.send_notification")
@patch("time.time", return_value=1000)
def test_respects_cooldown(mock_time, mock_send, notification_service):
    notification_service.maybe_notify_posture(40)
    notification_service.maybe_notify_posture(40)
    # Second call should be suppressed by cooldown
    assert mock_send.call_count == 1


@patch("src.services.notification_service.send_notification")
@patch("time.time", return_value=1000)
def test_disabled_notifications_skip(
    mock_time, mock_send, notification_service, settings_service
):
    settings_service.update_runtime(notifications_enabled=False)
    notification_service.maybe_notify_posture(40)
    mock_send.assert_not_called()
