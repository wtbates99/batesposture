from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ..data.database import Database, DatabaseInitializationError
from ..services.settings_service import SettingsService


@pytest.fixture
def db_manager(tmp_path):
    settings = SettingsService.for_testing(tmp_path / "db_settings.ini")
    manager = Database(":memory:", settings.get_posture_landmarks())
    yield manager
    manager.close()


@patch("batesposture.data.database.datetime")
def test_save_pose_data(mock_datetime, db_manager):
    mock_time = datetime(2024, 1, 1, 12, 0)
    mock_datetime.now.return_value = mock_time

    mock_landmarks = MagicMock()
    mock_landmark = MagicMock(x=1.0, y=2.0, z=3.0, visibility=0.9)
    mock_landmarks.landmark = {
        enum: mock_landmark for enum in db_manager.landmark_enums
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
    assert len(landmark_results) == len(db_manager.landmark_enums)

    # Check first landmark entry
    first_landmark = landmark_results[0]
    assert first_landmark[0] == mock_time.isoformat()  # timestamp
    assert isinstance(first_landmark[1], str)  # landmark_name
    assert first_landmark[2] == 1.0  # x
    assert first_landmark[3] == 2.0  # y
    assert first_landmark[4] == 3.0  # z
    assert first_landmark[5] == 0.9  # visibility


def test_testing_db_path_uses_settings_directory(tmp_path):
    settings = SettingsService.for_testing(tmp_path / "path_settings.ini")
    db_path = Path(settings.resources.default_db_name)
    assert db_path.name == "posture_data.db"
    assert db_path.parent == tmp_path


def test_database_initialization_failure_has_stable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "batesposture.data.database.sqlite3.connect",
        MagicMock(side_effect=OSError("read-only filesystem")),
    )

    with pytest.raises(DatabaseInitializationError, match="Could not initialize"):
        Database(str(tmp_path / "unavailable" / "posture.db"), [])


def test_export_scores_csv_returns_empty_path_on_write_failure(db_manager, monkeypatch):
    monkeypatch.setattr("builtins.open", MagicMock(side_effect=OSError("disk full")))

    assert db_manager.export_scores_csv() == ""


def test_close_is_idempotent(db_manager):
    db_manager.close()
    db_manager.close()
