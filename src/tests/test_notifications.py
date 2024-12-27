import pytest
from unittest.mock import patch
from ..notifications import notification_manager


@pytest.fixture
def notif_manager():
    return notification_manager()


def test_init(notif_manager):
    assert notif_manager.last_notification_time == 0
    assert notif_manager.notification_cooldown == 300
    assert notif_manager.poor_posture_threshold == 0.6


@patch("src.notifications.notification")
@patch("time.time")
def test_check_and_notify_bad_posture(mock_time, mock_notification, notif_manager):
    # Set up mock time to return consistent values
    mock_time.return_value = 1000

    # Test with poor posture (below threshold)
    notif_manager.check_and_notify(0.4)

    # Verify notification was sent
    mock_notification.notify.assert_called_once_with(
        title="Posture Alert!",
        message="Please sit up straight! Your posture needs attention.",
        app_icon=None,
        timeout=10,
    )
    assert notif_manager.last_notification_time == 1000


@patch("src.notifications.notification")
@patch("time.time")
def test_check_and_notify_good_posture(mock_time, mock_notification, notif_manager):
    # Test with good posture (above threshold)
    mock_time.return_value = 1000

    notif_manager.check_and_notify(0.8)

    # Verify notification was not sent
    mock_notification.notify.assert_not_called()
    assert notif_manager.last_notification_time == 0


@patch("src.notifications.notification")
@patch("time.time")
def test_notification_cooldown(mock_time, mock_notification, notif_manager):
    # First notification
    mock_time.return_value = 1000
    notif_manager.check_and_notify(0.4)
    assert mock_notification.notify.call_count == 1

    # Try to notify again before cooldown
    mock_time.return_value = 1200  # 200 seconds later (less than cooldown)
    notif_manager.check_and_notify(0.4)
    assert mock_notification.notify.call_count == 1  # Should not increase

    # Try after cooldown period
    mock_time.return_value = 1400  # 400 seconds later (more than cooldown)
    notif_manager.check_and_notify(0.4)
    assert mock_notification.notify.call_count == 2  # Should increase
