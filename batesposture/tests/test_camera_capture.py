from __future__ import annotations

from unittest.mock import MagicMock

from ..services import camera_capture


def test_backend_candidates_match_desktop_platform(monkeypatch):
    monkeypatch.setattr(camera_capture.sys, "platform", "darwin")
    assert (
        camera_capture._backend_candidates()[0] == camera_capture.cv2.CAP_AVFOUNDATION
    )

    monkeypatch.setattr(camera_capture.sys, "platform", "win32")
    assert camera_capture._backend_candidates()[:2] == (
        camera_capture.cv2.CAP_MSMF,
        camera_capture.cv2.CAP_DSHOW,
    )

    monkeypatch.setattr(camera_capture.sys, "platform", "linux")
    assert camera_capture._backend_candidates()[0] == camera_capture.cv2.CAP_V4L2


def test_open_camera_releases_failed_backend_before_fallback(monkeypatch):
    failed = MagicMock()
    failed.isOpened.return_value = False
    opened = MagicMock()
    opened.isOpened.return_value = True
    video_capture = MagicMock(side_effect=[failed, opened])
    monkeypatch.setattr(camera_capture.cv2, "VideoCapture", video_capture)
    monkeypatch.setattr(
        camera_capture,
        "_backend_candidates",
        lambda: (camera_capture.cv2.CAP_V4L2, camera_capture.cv2.CAP_ANY),
    )

    result = camera_capture.open_camera(2)

    assert result is opened
    failed.release.assert_called_once_with()
    opened.release.assert_not_called()
    assert video_capture.call_args_list[0].args == (2, camera_capture.cv2.CAP_V4L2)
    assert video_capture.call_args_list[1].args == (2,)


def test_discover_camera_ids_returns_only_openable_cameras(monkeypatch):
    captures = {
        0: MagicMock(),
        1: None,
        2: MagicMock(),
    }
    monkeypatch.setattr(
        camera_capture,
        "open_camera",
        lambda camera_id: captures.get(camera_id),
    )

    discovered = camera_capture.discover_camera_ids(max_index=3)

    assert discovered == [0, 2]
    captures[0].release.assert_called_once()
    captures[2].release.assert_called_once()


def test_discover_camera_ids_preserves_active_camera_without_reopening(monkeypatch):
    open_camera = MagicMock(return_value=None)
    monkeypatch.setattr(camera_capture, "open_camera", open_camera)

    discovered = camera_capture.discover_camera_ids(max_index=2, active_camera_id=1)

    assert discovered == [1]
    open_camera.assert_called_once_with(0)
