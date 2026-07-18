from __future__ import annotations

from unittest.mock import MagicMock

from ..services import camera_capture


def test_backend_candidates_match_desktop_platform(monkeypatch):
    monkeypatch.setattr(camera_capture.sys, "platform", "darwin")
    assert camera_capture._backend_candidates()[0] == camera_capture.cv2.CAP_AVFOUNDATION

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
