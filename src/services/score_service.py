from __future__ import annotations

from time import time
from typing import Optional

import numpy as np

from .settings_service import SettingsService


class ScoreService:
    """Rolling buffer for recent posture scores."""

    def __init__(self, settings: SettingsService) -> None:
        ml_settings = settings.ml
        self._buffer_size = ml_settings.score_buffer_size
        self._timestamps = np.zeros(self._buffer_size, dtype=np.float64)
        self._scores = np.zeros(self._buffer_size, dtype=np.float32)
        self._current_index = 0
        self._is_full = False
        self._window_size = ml_settings.score_window_size
        self._threshold = ml_settings.score_threshold

    @property
    def threshold(self) -> int:
        return self._threshold

    def reload(self, settings: SettingsService) -> None:
        ml_settings = settings.ml
        if ml_settings.score_buffer_size != self._buffer_size:
            self._buffer_size = ml_settings.score_buffer_size
            self._timestamps = np.zeros(self._buffer_size, dtype=np.float64)
            self._scores = np.zeros(self._buffer_size, dtype=np.float32)
            self._current_index = 0
            self._is_full = False
        self._window_size = ml_settings.score_window_size
        self._threshold = ml_settings.score_threshold

    def add_score(self, score: float) -> None:
        current_time = time()
        self._timestamps[self._current_index] = current_time
        self._scores[self._current_index] = score
        self._current_index = (self._current_index + 1) % self._buffer_size
        if self._current_index == 0:
            self._is_full = True

    def average(self, window_seconds: Optional[int] = None) -> float:
        window = window_seconds or self._window_size
        current_time = time()
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
