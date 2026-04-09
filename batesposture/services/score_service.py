from __future__ import annotations

import threading
from time import monotonic
from typing import Optional

import numpy as np

from .settings_service import SettingsService


class ScoreService:
    """Thread-safe rolling buffer for posture scores with session statistics and streak tracking.

    All public methods acquire a threading.Lock before reading or mutating internal state,
    making it safe to call add_score() from the camera thread while average() and
    session_stats() are read from the Qt main thread.
    """

    def __init__(self, settings: SettingsService) -> None:
        ml_settings = settings.ml
        self._lock = threading.Lock()
        self._buffer_size = ml_settings.score_buffer_size
        self._timestamps = np.zeros(self._buffer_size, dtype=np.float64)
        self._scores = np.zeros(self._buffer_size, dtype=np.float32)
        self._current_index = 0
        self._is_full = False
        self._window_size = ml_settings.score_window_size
        self._threshold = ml_settings.score_threshold
        self._session_start: Optional[float] = None
        # Streak: consecutive seconds the rolling average has been above threshold
        self._streak_start: Optional[float] = None
        self._best_streak_s: float = 0.0

    @property
    def threshold(self) -> int:
        with self._lock:
            return self._threshold

    @property
    def current_streak_s(self) -> float:
        """Seconds the posture has been consistently good this streak."""
        with self._lock:
            if self._streak_start is None:
                return 0.0
            return monotonic() - self._streak_start

    @property
    def best_streak_s(self) -> float:
        with self._lock:
            return max(self._best_streak_s, self._current_streak_s_unsafe())

    def _current_streak_s_unsafe(self) -> float:
        """Return current streak duration; must be called with self._lock held."""
        if self._streak_start is None:
            return 0.0
        return monotonic() - self._streak_start

    def reload(self, settings: SettingsService) -> None:
        ml_settings = settings.ml
        with self._lock:
            if ml_settings.score_buffer_size != self._buffer_size:
                self._buffer_size = ml_settings.score_buffer_size
                self._timestamps = np.zeros(self._buffer_size, dtype=np.float64)
                self._scores = np.zeros(self._buffer_size, dtype=np.float32)
                self._current_index = 0
                self._is_full = False
            self._window_size = ml_settings.score_window_size
            self._threshold = ml_settings.score_threshold

    def reset_session(self) -> None:
        """Mark the start of a new tracking session and reset streaks."""
        with self._lock:
            self._session_start = monotonic()
            self._streak_start = None
            self._best_streak_s = 0.0

    def mark_absent(self) -> None:
        """Called when no human is detected in frame.

        Breaks any active good-posture streak (time away doesn't count toward
        it) without adding a spurious zero score to the rolling buffer.
        Idempotent — safe to call every tick while the user is absent.
        """
        with self._lock:
            if self._streak_start is not None:
                elapsed = monotonic() - self._streak_start
                if elapsed > self._best_streak_s:
                    self._best_streak_s = elapsed
                self._streak_start = None

    def add_score(self, score: float) -> None:
        with self._lock:
            if self._session_start is None:
                self._session_start = monotonic()
            current_time = monotonic()
            self._timestamps[self._current_index] = current_time
            self._scores[self._current_index] = score
            self._current_index = (self._current_index + 1) % self._buffer_size
            if self._current_index == 0:
                self._is_full = True
            self._update_streak_unsafe(score)

    def _update_streak_unsafe(self, score: float) -> None:
        """Update streak state; must be called with self._lock held."""
        if score >= self._threshold:
            if self._streak_start is None:
                self._streak_start = monotonic()
        else:
            if self._streak_start is not None:
                elapsed = monotonic() - self._streak_start
                if elapsed > self._best_streak_s:
                    self._best_streak_s = elapsed
            self._streak_start = None

    def average(self, window_seconds: Optional[int] = None) -> float:
        with self._lock:
            return self._average_unsafe(window_seconds)

    def _average_unsafe(self, window_seconds: Optional[int] = None) -> float:
        """Compute rolling average; must be called with self._lock held."""
        window = window_seconds or self._window_size
        current_time = monotonic()
        if not self._is_full and self._current_index == 0:
            return 0.0
        valid_mask = current_time - self._timestamps <= window
        if self._is_full:
            valid_scores = self._scores[valid_mask]
        else:
            valid_scores = self._scores[: self._current_index][
                valid_mask[: self._current_index]
            ]
        return float(np.mean(valid_scores)) if len(valid_scores) else 0.0

    def average_and_stats(self) -> tuple:
        """Return (rolling_average, session_stats_dict) in a single lock acquisition."""
        with self._lock:
            avg = self._average_unsafe()
            if not self._is_full and self._current_index == 0:
                return avg, {
                    "count": 0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "duration_s": 0.0,
                    "best_streak_s": 0.0,
                    "current_streak_s": 0.0,
                }
            cutoff = self._session_start if self._session_start is not None else 0.0
            if self._is_full:
                mask = self._timestamps >= cutoff
                scores = self._scores[mask]
            else:
                ts_slice = self._timestamps[: self._current_index]
                sc_slice = self._scores[: self._current_index]
                scores = sc_slice[ts_slice >= cutoff]
            if len(scores) == 0:
                return avg, {
                    "count": 0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "duration_s": 0.0,
                    "best_streak_s": 0.0,
                    "current_streak_s": 0.0,
                }
            duration = monotonic() - self._session_start if self._session_start else 0.0
            best = max(self._best_streak_s, self._current_streak_s_unsafe())
            current = self._current_streak_s_unsafe()
            return avg, {
                "count": int(len(scores)),
                "avg": float(round(np.mean(scores), 1)),
                "min": float(round(np.min(scores), 1)),
                "max": float(round(np.max(scores), 1)),
                "duration_s": round(duration, 1),
                "best_streak_s": round(best, 1),
                "current_streak_s": round(current, 1),
            }

    def session_stats(self) -> dict:
        """Return stats for all scores collected since the session started."""
        with self._lock:
            if not self._is_full and self._current_index == 0:
                return {
                    "count": 0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "duration_s": 0.0,
                    "best_streak_s": 0.0,
                    "current_streak_s": 0.0,
                }

            cutoff = self._session_start if self._session_start is not None else 0.0

            if self._is_full:
                mask = self._timestamps >= cutoff
                scores = self._scores[mask]
            else:
                ts_slice = self._timestamps[: self._current_index]
                sc_slice = self._scores[: self._current_index]
                mask = ts_slice >= cutoff
                scores = sc_slice[mask]

            if len(scores) == 0:
                return {
                    "count": 0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "duration_s": 0.0,
                    "best_streak_s": 0.0,
                    "current_streak_s": 0.0,
                }

            duration = monotonic() - self._session_start if self._session_start else 0.0
            best = max(self._best_streak_s, self._current_streak_s_unsafe())
            current = self._current_streak_s_unsafe()
            return {
                "count": int(len(scores)),
                "avg": float(round(np.mean(scores), 1)),
                "min": float(round(np.min(scores), 1)),
                "max": float(round(np.max(scores), 1)),
                "duration_s": round(duration, 1),
                "best_streak_s": round(best, 1),
                "current_streak_s": round(current, 1),
            }
