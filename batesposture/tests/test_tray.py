from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from ..ml.pose_detector import PoseDetectionResult
from ..services.settings_service import SettingsService
from ..ui import tray as tray_module

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class DummyScheduler:
    def schedule(self, name, interval_ms, callback) -> None:
        return None

    def single_shot(self, delay_ms, callback) -> None:
        return None

    def shutdown(self) -> None:
        return None


class DummyDetector:
    def __init__(self) -> None:
        self.reload_calls = 0

    def process_frame(self, frame):
        return frame, 0.0, None

    def reload(self) -> None:
        self.reload_calls += 1


class DummyCameraService:
    def __init__(self) -> None:
        self.reload_calls = 0
        self.latest_frame = None
        self.latest_score = 0.0
        self.latest_pose_results = None

    @contextmanager
    def pause_processing(self):
        yield

    def reload_settings(self) -> None:
        self.reload_calls += 1

    def start(self, callback=None) -> bool:
        return True

    def stop(self) -> None:
        return None

    def get_latest_frame(self):
        return self.latest_frame, self.latest_score

    def get_latest_pose_results(self):
        return self.latest_pose_results


class DummyScoreService:
    def __init__(self) -> None:
        self.reload_calls = 0
        self.pause_calls = 0
        self.resume_calls = 0
        self.mark_absent_calls = 0
        self.added_scores = []
        self.current_streak_s = 0.0

    def reload(self, settings) -> None:
        self.reload_calls += 1

    def reset_session(self) -> None:
        return None

    def mark_absent(self) -> None:
        self.mark_absent_calls += 1

    def pause_session(self) -> None:
        self.pause_calls += 1

    def resume_session(self) -> None:
        self.resume_calls += 1

    def add_score(self, score: float) -> None:
        self.added_scores.append(score)

    def average_and_stats(self):
        latest = self.added_scores[-1] if self.added_scores else 0.0
        return latest, {
            "count": len(self.added_scores),
            "avg": latest,
            "min": latest,
            "max": latest,
            "duration_s": 0.0,
            "best_streak_s": 0.0,
            "current_streak_s": self.current_streak_s,
        }


class DummyNotificationService:
    def notify_interval_change(self, message: str) -> None:
        return None

    def maybe_notify_posture(self, posture_score: float) -> None:
        return None


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _build_tray(tmp_path, monkeypatch):
    monkeypatch.setattr(tray_module, "run_onboarding_if_needed", lambda settings: False)
    monkeypatch.setattr(tray_module, "create_score_icon", lambda score: QIcon())
    monkeypatch.setattr(
        tray_module.PostureTrackerTray, "_setup_signal_handling", lambda self: None
    )
    monkeypatch.setattr(
        tray_module.PostureTrackerTray, "setVisible", lambda self, visible: None
    )

    settings = SettingsService.for_testing(tmp_path / "tray_settings.ini")
    detector = DummyDetector()
    camera = DummyCameraService()
    scores = DummyScoreService()
    tray = tray_module.PostureTrackerTray(
        settings=settings,
        detector=detector,
        camera_service=camera,
        score_service=scores,
        notification_service=DummyNotificationService(),
        scheduler=DummyScheduler(),
        database=None,
    )
    return tray, settings, detector, camera, scores


def test_refresh_after_settings_change_syncs_database_logging(
    qapp, tmp_path, monkeypatch
):
    tray, settings, detector, camera, scores = _build_tray(tmp_path, monkeypatch)
    try:
        assert tray._database is None

        settings.update_runtime(enable_database_logging=True)
        tray._refresh_after_settings_change()

        assert tray._database is not None
        assert tray.export_action.isEnabled()
        assert detector.reload_calls == 1
        assert camera.reload_calls == 1
        assert scores.reload_calls == 1

        settings.update_runtime(enable_database_logging=False)
        tray._refresh_after_settings_change()

        assert tray._database is None
        assert not tray.export_action.isEnabled()
    finally:
        if tray._database:
            tray._database.close()
        tray.hide()


def test_save_to_db_uses_elapsed_interval_for_scheduled_tracking():
    saved = []
    fake_db = SimpleNamespace(
        save_pose_data=lambda pose, score: saved.append((pose, score))
    )
    fake_tray = SimpleNamespace(
        _database=fake_db,
        _settings=SimpleNamespace(
            runtime=SimpleNamespace(db_write_interval_seconds=300)
        ),
        last_db_save=None,
    )
    bundle = SimpleNamespace(pose_landmarks="pose-landmarks")
    start = datetime(2026, 1, 1, 12, 0, 0)

    with pytest.MonkeyPatch.context() as monkeypatch:

        class FakeDateTime:
            _values = iter(
                (
                    start,
                    start + timedelta(seconds=120),
                    start + timedelta(seconds=301),
                )
            )

            @classmethod
            def now(cls):
                return next(cls._values)

        monkeypatch.setattr(tray_module, "datetime", FakeDateTime)
        tray_module.PostureTrackerTray._save_to_db(fake_tray, 80.0, bundle)
        tray_module.PostureTrackerTray._save_to_db(fake_tray, 81.0, bundle)
        tray_module.PostureTrackerTray._save_to_db(fake_tray, 82.0, bundle)

    assert saved == [("pose-landmarks", 80.0), ("pose-landmarks", 82.0)]


def test_tracking_pauses_after_human_absence_grace_period(qapp, tmp_path, monkeypatch):
    tray, settings, detector, camera, scores = _build_tray(tmp_path, monkeypatch)
    camera.latest_frame = object()
    camera.latest_pose_results = None
    tray.tracking_enabled = True

    start = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.MonkeyPatch.context() as patch_ctx:

        class FakeDateTime:
            _values = iter((start, start + timedelta(seconds=3)))

            @classmethod
            def now(cls):
                return next(cls._values)

        patch_ctx.setattr(tray_module, "datetime", FakeDateTime)
        tray._update_tracking()
        assert not tray._tracking_paused_for_absence
        tray._update_tracking()

    assert tray._tracking_paused_for_absence
    assert scores.mark_absent_calls == 2
    assert scores.pause_calls == 1
    assert tray.toolTip() == "Away from desk — tracking paused"


def test_tracking_resumes_when_human_returns(qapp, tmp_path, monkeypatch):
    tray, settings, detector, camera, scores = _build_tray(tmp_path, monkeypatch)
    tray.tracking_enabled = True
    tray._tracking_paused_for_absence = True
    tray._absence_started_at = datetime(2026, 1, 1, 12, 0, 0)
    tray._continuous_tracking_start = datetime(2026, 1, 1, 11, 0, 0)
    tray._break_reminder_sent = True
    tray.last_db_save = datetime(2026, 1, 1, 11, 55, 0)

    camera.latest_frame = object()
    camera.latest_score = 88.0
    camera.latest_pose_results = PoseDetectionResult(
        SimpleNamespace(pose_landmarks=True),
        {"posture_score": 88.0},
    )

    resume_time = datetime(2026, 1, 1, 12, 5, 0)
    with pytest.MonkeyPatch.context() as patch_ctx:

        class FakeDateTime:
            @classmethod
            def now(cls):
                return resume_time

        patch_ctx.setattr(tray_module, "datetime", FakeDateTime)
        tray._update_tracking()

    assert not tray._tracking_paused_for_absence
    assert tray._absence_started_at is None
    assert scores.resume_calls == 1
    assert scores.added_scores == [88.0]
    assert tray.last_db_save is None
    assert tray._continuous_tracking_start == resume_time
    assert tray._break_reminder_sent is False
