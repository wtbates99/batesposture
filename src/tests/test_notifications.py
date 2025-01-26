from unittest.mock import patch

import pytest

from ..notifications import NotificationManager


@pytest.fixture
def notif_manager():
    return NotificationManager()


def test_init(notif_manager):
    assert notif_manager.last_notification_time == 0
    assert notif_manager.notification_cooldown == 300
    assert notif_manager.poor_posture_threshold == 60


@patch("plyer.notification")
@patch("time.time")
def test_check_and_notify_bad_posture(mock_time, mock_notification, notif_manager):
    mock_time.return_value = 1000
    # Force non-Darwin, non-Linux platform for testing
    with patch("platform.system", return_value="Windows"):
        notif_manager.check_and_notify(0.4)

    mock_notification.notify.assert_called_once_with(
        title="Posture Alert!",
        message=notif_manager.posture_message,
        app_icon=None,
        timeout=10,
    )
    assert notif_manager.last_notification_time == 1000


@patch("plyer.notification")
@patch("time.time")
def test_notification_cooldown(mock_time, mock_notification, notif_manager):
    mock_time.return_value = 1000
    # Force non-Darwin, non-Linux platform for testing
    with patch("platform.system", return_value="Windows"):
        notif_manager.check_and_notify(0.4)
        assert mock_notification.notify.call_count == 1

        mock_time.return_value = 1200  # 200 seconds later (less than cooldown)
        notif_manager.check_and_notify(0.4)
        assert mock_notification.notify.call_count == 1  # Should not increase

        mock_time.return_value = 1400  # 400 seconds later (more than cooldown)
        notif_manager.check_and_notify(0.4)
        assert mock_notification.notify.call_count == 2  # Should increase


@patch("os.system")
def test_macos_notification(mock_system, notif_manager):
    with patch("platform.system", return_value="Darwin"):
        notif_manager.send_notification("Test Message", "Test Title")
    mock_system.assert_called_once_with(
        '\n                osascript -e \'display notification "Test Message" with title "Test Title"\'\n                '
    )


@patch("os.system")
def test_linux_notification(mock_system, notif_manager):
    with patch("platform.system", return_value="Linux"):
        notif_manager.send_notification("Test Message", "Test Title")
    mock_system.assert_called_once_with('notify-send "Test Title" "Test Message"')


@patch("plyer.notification")
@patch("time.time")
def test_check_and_notify_good_posture(mock_time, mock_notification, notif_manager):
    mock_time.return_value = 1000
    with patch("platform.system", return_value="Windows"):
        notif_manager.check_and_notify(70)  # Above threshold
    mock_notification.notify.assert_not_called()


@patch("plyer.notification")
def test_set_interval_message(mock_notification, notif_manager):
    with patch("platform.system", return_value="Windows"):
        # Test setting new message
        notif_manager.set_interval_message("New Interval")
        assert notif_manager.interval_message == "New Interval"
        mock_notification.notify.assert_called_once_with(
            title="Tracking Interval Changed",
            message="New Interval",
            app_icon=None,
            timeout=10,
        )

        # Test clearing message
        mock_notification.notify.reset_mock()
        notif_manager.set_interval_message(None)
        assert notif_manager.interval_message is None
        mock_notification.notify.assert_not_called()


def test_posture_message(notif_manager):
    assert notif_manager.posture_message == "Please sit up straight!"
