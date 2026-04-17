from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

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
        return None, 0.0

    def get_latest_pose_results(self):
        return None


class DummyScoreService:
    def __init__(self) -> None:
        self.reload_calls = 0

    def reload(self, settings) -> None:
        self.reload_calls += 1


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
