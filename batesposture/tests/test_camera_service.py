from __future__ import annotations

import threading
from unittest.mock import MagicMock

from ..services import camera_service as camera_module
from ..services.camera_service import CameraService
from ..services.settings_service import SettingsService


def _service(tmp_path):
    settings = SettingsService.for_testing(tmp_path / "camera_settings.ini")
    return CameraService(settings)


def test_start_releases_camera_when_device_cannot_open(tmp_path, monkeypatch):
    monkeypatch.setattr(camera_module, "open_camera", lambda camera_id: None)
    service = _service(tmp_path)

    assert not service.start()
    assert service._cap is None
    assert not service._is_running.is_set()


def test_failed_frame_read_stops_and_releases_camera(tmp_path):
    capture = MagicMock()
    capture.read.return_value = (False, None)
    service = _service(tmp_path)
    service._cap = capture
    service._is_running.set()
    service._thread = threading.current_thread()

    service._capture_loop()

    capture.release.assert_called_once_with()
    assert service._cap is None
    assert not service._is_running.is_set()


def test_stop_releases_camera_when_thread_does_not_exit(tmp_path, caplog):
    capture = MagicMock()
    thread = MagicMock()
    thread.is_alive.return_value = True
    service = _service(tmp_path)
    service._cap = capture
    service._thread = thread
    service._is_running.set()

    service.stop()

    thread.join.assert_called_once_with(timeout=2.0)
    capture.release.assert_called_once_with()
    assert "did not stop within 2 seconds" in caplog.text


def test_processed_frames_are_published_with_sequence_and_notification(tmp_path):
    service = _service(tmp_path)
    notified = []
    service._callback = lambda frame: (frame, 72.0, "pose")
    service._on_processed = lambda: notified.append(True)

    service._publish("frame")
    service._publish("frame")

    assert service.get_latest() == (2, "frame", 72.0, "pose")
    assert len(notified) == 2


def test_background_mode_caps_processing_rate(tmp_path):
    service = _service(tmp_path)
    service.set_background(False)
    assert service._frame_time == 1 / service._fps

    service.set_background(True)
    assert service._frame_time == 1 / camera_module.BACKGROUND_FPS
