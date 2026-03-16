from __future__ import annotations

import contextlib
import logging
import threading
import time
from threading import Event, Thread
from typing import Any, Callable, Iterator, Optional

import cv2

from .settings_service import SettingsService

logger = logging.getLogger(__name__)

FrameCallback = Callable[[Any], Any]


class CameraService:
    """Background camera reader that streams frames via callback."""

    def __init__(self, settings: SettingsService) -> None:
        self._settings = settings
        self._camera_id = settings.runtime.default_camera_id
        self._fps = settings.runtime.default_fps
        self._frame_time = 1 / max(self._fps, 1)
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_running = Event()
        self._paused = Event()
        self._thread: Optional[Thread] = None
        self._callback: Optional[FrameCallback] = None
        self._latest_frame = None
        self._latest_score = 0.0
        self._latest_pose_results = None
        self._lock = threading.Lock()

    def start(self, callback: Optional[FrameCallback] = None) -> bool:
        if self._is_running.is_set():
            return False
        self._callback = callback
        self._cap = cv2.VideoCapture(self._camera_id)
        if not self._cap.isOpened():
            logger.error("Failed to open camera %s", self._camera_id)
            return False
        self._is_running.set()
        self._thread = Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Camera %s started at %d FPS", self._camera_id, self._fps)
        return True

    def stop(self) -> None:
        self._is_running.clear()
        if self._thread and self._thread != threading.current_thread():
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
        self._cap = None
        self._thread = None
        logger.info("Camera stopped")

    def reload_settings(self) -> None:
        runtime = self._settings.runtime
        with self._lock:
            self._camera_id = runtime.default_camera_id
            self._fps = runtime.default_fps
            self._frame_time = 1 / max(self._fps, 1)

    @contextlib.contextmanager
    def pause_processing(self) -> Iterator[None]:
        """Pause the capture loop between frames for safe settings reload.

        Use this when reloading settings (fps, resolution, camera ID) or
        reloading ScoreService state during live tracking. The method:

        1. Sets the _paused event so the loop idles at the top of its next iteration.
        2. Acquires-then-releases the frame lock to wait for any active callback
           invocation to finish (process_frame is infallible, so this resolves quickly).
        3. Yields — callers may safely mutate shared state here.
        4. Clears _paused on exit, resuming normal capture.

        Example::

            with camera_service.pause_processing():
                camera_service.reload_settings()
                score_service.reload(settings)
        """
        self._paused.set()
        # Acquire and immediately release the lock to wait for any active callback
        with self._lock:
            pass
        try:
            yield
        finally:
            self._paused.clear()

    def _capture_loop(self) -> None:
        while self._is_running.is_set():
            if self._paused.is_set():
                time.sleep(0.01)
                continue

            start_time = time.time()
            try:
                if self._cap is None:
                    break
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("Failed to read frame from camera; stopping capture")
                    self.stop()
                    break

                latest_score = 0.0
                pose_results = None
                # process_frame is already infallible (returns (frame, 0.0, None) on error)
                if self._callback:
                    processed = self._callback(frame)
                    if isinstance(processed, tuple) and len(processed) == 3:
                        frame, latest_score, pose_results = processed

                with self._lock:
                    self._latest_frame = frame
                    self._latest_score = latest_score
                    self._latest_pose_results = pose_results

            except (cv2.error, OSError) as exc:
                logger.error("Camera I/O error in capture loop; stopping: %s", exc)
                self.stop()
                break
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected non-IO error in capture loop; stopping")
                self.stop()
                break

            processing_time = time.time() - start_time
            with self._lock:
                frame_time = self._frame_time
            if processing_time < frame_time:
                time.sleep(frame_time - processing_time)

    def get_latest_frame(self):
        with self._lock:
            return self._latest_frame, self._latest_score

    def get_latest_pose_results(self):
        with self._lock:
            return self._latest_pose_results
