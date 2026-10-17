from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable, Iterator
from threading import Event, Thread
from typing import Any

import cv2

from .camera_capture import open_camera
from .settings_service import SettingsService

logger = logging.getLogger(__name__)

FrameCallback = Callable[[Any], Any]

# Posture changes over seconds, so with no dashboard open a few frames per
# second is plenty and inference cost drops by the ratio to the full rate.
BACKGROUND_FPS = 2


class CameraService:
    """Background camera reader that streams frames via callback."""

    def __init__(self, settings: SettingsService) -> None:
        self._settings = settings
        self._camera_id = settings.runtime.default_camera_id
        self._fps = settings.runtime.default_fps
        self._background = True
        self._frame_time = self._compute_frame_time()
        self._cap: cv2.VideoCapture | None = None
        self._is_running = Event()
        self._paused = Event()
        self._thread: Thread | None = None
        self._callback: FrameCallback | None = None
        self._on_processed: Callable[[], None] | None = None
        self._latest_frame = None
        self._latest_score = 0.0
        self._latest_pose_results = None
        self._frame_seq = 0
        self._settings_lock = threading.Lock()
        self._processing_lock = threading.Lock()

    def start(
        self,
        callback: FrameCallback | None = None,
        on_processed: Callable[[], None] | None = None,
    ) -> bool:
        """Start capturing; ``on_processed`` runs on the capture thread per frame."""
        if self._is_running.is_set():
            return False
        self._callback = callback
        self._on_processed = on_processed
        self._cap = open_camera(self._camera_id)
        if self._cap is None:
            return False
        runtime = self._settings.runtime
        # Ask the driver for the processing size up front instead of resizing
        # every frame, and keep only the newest frame so slow polling isn't laggy.
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, runtime.frame_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, runtime.frame_height)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._paused.clear()
        self._is_running.set()
        self._thread = Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Camera %s started at %d FPS", self._camera_id, self._fps)
        return True

    def stop(self) -> None:
        self._is_running.clear()
        thread = self._thread
        capture = self._cap
        if thread and thread != threading.current_thread():
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning("Camera thread did not stop within 2 seconds")
        if capture:
            capture.release()
        self._cap = None
        self._thread = None
        self._paused.clear()
        logger.info("Camera stopped")

    def reload_settings(self) -> None:
        runtime = self._settings.runtime
        with self._settings_lock:
            self._camera_id = runtime.default_camera_id
            self._fps = runtime.default_fps
            self._frame_time = self._compute_frame_time()

    def set_background(self, background: bool) -> None:
        """Process at BACKGROUND_FPS when nothing displays frames, else full rate."""
        with self._settings_lock:
            self._background = background
            self._frame_time = self._compute_frame_time()

    def _compute_frame_time(self) -> float:
        fps = max(self._fps, 1)
        if self._background:
            fps = min(fps, BACKGROUND_FPS)
        return 1 / fps

    @contextlib.contextmanager
    def pause_processing(self) -> Iterator[None]:
        """Pause the capture loop between frames for safe settings reload.

        Use this when reloading settings (fps, resolution, camera ID) or
        reloading ScoreService state during live tracking. The method:

        1. Sets the _paused event so the loop idles at the top of its next iteration.
        2. Acquires-then-releases the processing lock to wait for any active callback
           invocation to finish before mutating detector / scoring settings.
        3. Yields — callers may safely mutate shared state here.
        4. Clears _paused on exit, resuming normal capture.

        Example::

            with camera_service.pause_processing():
                camera_service.reload_settings()
                score_service.reload(settings)
        """
        self._paused.set()
        # Acquire and immediately release the lock to wait for any active callback.
        with self._processing_lock:
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

            start_time = time.monotonic()
            try:
                if self._cap is None:
                    break
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("Failed to read frame from camera; stopping capture")
                    self.stop()
                    break

                self._publish(frame)

            except (cv2.error, OSError) as exc:
                logger.error("Camera I/O error in capture loop; stopping: %s", exc)
                self.stop()
                break
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected non-IO error in capture loop; stopping")
                self.stop()
                break

            processing_time = time.monotonic() - start_time
            # _frame_time is a float; CPython's GIL makes this read atomic, and a
            # rate change landing mid-iteration only affects this one sleep.
            if processing_time < self._frame_time:
                time.sleep(self._frame_time - processing_time)

    def _publish(self, frame) -> None:
        """Run the frame callback, store its result, and notify the listener."""
        latest_score = 0.0
        pose_results = None
        with self._processing_lock:
            # process_frame is already infallible (returns (frame, 0.0, None) on error)
            if self._callback:
                processed = self._callback(frame)
                if isinstance(processed, tuple) and len(processed) == 3:
                    frame, latest_score, pose_results = processed

        with self._settings_lock:
            self._latest_frame = frame
            self._latest_score = latest_score
            self._latest_pose_results = pose_results
            self._frame_seq += 1
        if self._on_processed:
            self._on_processed()

    def get_latest(self) -> tuple[int, Any, float, Any]:
        """Return (sequence, frame, score, pose_results) from one processed frame.

        The sequence number increments per processed frame so callers can skip
        results they have already consumed.
        """
        with self._settings_lock:
            return (
                self._frame_seq,
                self._latest_frame,
                self._latest_score,
                self._latest_pose_results,
            )
