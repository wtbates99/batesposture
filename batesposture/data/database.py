from __future__ import annotations

import csv
import logging
import os
import sqlite3
from collections.abc import Iterable
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseInitializationError(RuntimeError):
    """Raised when the local posture database cannot be opened or initialized."""


class Database:
    """SQLite persistence for posture scores, landmarks, and dashboard history.

    Maintains three tables:

    - ``posture_scores`` (timestamp, score) — written on a configurable interval
      during tracking sessions; queryable via get_recent_stats() and exportable to CSV.
    - ``pose_landmarks`` (timestamp, landmark_name, x, y, z, visibility) — detailed
      per-frame landmark positions aligned with posture_scores timestamps.
    - ``dashboard_history`` (ts REAL PRIMARY KEY, score REAL) — lightweight score
      series for the sparkline widget; persisted when the dashboard is closed and
      reloaded when it reopens.

    Uses WAL journal mode for faster concurrent writes from background threads.
    Pending records are accumulated in memory and flushed in a single transaction
    via _flush() to minimise write amplification.
    """

    def __init__(self, db_path: str, landmark_names: Iterable[str]) -> None:
        self._conn: sqlite3.Connection | None = None
        self._cursor: sqlite3.Cursor | None = None
        self._landmark_names = list(landmark_names)
        self._pending_scores: list[tuple] = []
        self._pending_landmarks: list[tuple] = []
        try:
            if db_path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            self._conn = sqlite3.connect(db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._cursor = self._conn.cursor()
            self._create_tables()
        except (OSError, sqlite3.Error) as exc:
            if self._conn is not None:
                self._conn.close()
            raise DatabaseInitializationError(
                f"Could not initialize posture database at {db_path}: {exc}"
            ) from exc

    @classmethod
    def from_settings(cls, settings) -> Database:
        return cls(
            settings.resources.default_db_name,
            settings.get_posture_landmarks(),
        )

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise sqlite3.ProgrammingError("Database is closed")
        return self._conn

    def _active_cursor(self) -> sqlite3.Cursor:
        if self._cursor is None:
            raise sqlite3.ProgrammingError("Database is closed")
        return self._cursor

    def _create_tables(self) -> None:
        self._active_cursor().executescript("""
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

            CREATE TABLE IF NOT EXISTS dashboard_history (
                ts REAL PRIMARY KEY,
                score REAL NOT NULL
            );
            """)
        self._connection().commit()

    def save_pose_data(self, landmarks, score: float) -> bool:
        timestamp = datetime.now().isoformat()
        self._pending_scores.append((timestamp, score))

        for landmark_enum in self._landmark_names:
            lm = landmarks.landmark[landmark_enum]
            self._pending_landmarks.append(
                (timestamp, landmark_enum.name, lm.x, lm.y, lm.z, lm.visibility)
            )

        return self._flush()

    def _flush(self) -> bool:
        """Write all pending records in a single transaction."""
        if not self._pending_scores and not self._pending_landmarks:
            return True
        try:
            connection = self._connection()
            with connection:
                if self._pending_scores:
                    connection.executemany(
                        "INSERT INTO posture_scores VALUES (?, ?)",
                        self._pending_scores,
                    )
                if self._pending_landmarks:
                    connection.executemany(
                        "INSERT INTO pose_landmarks VALUES (?, ?, ?, ?, ?, ?)",
                        self._pending_landmarks,
                    )
            self._pending_scores.clear()
            self._pending_landmarks.clear()
            return True
        except sqlite3.Error:
            logger.exception("Failed to flush posture data to database")
            return False

    def get_recent_stats(self, since_iso: str) -> dict | None:
        """Return aggregate score stats since *since_iso* (ISO-format timestamp)."""
        try:
            row = (
                self._active_cursor()
                .execute(
                    """
                SELECT COUNT(*), AVG(score), MIN(score), MAX(score)
                FROM posture_scores
                WHERE timestamp >= ?
                """,
                    (since_iso,),
                )
                .fetchone()
            )
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

    def export_scores_csv(self, since_iso: str | None = None) -> str:
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
            rows = self._active_cursor().execute(query, params).fetchall()
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "score"])
                writer.writerows(rows)
            logger.info("Exported %d score rows to %s", len(rows), out_path)
            return out_path
        except (sqlite3.Error, OSError):
            logger.exception("Failed to export scores CSV")
            return ""

    def save_dashboard_history(self, scores: list[tuple[float, float]]) -> None:
        """Persist (timestamp, score) pairs for the dashboard sparkline."""
        if not scores:
            return
        try:
            connection = self._connection()
            with connection:
                connection.executemany(
                    "INSERT OR REPLACE INTO dashboard_history (ts, score) VALUES (?, ?)",
                    scores,
                )
        except sqlite3.Error:
            logger.exception("Failed to save dashboard history")

    def load_dashboard_history(self, limit: int = 120) -> list[tuple[float, float]]:
        """Return the most recent *limit* (timestamp, score) pairs, oldest first."""
        try:
            rows = (
                self._active_cursor()
                .execute(
                    "SELECT ts, score FROM dashboard_history ORDER BY ts DESC LIMIT ?",
                    (limit,),
                )
                .fetchall()
            )
            return list(reversed(rows))
        except sqlite3.Error:
            logger.exception("Failed to load dashboard history")
            return []

    def close(self) -> None:
        if self._conn is None:
            return
        self._flush()
        self._conn.close()
        self._conn = None
        self._cursor = None

    @property
    def cursor(self):
        return self._active_cursor()

    @property
    def landmark_enums(self):
        return self._landmark_names
