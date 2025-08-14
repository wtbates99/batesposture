from unittest.mock import patch
import pytest

from ..notifications import Notifications


@pytest.fixture
def notif_manager():
    """Create a Notifications instance with a mock icon path"""
    return Notifications("/mock/icon/path.png")


def test_init(notif_manager):
    """Test that Notifications initializes with correct default values"""
    assert notif_manager.last_notification_time == 0
    assert notif_manager.notification_cooldown == 300  # From settings
    assert notif_manager.poor_posture_threshold == 60  # From settings
    assert notif_manager.posture_message == "Please sit up straight!"  # From settings
    assert notif_manager.icon_path == "/mock/icon/path.png"
    assert notif_manager.interval_message is None


@patch("src.notifications.send_notification")
@patch("time.time")
def test_check_and_notify_bad_posture(mock_time, mock_send_notification, notif_manager):
    """Test notification is sent when posture score is below threshold"""
    mock_time.return_value = 1000
    notif_manager.check_and_notify(40)  # Below threshold of 60

    mock_send_notification.assert_called_once_with(
        "Please sit up straight!", "Posture Alert!", "/mock/icon/path.png"
    )
    assert notif_manager.last_notification_time == 1000


@patch("src.notifications.send_notification")
@patch("time.time")
def test_check_and_notify_good_posture(
    mock_time, mock_send_notification, notif_manager
):
    """Test no notification is sent when posture score is above threshold"""
    mock_time.return_value = 1000
    notif_manager.check_and_notify(80)  # Above threshold of 60

    mock_send_notification.assert_not_called()
    assert notif_manager.last_notification_time == 0  # Should not change


@patch("src.notifications.send_notification")
@patch("time.time")
def test_notification_cooldown(mock_time, mock_send_notification, notif_manager):
    """Test that notifications respect the cooldown period"""
    mock_time.return_value = 1000
    # First notification should be sent
    notif_manager.check_and_notify(40)
    assert mock_send_notification.call_count == 1

    # Second notification within cooldown should not be sent
    mock_time.return_value = 1200  # 200 seconds later (less than 300s cooldown)
    notif_manager.check_and_notify(40)
    assert mock_send_notification.call_count == 1  # Should not increase

    # Third notification after cooldown should be sent
    mock_time.return_value = 1400  # 400 seconds later (more than 300s cooldown)
    notif_manager.check_and_notify(40)
    assert mock_send_notification.call_count == 2  # Should increase


@patch("src.notifications.send_notification")
@patch("time.time")
def test_notification_cooldown_exact_boundary(
    mock_time, mock_send_notification, notif_manager
):
    """Test notification behavior at exact cooldown boundary"""
    mock_time.return_value = 1000
    # First notification
    notif_manager.check_and_notify(40)
    assert mock_send_notification.call_count == 1

    # Exactly at cooldown boundary (should not send)
    mock_time.return_value = 1300  # Exactly 300 seconds later
    notif_manager.check_and_notify(40)
    assert mock_send_notification.call_count == 1  # Should not increase

    # Just over cooldown boundary (should send)
    mock_time.return_value = 1301  # 301 seconds later
    notif_manager.check_and_notify(40)
    assert mock_send_notification.call_count == 2  # Should increase


@patch("src.notifications.send_notification")
@patch("time.time")
def test_notification_cooldown_only_applies_to_posture(
    mock_time, mock_send_notification, notif_manager
):
    """Test that cooldown only applies to posture notifications, not interval messages"""
    mock_time.return_value = 1000
    # Send posture notification
    notif_manager.check_and_notify(40)
    assert mock_send_notification.call_count == 1

    # Send interval message immediately after (should work despite cooldown)
    notif_manager.set_interval_message("Test interval")
    assert mock_send_notification.call_count == 2  # Should increase


@patch("src.notifications.send_notification")
def test_set_interval_message_with_message(mock_send_notification, notif_manager):
    """Test setting interval message with a valid message"""
    notif_manager.set_interval_message("New tracking interval: 30 minutes")

    assert notif_manager.interval_message == "New tracking interval: 30 minutes"
    mock_send_notification.assert_called_once_with(
        "New tracking interval: 30 minutes",
        "Tracking Interval Changed",
        "/mock/icon/path.png",
    )


@patch("src.notifications.send_notification")
def test_set_interval_message_with_none(mock_send_notification, notif_manager):
    """Test setting interval message to None (clearing it)"""
    # First set a message
    notif_manager.set_interval_message("Test message")
    mock_send_notification.reset_mock()

    # Then clear it
    notif_manager.set_interval_message(None)

    assert notif_manager.interval_message is None
    mock_send_notification.assert_not_called()


@patch("src.notifications.send_notification")
@patch("time.time")
def test_multiple_posture_notifications_respect_cooldown(
    mock_time, mock_send_notification, notif_manager
):
    """Test multiple posture notifications over time respect cooldown"""
    mock_time.return_value = 1000
    # First notification
    notif_manager.check_and_notify(30)
    assert mock_send_notification.call_count == 1

    # Multiple attempts within cooldown
    for i in range(5):
        mock_time.return_value = 1000 + (i * 60)  # Every minute for 5 minutes
        notif_manager.check_and_notify(30)
        assert mock_send_notification.call_count == 1  # Should not increase

    # After cooldown
    mock_time.return_value = 1400  # 400 seconds later
    notif_manager.check_and_notify(30)
    assert mock_send_notification.call_count == 2  # Should increase


@patch("src.notifications.send_notification")
@patch("time.time")
def test_posture_score_at_threshold(mock_time, mock_send_notification, notif_manager):
    """Test behavior when posture score is exactly at the threshold"""
    mock_time.return_value = 1000
    notif_manager.check_and_notify(60)  # Exactly at threshold

    mock_send_notification.assert_not_called()
    assert notif_manager.last_notification_time == 0


@patch("src.notifications.send_notification")
@patch("time.time")
def test_posture_score_just_below_threshold(
    mock_time, mock_send_notification, notif_manager
):
    """Test behavior when posture score is just below threshold"""
    mock_time.return_value = 1000
    notif_manager.check_and_notify(59)  # Just below threshold of 60

    mock_send_notification.assert_called_once_with(
        "Please sit up straight!", "Posture Alert!", "/mock/icon/path.png"
    )
    assert notif_manager.last_notification_time == 1000


@patch("src.notifications.send_notification")
@patch("time.time")
def test_posture_score_just_above_threshold(
    mock_time, mock_send_notification, notif_manager
):
    """Test behavior when posture score is just above threshold"""
    mock_time.return_value = 1000
    notif_manager.check_and_notify(61)  # Just above threshold of 60

    mock_send_notification.assert_not_called()
    assert notif_manager.last_notification_time == 0


@patch("src.notifications.send_notification")
def test_interval_message_persistence(mock_send_notification, notif_manager):
    """Test that interval message persists until changed"""
    # Set initial message
    notif_manager.set_interval_message("Initial interval")
    assert notif_manager.interval_message == "Initial interval"

    # Set different message
    notif_manager.set_interval_message("Updated interval")
    assert notif_manager.interval_message == "Updated interval"

    # Clear message
    notif_manager.set_interval_message(None)
    assert notif_manager.interval_message is None


@patch("src.notifications.send_notification")
@patch("time.time")
def test_posture_notification_after_interval_message(
    mock_time, mock_send_notification, notif_manager
):
    """Test that posture notifications work correctly after sending interval messages"""
    mock_time.return_value = 1000

    # Send interval message
    notif_manager.set_interval_message("Test interval")
    assert mock_send_notification.call_count == 1

    # Send posture notification
    notif_manager.check_and_notify(30)
    assert mock_send_notification.call_count == 2
