"""Integration tests for the camera → scoring → notification pipeline."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from ..data.database import Database
from ..services.notification_service import NotificationService
from ..services.score_service import ScoreService
from ..services.settings_service import (
    SettingsService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings(tmp_path):
    svc = SettingsService.for_testing(tmp_path / "settings.ini")
    svc.update_runtime(notifications_enabled=True, focus_mode_enabled=False)
    svc.save_all()
    return svc


@pytest.fixture
def score_service(settings):
    svc = ScoreService(settings)
    svc.reset_session()
    return svc


@pytest.fixture
def notification_service(settings):
    return NotificationService(settings, "/mock/icon.png")


@pytest.fixture
def db(tmp_path, settings):
    manager = Database(str(tmp_path / "test.db"), settings.get_posture_landmarks())
    yield manager
    manager.close()


# ---------------------------------------------------------------------------
# 1. Score accumulation
# ---------------------------------------------------------------------------


def test_score_service_accumulates_scores(score_service):
    """ScoreService.average() should converge toward the submitted values."""
    for _ in range(10):
        score_service.add_score(80.0)

    avg = score_service.average()
    assert 70.0 <= avg <= 90.0, f"Expected ~80, got {avg}"


def test_score_service_returns_zero_when_empty(score_service):
    assert score_service.average() == 0.0


# ---------------------------------------------------------------------------
# 2. Notification fires when score is below threshold
# ---------------------------------------------------------------------------


@patch("batesposture.services.notification_service.send_notification")
@patch("batesposture.services.notification_service.monotonic", return_value=1000.0)
def test_notification_fires_below_threshold(
    mock_monotonic, mock_send, settings, notification_service
):
    settings.update_runtime(poor_posture_threshold=70, notification_cooldown=300)
    notification_service.maybe_notify_posture(50.0)
    mock_send.assert_called_once()


@patch("batesposture.services.notification_service.send_notification")
def test_notification_suppressed_above_threshold(
    mock_send, settings, notification_service
):
    settings.update_runtime(poor_posture_threshold=70)
    notification_service.maybe_notify_posture(85.0)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Notification cooldown
# ---------------------------------------------------------------------------


@patch("batesposture.services.notification_service.send_notification")
def test_notification_suppressed_during_cooldown(
    mock_send, settings, notification_service
):
    """Two calls within the cooldown window should only produce one notification."""
    settings.update_runtime(poor_posture_threshold=70, notification_cooldown=300)
    with patch(
        "batesposture.services.notification_service.monotonic", return_value=1000.0
    ):
        notification_service.maybe_notify_posture(40.0)
    # Still within cooldown window (only 1 second has passed)
    with patch(
        "batesposture.services.notification_service.monotonic", return_value=1001.0
    ):
        notification_service.maybe_notify_posture(40.0)
    assert mock_send.call_count == 1


@patch("batesposture.services.notification_service.send_notification")
def test_notification_fires_after_cooldown_expires(
    mock_send, settings, notification_service
):
    settings.update_runtime(poor_posture_threshold=70, notification_cooldown=300)
    with patch(
        "batesposture.services.notification_service.monotonic", return_value=1000.0
    ):
        notification_service.maybe_notify_posture(40.0)
    # Cooldown (300s) has elapsed
    with patch(
        "batesposture.services.notification_service.monotonic", return_value=1301.0
    ):
        notification_service.maybe_notify_posture(40.0)
    assert mock_send.call_count == 2


# ---------------------------------------------------------------------------
# 4. Settings reload propagates to ScoreService
# ---------------------------------------------------------------------------


def test_settings_reload_propagates_threshold(settings, score_service):
    original = score_service.threshold
    new_threshold = original + 10
    settings.update_ml(score_threshold=new_threshold)
    score_service.reload(settings)
    assert score_service.threshold == new_threshold


def test_settings_reload_resizes_buffer(settings, score_service):
    for _ in range(5):
        score_service.add_score(75.0)

    settings.update_ml(score_buffer_size=200)
    score_service.reload(settings)
    # Buffer was resized; existing scores are cleared
    assert score_service.average() == 0.0


# ---------------------------------------------------------------------------
# 5. Absence handling — mark_absent() must not pollute the score buffer
# ---------------------------------------------------------------------------


def test_mark_absent_does_not_add_scores(score_service):
    """mark_absent() must leave the rolling buffer untouched."""
    for _ in range(5):
        score_service.add_score(80.0)
    avg_before = score_service.average()

    for _ in range(10):
        score_service.mark_absent()

    avg_after = score_service.average()
    assert avg_after == pytest.approx(avg_before, abs=1.0)


def test_mark_absent_breaks_streak(score_service):
    """A good-posture streak must be ended by an absence so time away never inflates it."""
    for _ in range(10):
        score_service.add_score(90.0)
    assert score_service.current_streak_s > 0.0

    score_service.mark_absent()
    assert score_service.current_streak_s == 0.0


def test_mark_absent_saves_best_streak(score_service):
    """best_streak_s must capture the streak that was broken by absence."""
    for _ in range(10):
        score_service.add_score(90.0)
    streak_before = score_service.current_streak_s

    score_service.mark_absent()
    assert score_service.best_streak_s >= streak_before


def test_mark_absent_idempotent_when_no_streak(score_service):
    """Calling mark_absent() repeatedly without a streak must not raise."""
    for _ in range(5):
        score_service.mark_absent()
    assert score_service.current_streak_s == 0.0


def test_pause_session_excludes_absence_from_duration(settings):
    score_service = ScoreService(settings)
    with patch(
        "batesposture.services.score_service.monotonic",
        side_effect=[0.0, 1.0, 6.0, 11.0, 12.0, 15.0],
    ):
        score_service.reset_session()
        score_service.add_score(50.0)
        score_service.pause_session()
        paused_stats = score_service.session_stats()
        score_service.resume_session()
        resumed_stats = score_service.session_stats()

    assert paused_stats["duration_s"] == pytest.approx(6.0)
    assert resumed_stats["duration_s"] == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# 6. Thread safety: concurrent add_score calls don't corrupt state
# ---------------------------------------------------------------------------


def test_score_service_thread_safety(score_service):
    """Hammering add_score from multiple threads should not raise or corrupt data."""
    import threading

    errors: list[Exception] = []

    def _worker():
        try:
            for _ in range(100):
                score_service.add_score(float(np.random.uniform(0, 100)))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread safety errors: {errors}"
    stats = score_service.session_stats()
    assert stats["count"] > 0


# ---------------------------------------------------------------------------
# 6. Dashboard history round-trip through Database
# ---------------------------------------------------------------------------


def test_dashboard_history_persists_and_reloads(db):
    pairs = [(1000.0 + i, float(50 + i)) for i in range(10)]
    db.save_dashboard_history(pairs)
    loaded = db.load_dashboard_history()
    assert len(loaded) == 10
    assert loaded[0] == pytest.approx((1000.0, 50.0))
    assert loaded[-1] == pytest.approx((1009.0, 59.0))


def test_dashboard_history_limit(db):
    pairs = [(float(i), float(i)) for i in range(200)]
    db.save_dashboard_history(pairs)
    loaded = db.load_dashboard_history(limit=50)
    assert len(loaded) == 50
    # Should be the most-recent 50 entries
    assert loaded[0][0] == pytest.approx(150.0)


def test_dashboard_history_empty_db(db):
    assert db.load_dashboard_history() == []
