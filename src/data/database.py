from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable


class Database:
    """SQLite persistence for posture scores and landmarks."""

    def __init__(self, db_path: str, landmark_names: Iterable[str]) -> None:
        self._conn = sqlite3.connect(db_path)
        self._cursor = self._conn.cursor()
        self._landmark_names = list(landmark_names)
        self._create_tables()

    def _create_tables(self) -> None:
        self.create_table(
            "posture_scores",
            [
                ("timestamp", "DATETIME"),
                ("score", "FLOAT"),
            ],
        )

        self.create_table(
            "pose_landmarks",
            [
                ("timestamp", "DATETIME"),
                ("landmark_name", "TEXT"),
                ("x", "FLOAT"),
                ("y", "FLOAT"),
                ("z", "FLOAT"),
                ("visibility", "FLOAT"),
            ],
        )

    def create_table(self, table_name: str, columns: list[tuple[str, str]]) -> None:
        definitions = ", ".join(f"{name} {type_}" for name, type_ in columns)
        self._cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({definitions})")
        self._conn.commit()

    def insert(self, table_name: str, values: list[tuple]) -> None:
        placeholders = ", ".join("?" for _ in values[0])
        self._cursor.executemany(
            f"INSERT INTO {table_name} VALUES ({placeholders})",
            values,
        )
        self._conn.commit()

    def save_pose_data(self, landmarks, score: float) -> None:
        timestamp = datetime.now().isoformat()
        self.insert("posture_scores", [(timestamp, score)])

        landmark_records = []
        for landmark_enum in self._landmark_names:
            landmark = landmarks.landmark[landmark_enum]
            landmark_records.append(
                (
                    timestamp,
                    landmark_enum.name,
                    landmark.x,
                    landmark.y,
                    landmark.z,
                    landmark.visibility,
                )
            )
        self.insert("pose_landmarks", landmark_records)

    def close(self) -> None:
        self._conn.close()

    @property
    def cursor(self):
        return self._cursor

    @property
    def landmark_enums(self):
        return self._landmark_names
