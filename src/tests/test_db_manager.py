import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from ..db_manager import DBManager


@pytest.fixture
def db_manager():
    # Use in-memory database for testing
    manager = DBManager(":memory:")
    yield manager
    manager.close()


def test_init(db_manager):
    assert isinstance(db_manager.conn, sqlite3.Connection)
    assert isinstance(db_manager.cursor, sqlite3.Cursor)
    assert hasattr(db_manager, "posture_landmarks")


def test_create_table(db_manager):
    # Test creating a new table
    test_columns = [("test_col1", "TEXT"), ("test_col2", "INTEGER")]
    db_manager.create_table("test_table", test_columns)

    # Verify table exists
    cursor = db_manager.cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
    )
    assert cursor.fetchone() is not None


def test_insert(db_manager):
    # Create test table
    db_manager.create_table("test_table", [("col1", "TEXT"), ("col2", "INTEGER")])

    # Test inserting values
    test_values = [("test1", 1), ("test2", 2)]
    db_manager.insert("test_table", test_values)

    # Verify inserted values
    cursor = db_manager.cursor.execute("SELECT * FROM test_table")
    results = cursor.fetchall()
    assert len(results) == 2
    assert results == test_values


@patch("src.db_manager.datetime")
def test_save_pose_data(mock_datetime, db_manager):
    # Mock datetime
    mock_time = datetime(2024, 1, 1, 12, 0)
    mock_datetime.now.return_value = mock_time

    # Create mock landmarks
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


def test_close(db_manager):
    db_manager.close()
    # Verify connection is closed by attempting to execute a query
    with pytest.raises(sqlite3.ProgrammingError):
        db_manager.cursor.execute("SELECT 1")
