from __future__ import annotations

import threading
import time
from threading import Event, Thread
from typing import Any, Callable, Optional

import cv2

from .settings_service import SettingsService


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
            return False
        self._is_running.set()
        self._thread = Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._is_running.clear()
        if self._thread and self._thread != threading.current_thread():
            self._thread.join()
        if self._cap:
            self._cap.release()
        self._cap = None
        self._thread = None

    def reload_settings(self) -> None:
        runtime = self._settings.runtime
        self._camera_id = runtime.default_camera_id
        self._fps = runtime.default_fps
        self._frame_time = 1 / max(self._fps, 1)

    def _capture_loop(self) -> None:
        while self._is_running.is_set():
            start_time = time.time()
            try:
                assert self._cap is not None
                ret, frame = self._cap.read()
                if not ret:
                    print("Failed to read frame from camera")
                    self.stop()
                    break

                latest_score = 0.0
                pose_results = None
                if self._callback:
                    try:
                        processed = self._callback(frame)
                        if isinstance(processed, tuple) and len(processed) == 3:
                            frame, latest_score, pose_results = processed
                    except Exception as exc:  # noqa: BLE001 - surface capture issues
                        print(f"Error in frame callback: {exc}")

                with self._lock:
                    self._latest_frame = frame
                    self._latest_score = latest_score
                    self._latest_pose_results = pose_results

            except Exception as exc:  # noqa: BLE001 - ensure loop exits cleanly
                print(f"Error capturing frame: {exc}")
                self.stop()
                break

            processing_time = time.time() - start_time
            if processing_time < self._frame_time:
                time.sleep(self._frame_time - processing_time)

    def get_latest_frame(self):
        with self._lock:
            return self._latest_frame, self._latest_score

    def get_latest_pose_results(self):
        with self._lock:
            return self._latest_pose_results
