import sqlite3
from datetime import datetime
import mediapipe as mp


class DBManager:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.mp_pose = mp.solutions.pose
        self._create_tables()

    def _create_tables(self):
        # Create table for overall posture scores
        self.create_table(
            "posture_scores",
            [
                ("timestamp", "DATETIME"),
                ("score", "FLOAT"),
            ],
        )

        # Create table for individual landmark positions
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

    def create_table(self, table_name: str, columns: list[tuple[str, str]]):
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join([f'{col[0]} {col[1]}' for col in columns])})"
        )
        self.conn.commit()

    def insert(self, table_name: str, values: list[tuple]):
        placeholders = ", ".join(["?" for _ in values[0]])
        self.cursor.executemany(
            f"INSERT INTO {table_name} VALUES ({placeholders})",
            values,
        )
        self.conn.commit()

    def save_pose_data(self, landmarks, score):
        timestamp = datetime.now().isoformat()

        # Save overall score
        self.insert("posture_scores", [(timestamp, score)])

        # Save landmark positions with names
        landmark_data = []
        for idx, landmark in enumerate(landmarks.landmark):
            # Get the landmark name from the enum
            landmark_name = self.mp_pose.PoseLandmark(idx).name
            landmark_data.append(
                (
                    timestamp,
                    landmark_name,
                    landmark.x,
                    landmark.y,
                    landmark.z,
                    landmark.visibility,
                )
            )
        self.insert("pose_landmarks", landmark_data)

    def close(self):
        self.conn.close()
