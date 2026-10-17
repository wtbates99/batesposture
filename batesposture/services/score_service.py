from __future__ import annotations

import math
import threading
from collections import deque
from time import monotonic

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
        self._session_start: float | None = None
        self._paused_since: float | None = None
        self._paused_duration_s: float = 0.0
        # Streak: consecutive seconds the rolling average has been above threshold
        self._streak_start: float | None = None
        self._best_streak_s: float = 0.0
        # Running session totals — O(1) per score and independent of buffer size
        self._session_count = 0
        self._session_sum = 0.0
        self._session_min = math.inf
        self._session_max = -math.inf
        # Per-second [second, sum, count] buckets for trend detection; covers
        # ten minutes regardless of how fast scores arrive
        self._trend: deque[list[float]] = deque(maxlen=600)

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
            self._paused_since = None
            self._paused_duration_s = 0.0
            self._streak_start = None
            self._best_streak_s = 0.0
            self._session_count = 0
            self._session_sum = 0.0
            self._session_min = math.inf
            self._session_max = -math.inf

    def mark_absent(self) -> None:
        """Called when no human is detected in frame.

        Breaks any active good-posture streak (time away doesn't count toward
        it) without adding a spurious zero score to the rolling buffer.
        Idempotent — safe to call every tick while the user is absent.
        """
        with self._lock:
            self._end_streak_unsafe()

    def pause_session(self) -> None:
        """Pause session duration while the user is away from the desk."""
        with self._lock:
            if self._session_start is None or self._paused_since is not None:
                return
            self._end_streak_unsafe()
            self._paused_since = monotonic()

    def resume_session(self) -> None:
        """Resume a paused session once the user returns to frame."""
        with self._lock:
            if self._session_start is None or self._paused_since is None:
                return
            self._paused_duration_s += monotonic() - self._paused_since
            self._paused_since = None

    def add_score(self, score: float) -> None:
        with self._lock:
            if self._session_start is None:
                self._session_start = monotonic()
            if self._paused_since is not None:
                self._paused_duration_s += monotonic() - self._paused_since
                self._paused_since = None
            current_time = monotonic()
            self._timestamps[self._current_index] = current_time
            self._scores[self._current_index] = score
            self._current_index = (self._current_index + 1) % self._buffer_size
            if self._current_index == 0:
                self._is_full = True
            self._session_count += 1
            self._session_sum += score
            self._session_min = min(self._session_min, score)
            self._session_max = max(self._session_max, score)
            second = math.floor(current_time)
            if self._trend and self._trend[-1][0] == second:
                self._trend[-1][1] += score
                self._trend[-1][2] += 1
            else:
                self._trend.append([second, score, 1])
            self._update_streak_unsafe(score)

    def _end_streak_unsafe(self) -> None:
        if self._streak_start is None:
            return
        elapsed = monotonic() - self._streak_start
        if elapsed > self._best_streak_s:
            self._best_streak_s = elapsed
        self._streak_start = None

    def _update_streak_unsafe(self, score: float) -> None:
        """Update streak state; must be called with self._lock held."""
        if score >= self._threshold:
            if self._streak_start is None:
                self._streak_start = monotonic()
        else:
            self._end_streak_unsafe()

    def _session_duration_unsafe(self) -> float:
        if self._session_start is None:
            return 0.0
        current_time = monotonic()
        paused = self._paused_duration_s
        if self._paused_since is not None:
            paused += current_time - self._paused_since
        return max(0.0, current_time - self._session_start - paused)

    def average(self, window_seconds: int | None = None) -> float:
        with self._lock:
            return self._average_unsafe(window_seconds)

    def _average_unsafe(self, window_seconds: int | None = None) -> float:
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

    def recent_decline(
        self,
        recent_s: int = 60,
        baseline_s: int = 60,
        baseline_offset_s: int = 240,
    ) -> float | None:
        """Return points dropped between a baseline window and the most recent window.

        Compares the mean score over the last ``recent_s`` seconds against the
        mean over a window of ``baseline_s`` seconds ending ``baseline_offset_s``
        seconds ago. A positive return value means posture has declined.

        Returns ``None`` when either window has no samples (e.g., session is
        younger than the baseline offset).
        """
        with self._lock:
            if not self._trend:
                return None
            buckets = np.array(self._trend, dtype=np.float64)
        age = monotonic() - buckets[:, 0]
        recent_mask = (age >= 0) & (age <= recent_s)
        baseline_mask = (age > baseline_offset_s) & (
            age <= baseline_offset_s + baseline_s
        )
        if not recent_mask.any() or not baseline_mask.any():
            return None

        def _mean(mask: np.ndarray) -> float:
            return buckets[mask, 1].sum() / buckets[mask, 2].sum()

        return float(_mean(baseline_mask) - _mean(recent_mask))

    def average_and_stats(self) -> tuple:
        """Return (rolling_average, session_stats_dict) in a single lock acquisition."""
        with self._lock:
            return self._average_unsafe(), self._session_stats_unsafe()

    def session_stats(self) -> dict:
        """Return stats for all scores collected since the session started."""
        with self._lock:
            return self._session_stats_unsafe()

    def _session_stats_unsafe(self) -> dict:
        if self._session_count == 0:
            return {
                "count": 0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "duration_s": 0.0,
                "best_streak_s": 0.0,
                "current_streak_s": 0.0,
            }
        current = self._current_streak_s_unsafe()
        return {
            "count": self._session_count,
            "avg": round(self._session_sum / self._session_count, 1),
            "min": round(self._session_min, 1),
            "max": round(self._session_max, 1),
            "duration_s": round(self._session_duration_unsafe(), 1),
            "best_streak_s": round(max(self._best_streak_s, current), 1),
            "current_streak_s": round(current, 1),
        }
