from __future__ import annotations

import csv
import logging
import os
import sqlite3
from datetime import datetime
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


class Database:
    """SQLite persistence for posture scores and landmarks."""

    def __init__(self, db_path: str, landmark_names: Iterable[str]) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")  # faster concurrent writes
        self._cursor = self._conn.cursor()
        self._landmark_names = list(landmark_names)
        self._pending_scores: list[tuple] = []
        self._pending_landmarks: list[tuple] = []
        self._create_tables()

    def _create_tables(self) -> None:
        self._cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS posture_scores (
                timestamp DATETIME,
                score FLOAT
            );
            CREATE INDEX IF NOT EXISTS idx_scores_timestamp
                ON posture_scores (timestamp);

            CREATE TABLE IF NOT EXISTS pose_landmarks (
                timestamp DATETIME,
                landmark_name TEXT,
                x FLOAT,
                y FLOAT,
                z FLOAT,
                visibility FLOAT
            );
            CREATE INDEX IF NOT EXISTS idx_landmarks_timestamp
                ON pose_landmarks (timestamp);
            """
        )
        self._conn.commit()

    def save_pose_data(self, landmarks, score: float) -> None:
        timestamp = datetime.now().isoformat()
        self._pending_scores.append((timestamp, score))

        for landmark_enum in self._landmark_names:
            lm = landmarks.landmark[landmark_enum]
            self._pending_landmarks.append(
                (timestamp, landmark_enum.name, lm.x, lm.y, lm.z, lm.visibility)
            )

        self._flush()

    def _flush(self) -> None:
        """Write all pending records in a single transaction."""
        if not self._pending_scores and not self._pending_landmarks:
            return
        try:
            with self._conn:
                if self._pending_scores:
                    self._conn.executemany(
                        "INSERT INTO posture_scores VALUES (?, ?)",
                        self._pending_scores,
                    )
                if self._pending_landmarks:
                    self._conn.executemany(
                        "INSERT INTO pose_landmarks VALUES (?, ?, ?, ?, ?, ?)",
                        self._pending_landmarks,
                    )
            self._pending_scores.clear()
            self._pending_landmarks.clear()
        except sqlite3.Error:
            logger.exception("Failed to flush posture data to database")

    def get_recent_stats(self, since_iso: str) -> Optional[dict]:
        """Return aggregate score stats since *since_iso* (ISO-format timestamp)."""
        try:
            row = self._cursor.execute(
                """
                SELECT COUNT(*), AVG(score), MIN(score), MAX(score)
                FROM posture_scores
                WHERE timestamp >= ?
                """,
                (since_iso,),
            ).fetchone()
            if row and row[0]:
                return {
                    "count": row[0],
                    "avg": round(row[1], 1),
                    "min": round(row[2], 1),
                    "max": round(row[3], 1),
                }
        except sqlite3.Error:
            logger.exception("Failed to query recent stats")
        return None

    def export_scores_csv(self, since_iso: Optional[str] = None) -> str:
        """Write posture scores to a timestamped CSV in the user's home directory.

        Returns the path to the created file.
        """
        filename = f"posture_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        out_path = os.path.join(os.path.expanduser("~"), filename)
        query = "SELECT timestamp, score FROM posture_scores"
        params: tuple = ()
        if since_iso:
            query += " WHERE timestamp >= ?"
            params = (since_iso,)
        query += " ORDER BY timestamp"
        try:
            rows = self._cursor.execute(query, params).fetchall()
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "score"])
                writer.writerows(rows)
            logger.info("Exported %d score rows to %s", len(rows), out_path)
            return out_path
        except (sqlite3.Error, OSError):
            logger.exception("Failed to export scores CSV")
            return ""

    def close(self) -> None:
        self._flush()
        self._conn.close()

    @property
    def cursor(self):
        return self._cursor

    @property
    def landmark_enums(self):
        return self._landmark_names
