from __future__ import annotations

from mediapipe.tasks.python import vision

# MediaPipe Tasks pose API. Importing this module before PyQt6 also avoids the
# Windows DLL initialization failures seen when Qt loads first.
PoseLandmark = vision.PoseLandmark
POSE_CONNECTIONS = vision.PoseLandmarksConnections.POSE_LANDMARKS
