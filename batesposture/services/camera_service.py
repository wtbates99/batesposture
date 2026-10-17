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
        self._stopping = Event()
        self._paused = Event()
        self._thread: Thread | None = None
        self._callback: FrameCallback | None = None
        self._on_processed: Callable[[], None] | None = None
        self._on_failed: Callable[[], None] | None = None
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
        on_failed: Callable[[], None] | None = None,
    ) -> bool:
        """Start capturing on a background thread; False if already running.

        Opening a camera takes over a second on macOS, so it happens on the
        capture thread. ``on_processed`` runs there after each frame and
        ``on_failed`` if the camera cannot be opened or stops delivering frames.
        """
        if self._is_running.is_set():
            return False
        self._callback = callback
        self._on_processed = on_processed
        self._on_failed = on_failed
        self._paused.clear()
        self._stopping.clear()
        self._is_running.set()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        capture = open_camera(self._camera_id)
        if capture is None:
            self._is_running.clear()
            self._notify_failed()
            return
        # Keep only the newest frame so low-rate reads aren't stale. Frame size
        # is left to the driver: setting it restarts the macOS capture session
        # (~1.2 s) and inference cost doesn't depend on it.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = capture
        if not self._is_running.is_set():  # stopped while the camera was opening
            self._cap = None
            capture.release()
            return
        logger.info("Camera %s started at %d FPS", self._camera_id, self._fps)
        self._capture_loop()

    def _notify_failed(self) -> None:
        if self._on_failed:
            self._on_failed()

    def stop(self) -> None:
        self._is_running.clear()
        self._stopping.set()
        thread = self._thread
        if thread and thread != threading.current_thread():
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning("Camera thread did not stop within 2 seconds")
        # Read after the join: the thread may have finished opening meanwhile.
        capture = self._cap
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
                    self._notify_failed()
                    break

                self._publish(frame)

            except (cv2.error, OSError) as exc:
                logger.error("Camera I/O error in capture loop; stopping: %s", exc)
                self.stop()
                self._notify_failed()
                break
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected non-IO error in capture loop; stopping")
                self.stop()
                break

            processing_time = time.monotonic() - start_time
            # _frame_time is a float; CPython's GIL makes this read atomic, and a
            # rate change landing mid-iteration only affects this one sleep.
            if processing_time < self._frame_time:
                # Interruptible, so stop() isn't held up by a 500 ms idle gap
                self._stopping.wait(self._frame_time - processing_time)

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
