import cv2
import mediapipe as mp
from typing import Tuple
import numpy as np


class PoseDetector:
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        self.upper_body_landmarks = [
            self.mp_pose.PoseLandmark.NOSE,
            self.mp_pose.PoseLandmark.LEFT_EYE,
            self.mp_pose.PoseLandmark.RIGHT_EYE,
            self.mp_pose.PoseLandmark.LEFT_EAR,
            self.mp_pose.PoseLandmark.RIGHT_EAR,
            self.mp_pose.PoseLandmark.LEFT_SHOULDER,
            self.mp_pose.PoseLandmark.RIGHT_SHOULDER,
        ]

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, bool]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        if results.pose_landmarks:
            self._draw_landmarks(frame, results)
            return frame, True
        return frame, False

    def _draw_landmarks(self, frame: np.ndarray, results) -> None:
        for landmark in self.upper_body_landmarks:
            point = results.pose_landmarks.landmark[landmark]
            h, w, _ = frame.shape
            cx, cy = int(point.x * w), int(point.y * h)
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), cv2.FILLED)

        self.mp_draw.draw_landmarks(
            frame,
            results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            self.mp_draw.DrawingSpec(
                color=(245, 117, 66), thickness=2, circle_radius=2
            ),
            self.mp_draw.DrawingSpec(
                color=(245, 66, 230), thickness=2, circle_radius=2
            ),
        )


def main():
    cap = cv2.VideoCapture(0)
    detector = PoseDetector()
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame, detected = detector.process_frame(frame)
        cv2.imshow("Posture Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
