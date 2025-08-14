from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


from database import Database


@pytest.fixture
def db_manager():
    manager = Database(":memory:")
    yield manager
    manager.close()


@patch("database.datetime")
def test_save_pose_data(mock_datetime, db_manager):
    mock_time = datetime(2024, 1, 1, 12, 0)
    mock_datetime.now.return_value = mock_time

    mock_landmarks = MagicMock()
    mock_landmark = MagicMock(x=1.0, y=2.0, z=3.0, visibility=0.9)
    mock_landmarks.landmark = {
        enum: mock_landmark for enum in db_manager.posture_landmarks
    }

    # Test saving pose data
    test_score = 0.85
    db_manager.save_pose_data(mock_landmarks, test_score)

    # Verify score was saved
    cursor = db_manager.cursor.execute("SELECT * FROM posture_scores")
    score_result = cursor.fetchone()
    assert score_result[0] == mock_time.isoformat()
    assert score_result[1] == test_score

    # Verify landmarks were saved
    cursor = db_manager.cursor.execute("SELECT * FROM pose_landmarks")
    landmark_results = cursor.fetchall()
    assert len(landmark_results) == len(db_manager.posture_landmarks)

    # Check first landmark entry
    first_landmark = landmark_results[0]
    assert first_landmark[0] == mock_time.isoformat()  # timestamp
    assert isinstance(first_landmark[1], str)  # landmark_name
    assert first_landmark[2] == 1.0  # x
    assert first_landmark[3] == 2.0  # y
    assert first_landmark[4] == 3.0  # z
    assert first_landmark[5] == 0.9  # visibility
