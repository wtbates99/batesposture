import pytest
from time import sleep, time
from ..score_history import score_history


def test_basic_score_addition():
    sh = score_history()

    test_scores = [70, 80, 90]
    for score in test_scores:
        sh.add_score(score)

    expected_average = sum(test_scores) / len(test_scores)
    actual_average = sh.get_average_score()

    assert (
        abs(actual_average - expected_average) < 0.01
    )  # Using small delta for float comparison


def test_window_timeout():
    sh = score_history()
    sh.WINDOW_SIZE = 1  # Set window to 1 second for testing
    sh.add_score(100)
    sleep(1.1)
    assert sh.get_average_score() == 0


def test_empty_history():
    sh = score_history()
    assert sh.get_average_score() == 0


def test_buffer_overflow():
    sh = score_history()
    buffer_size = sh.buffer_size

    for i in range(buffer_size + 10):
        sh.add_score(100)

    assert sh.is_buffer_full
    assert sh.current_index == 10
    assert sh.get_average_score() > 0


def test_partial_window():
    sh = score_history()

    sh.timestamps[0] = time() - 3
    sh.timestamps[1] = time() - 6
    sh.scores[0] = 100
    sh.scores[1] = 50
    sh.current_index = 2

    assert sh.get_average_score() == 100


def test_buffer_size_handling():
    sh = score_history()

    for i in range(sh.buffer_size):
        sh.add_score(100)

    assert sh.is_buffer_full
    assert sh.current_index == 0


def test_large_number_of_scores():
    sh = score_history()

    for i in range(2000):
        sh.add_score(i % 100)

    avg = sh.get_average_score()
    assert isinstance(avg, float)
    assert avg >= 0


def test_invalid_scores():
    sh = score_history()

    sh.add_score(-1000)
    sh.add_score(1000)

    avg = sh.get_average_score()
    assert isinstance(avg, float)
