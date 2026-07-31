from __future__ import annotations

import logging
import sys

import cv2

logger = logging.getLogger(__name__)


def _backend_candidates() -> tuple[int, ...]:
    """Return preferred OpenCV camera backends for the current desktop OS."""
    if sys.platform == "darwin":
        return (cv2.CAP_AVFOUNDATION, cv2.CAP_ANY)
    if sys.platform == "win32":
        return (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY)
    return (cv2.CAP_V4L2, cv2.CAP_ANY)


def open_camera(camera_id: int) -> cv2.VideoCapture | None:
    """Open a camera with native backends first, releasing every failed handle."""
    for backend in dict.fromkeys(_backend_candidates()):
        capture = (
            cv2.VideoCapture(camera_id)
            if backend == cv2.CAP_ANY
            else cv2.VideoCapture(camera_id, backend)
        )
        if capture.isOpened():
            return capture
        capture.release()
    logger.error("Failed to open camera %s on %s", camera_id, sys.platform)
    return None


def discover_camera_ids(
    max_index: int = 5, active_camera_id: int | None = None
) -> list[int]:
    """Return camera indices that can actually be opened.

    ``active_camera_id`` is included without probing because the running capture
    already proves that it exists and a second open commonly fails.
    """
    discovered: list[int] = []
    for camera_id in range(max_index):
        if camera_id == active_camera_id:
            discovered.append(camera_id)
            continue
        capture = open_camera(camera_id)
        if capture is not None:
            discovered.append(camera_id)
            capture.release()
    return discovered
