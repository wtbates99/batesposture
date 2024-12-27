import cv2
from threading import Thread, Event
import time


class webcam:
    def __init__(self, camera_id=0, fps=30):
        self.camera_id = camera_id
        self.cap = None
        self.is_running = Event()
        self.thread = None
        self.fps = fps
        self.frame_time = 1 / fps
        self._latest_frame = None
        self._latest_score = 0
        self._callback = None

    def start(self, callback=None):
        """Start the camera capture with optional callback for frame processing"""
        if self.is_running.is_set():
            return False

        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            return False

        self._callback = callback
        self.is_running.set()
        self.thread = Thread(target=self._update_frame)
        self.thread.daemon = True
        self.thread.start()
        return True

    def stop(self):
        """Stop the camera capture and cleanup"""
        self.is_running.clear()
        if self.thread:
            self.thread.join()
        if self.cap:
            self.cap.release()
            cv2.destroyAllWindows()
            self.cap = None
        self._latest_frame = None
        self._latest_score = 0

    def _update_frame(self):
        """Background thread for frame capture and processing"""
        while self.is_running.is_set():
            start_time = time.time()

            ret, frame = self.cap.read()
            if not ret:
                self.stop()
                break

            if self._callback:
                frame, score = self._callback(frame)
                self._latest_score = score

            self._latest_frame = frame

            processing_time = time.time() - start_time
            if processing_time < self.frame_time:
                time.sleep(self.frame_time - processing_time)

    def get_latest_frame(self):
        """Get the most recent frame and score"""
        return self._latest_frame, self._latest_score

    def __del__(self):
        """Ensure cleanup on destruction"""
        self.stop()
