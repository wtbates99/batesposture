from time import sleep, time

import pytest

from ..score_history import score_history


@pytest.fixture
def sh():
    return score_history()


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
