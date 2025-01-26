from time import sleep, time

import numpy as np
import pytest

from ..score_history import ScoreHistory


@pytest.fixture
def sh():
    return ScoreHistory()


class TestScoreHistory:
    @pytest.mark.parametrize(
        "scores,expected_average",
        [
            ([70, 80, 90], 80),
            ([], 0),
            ([100], 100),
        ],
    )
    def test_average_calculation(self, sh, scores, expected_average):
        for score in scores:
            sh.add_score(score)
        assert abs(sh.get_average_score() - expected_average) < 0.01

    def test_window_timeout(self, sh):
        sh.WINDOW_SIZE = 1
        sh.add_score(100)
        sleep(1.1)
        assert sh.get_average_score() == 0

    def test_partial_window(self, sh):
        sh.timestamps[0] = time() - 3
        sh.timestamps[1] = time() - 6
        sh.scores[0] = 100
        sh.scores[1] = 50
        sh.current_index = 2
        assert sh.get_average_score() == 100

    @pytest.mark.parametrize(
        "num_scores",
        [
            1000,  # Normal case
            2000,  # Large number of scores
        ],
    )
    def test_buffer_handling(self, sh, num_scores):
        for i in range(num_scores):
            sh.add_score(i % 100)

        assert isinstance(sh.get_average_score(), float)
        assert sh.get_average_score() >= 0

        if num_scores >= sh.buffer_size:
            assert sh.is_buffer_full
            assert sh.current_index == num_scores % sh.buffer_size

    @pytest.mark.parametrize("score", [-1000, 1000])
    def test_boundary_scores(self, sh, score):
        sh.add_score(score)
        assert isinstance(sh.get_average_score(), float)

    def test_score_threshold_exists(self, sh):
        """Test that SCORE_THRESHOLD is properly initialized"""
        assert hasattr(sh, "SCORE_THRESHOLD")
        assert sh.SCORE_THRESHOLD == 65

    def test_buffer_initialization(self, sh):
        """Test initial state of the buffer"""
        assert sh.current_index == 0
        assert sh.is_buffer_full is False
        assert len(sh.timestamps) == sh.buffer_size
        assert len(sh.scores) == sh.buffer_size
        assert np.all(sh.timestamps == 0)
        assert np.all(sh.scores == 0)

    def test_window_size_exists(self, sh):
        """Test that WINDOW_SIZE is properly initialized"""
        assert hasattr(sh, "WINDOW_SIZE")
        assert sh.WINDOW_SIZE == 5

    def test_buffer_wraparound(self, sh):
        """Test that buffer properly wraps around when full"""
        # Fill buffer exactly to capacity
        for i in range(sh.buffer_size):
            sh.add_score(100)

        assert sh.is_buffer_full
        assert sh.current_index == 0

        # Add one more score
        sh.add_score(200)
        assert sh.current_index == 1
        assert sh.scores[0] == 200

    def test_average_with_mixed_window(self, sh):
        """Test average calculation with some scores inside and outside the window"""
        # Add old scores (outside window)
        sh.timestamps[0] = time() - 10
        sh.timestamps[1] = time() - 8
        sh.scores[0] = 50
        sh.scores[1] = 60

        # Add recent scores (inside window)
        sh.timestamps[2] = time() - 2
        sh.timestamps[3] = time() - 1
        sh.scores[2] = 70
        sh.scores[3] = 80

        sh.current_index = 4

        # Should only average the recent scores
        assert abs(sh.get_average_score() - 75) < 0.01
