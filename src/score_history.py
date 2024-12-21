import numpy as np
from time import time


class score_history:
    def __init__(self):
        self.buffer_size = 1000  # Adjust based on expected updates per window
        self.timestamps = np.zeros(self.buffer_size, dtype=np.float64)
        self.scores = np.zeros(self.buffer_size, dtype=np.float32)
        self.current_index = 0
        self.is_buffer_full = False
        self.WINDOW_SIZE = 5  # 15 seconds
        self.SCORE_THRESHOLD = 65
        self.NOTIFICATION_COOLDOWN = 60
        self.last_notification_time = 0

    def add_score(self, score):
        current_time = time()

        # Add new score to buffer
        self.timestamps[self.current_index] = current_time
        self.scores[self.current_index] = score

        # Update buffer status
        self.current_index = (self.current_index + 1) % self.buffer_size
        if self.current_index == 0:
            self.is_buffer_full = True

    def get_average_score(self):
        current_time = time()
        if not self.is_buffer_full and self.current_index == 0:
            return 0

        # Calculate which entries are within the time window
        valid_mask = current_time - self.timestamps <= self.WINDOW_SIZE
        if self.is_buffer_full:
            valid_scores = self.scores[valid_mask]
        else:
            valid_scores = self.scores[: self.current_index][
                valid_mask[: self.current_index]
            ]

        return np.mean(valid_scores) if len(valid_scores) > 0 else 0
