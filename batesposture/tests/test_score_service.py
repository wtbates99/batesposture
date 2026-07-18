"""Unit tests for ScoreService — streaks, pause/resume, absence handling, and stats."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ..services.score_service import ScoreService
from ..services.settings_service import SettingsService


@pytest.fixture
def settings(tmp_path):
    svc = SettingsService.for_testing(tmp_path / "settings.ini")
    svc.update_ml(score_threshold=65, score_window_size=5, score_buffer_size=1000)
    return svc


@pytest.fixture
def service(settings):
    svc = ScoreService(settings)
    # Reset session under the same patched clock the tests use, so session_start
    # doesn't sit far in the future relative to patched score timestamps.
    with patch("batesposture.services.score_service.monotonic", return_value=999.0):
        svc.reset_session()
    return svc


def test_empty_service_returns_zero_average_and_no_stats(service):
    assert service.average() == 0.0
    stats = service.session_stats()
    assert stats["count"] == 0
    assert stats["avg"] == 0.0
    assert stats["duration_s"] == 0.0


def test_average_reflects_recent_scores(service):
    for _ in range(10):
        service.add_score(80.0)
    assert service.average() == pytest.approx(80.0, rel=1e-3)


def test_session_stats_min_max_count(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1001.0):
        for s in [50.0, 70.0, 90.0]:
            service.add_score(s)
        stats = service.session_stats()
    assert stats["count"] == 3
    assert stats["min"] == 50.0
    assert stats["max"] == 90.0
    assert stats["avg"] == pytest.approx(70.0, rel=1e-3)


def test_streak_starts_when_score_above_threshold(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1010.0):
        assert service.current_streak_s == pytest.approx(10.0, rel=1e-3)


def test_streak_breaks_when_score_drops_below_threshold(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1015.0):
        service.add_score(40.0)
        assert service.current_streak_s == 0.0
        # Best streak should record the prior 15s run
        assert service.best_streak_s == pytest.approx(15.0, rel=1e-3)


def test_mark_absent_ends_streak_without_recording_score(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1020.0):
        service.mark_absent()
        assert service.current_streak_s == 0.0
        assert service.best_streak_s == pytest.approx(20.0, rel=1e-3)
    # Scores buffer should still hold only the original entry
    assert service.session_stats()["count"] == 1


def test_mark_absent_is_idempotent(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1010.0):
        service.mark_absent()
        service.mark_absent()
        service.mark_absent()
    # Best streak captured once; calling absent again doesn't extend it
    assert service.best_streak_s == pytest.approx(10.0, rel=1e-3)


def test_pause_resume_excludes_away_time_from_duration(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1010.0):
        service.pause_session()
    with patch("batesposture.services.score_service.monotonic", return_value=1100.0):
        service.resume_session()
    with patch("batesposture.services.score_service.monotonic", return_value=1110.0):
        stats = service.session_stats()
    # 1110 - 999 total - 90 paused = 21s active
    assert stats["duration_s"] == pytest.approx(21.0, rel=1e-2)


def test_resume_without_pause_is_noop(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    # Should not raise or corrupt paused_duration
    service.resume_session()
    with patch("batesposture.services.score_service.monotonic", return_value=1010.0):
        stats = service.session_stats()
    assert stats["duration_s"] == pytest.approx(11.0, rel=1e-2)


def test_add_score_auto_resumes_paused_session(service):
    """When the user returns to frame, an incoming score should clear paused state."""
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1010.0):
        service.pause_session()
    with patch("batesposture.services.score_service.monotonic", return_value=1100.0):
        service.add_score(85.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1110.0):
        stats = service.session_stats()
    # 1110 - 999 total - 90 paused = 21s active
    assert stats["duration_s"] == pytest.approx(21.0, rel=1e-2)


def test_pause_ends_active_streak(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1030.0):
        service.pause_session()
        assert service.current_streak_s == 0.0
        assert service.best_streak_s == pytest.approx(30.0, rel=1e-3)


def test_reset_session_clears_streaks_and_pause(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1050.0):
        service.reset_session()
        assert service.current_streak_s == 0.0
        assert service.best_streak_s == 0.0


def test_average_and_stats_consistent_with_separate_calls(service):
    for s in [60.0, 70.0, 80.0, 90.0]:
        service.add_score(s)
    avg, stats = service.average_and_stats()
    assert avg == pytest.approx(service.average(), rel=1e-6)
    assert stats["count"] == service.session_stats()["count"]
    assert stats["avg"] == service.session_stats()["avg"]


def test_threshold_property_reflects_settings(service):
    assert service.threshold == 65


def test_recent_decline_returns_none_without_baseline(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        service.add_score(80.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1010.0):
        # Baseline window starts 240s back — too soon to compare
        assert service.recent_decline() is None


def test_recent_decline_detects_drop(service):
    # Baseline samples 4–5 minutes ago (~85), recent samples now (~60)
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        for _ in range(5):
            service.add_score(85.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1300.0):
        for _ in range(5):
            service.add_score(60.0)
        decline = service.recent_decline()
    assert decline == pytest.approx(25.0, rel=1e-3)


def test_recent_decline_negative_when_improving(service):
    with patch("batesposture.services.score_service.monotonic", return_value=1000.0):
        for _ in range(5):
            service.add_score(60.0)
    with patch("batesposture.services.score_service.monotonic", return_value=1300.0):
        for _ in range(5):
            service.add_score(85.0)
        decline = service.recent_decline()
    assert decline == pytest.approx(-25.0, rel=1e-3)


def test_reload_picks_up_new_threshold(service, settings):
    settings.update_ml(score_threshold=80)
    service.reload(settings)
    assert service.threshold == 80
    # A score of 70 should no longer count as a good-posture streak
    with patch("batesposture.services.score_service.monotonic", return_value=2000.0):
        service.add_score(70.0)
        assert service.current_streak_s == 0.0
