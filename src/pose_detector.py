from typing import Tuple, Any

import cv2
import mediapipe as mp
import numpy as np

from pose_landmarks import POSTURE_LANDMARKS
from settings import get_setting


class PoseDetector:
    def __init__(
        self,
        min_detection_confidence: float = get_setting("MIN_DETECTION_CONFIDENCE"),
        min_tracking_confidence: float = get_setting("MIN_TRACKING_CONFIDENCE"),
        frame_width: int = get_setting("FRAME_WIDTH"),
        frame_height: int = get_setting("FRAME_HEIGHT"),
    ) -> None:
        """
        Initialize the PoseDetector.

        Args:
            min_detection_confidence (float, optional): Minimum confidence for pose detection.
                Defaults to value from settings.
            min_tracking_confidence (float, optional): Minimum confidence for pose tracking.
                Defaults to value from settings.
            frame_width (int, optional): Width of the video frame. Defaults to value from settings.
            frame_height (int, optional): Height of the video frame. Defaults to value from settings.
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=get_setting("MODEL_COMPLEXITY"),
        )
        self.posture_landmarks = POSTURE_LANDMARKS
        self.ideal_neck_vector = np.array([0, -1, 0])
        self.ideal_spine_vector = np.array([0, -1, 0])
        self.weights = np.array(get_setting("POSTURE_WEIGHTS"))
        self.score_thresholds = get_setting("POSTURE_THRESHOLDS")

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float, Any]:
        """
        Process a video frame to detect pose and calculate posture score.

        Args:
            frame (np.ndarray): Input video frame.

        Returns:
            Tuple[np.ndarray, float, Any]: Processed frame, posture score, and pose results.
        """
        try:
            frame = self._preprocess_frame(frame)
            results = self._detect_pose(frame)
            if results.pose_landmarks:
                self._draw_landmarks(frame, results)
                posture_score = self._calculate_posture_score(results.pose_landmarks)
                self._draw_posture_feedback(frame, posture_score)
                return frame, posture_score, results
            return frame, 0.0, None
        except Exception as e:
            print(f"Error processing frame: {e}")
            return frame, 0.0, None

    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess the frame by resizing and enhancing with CLAHE.

        Args:
            frame (np.ndarray): Input frame.

        Returns:
            np.ndarray: Preprocessed frame.
        """
        frame = cv2.resize(frame, (self.frame_width, self.frame_height))
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        enhanced = cv2.merge([l_channel, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def _detect_pose(self, frame: np.ndarray) -> Any:
        """
        Detect pose in the frame using MediaPipe.

        Args:
            frame (np.ndarray): Preprocessed frame.

        Returns:
            Any: Pose detection results.
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return self.pose.process(rgb_frame)

    def _draw_landmarks(self, frame: np.ndarray, results: Any) -> None:
        """
        Draw pose landmarks and posture-related lines on the frame.

        Args:
            frame (np.ndarray): Video frame to draw on.
            results (Any): Pose detection results from MediaPipe.
        """
        self.mp_draw.draw_landmarks(
            frame,
            results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_draw.DrawingSpec(
                color=(0, 255, 0), thickness=2, circle_radius=2
            ),
            connection_drawing_spec=self.mp_draw.DrawingSpec(
                color=(255, 255, 255), thickness=2
            ),
        )
        if results.pose_landmarks:
            h, w, _ = frame.shape
            landmarks = results.pose_landmarks.landmark
            mid_hip = np.array(
                [
                    (
                        landmarks[self.mp_pose.PoseLandmark.LEFT_HIP].x
                        + landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP].x
                    )
                    / 2,
                    (
                        landmarks[self.mp_pose.PoseLandmark.LEFT_HIP].y
                        + landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP].y
                    )
                    / 2,
                ]
            )
            mid_shoulder = np.array(
                [
                    (
                        landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER].x
                        + landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].x
                    )
                    / 2,
                    (
                        landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER].y
                        + landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].y
                    )
                    / 2,
                ]
            )
            cv2.line(
                frame,
                (int(mid_hip[0] * w), int(mid_hip[1] * h)),
                (int(mid_shoulder[0] * w), int(mid_shoulder[1] * h)),
                (0, 0, 255),
                2,
            )

    @staticmethod
    def angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
        """
        Calculate the angle in degrees between two vectors.

        Args:
            v1 (np.ndarray): First vector.
            v2 (np.ndarray): Second vector.

        Returns:
            float: Angle in degrees.
        """
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        if norm_v1 < 1e-6 or norm_v2 < 1e-6:
            return 0.0
        v1_norm = v1 / norm_v1
        v2_norm = v2 / norm_v2
        dot_product = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
        return float(np.degrees(np.arccos(dot_product)))

    def _calculate_posture_score(self, landmarks: Any) -> float:
        """
        Calculate the posture score based on pose landmarks.

        Args:
            landmarks (Any): Pose landmarks from MediaPipe.

        Returns:
            float: Posture score between 0 and 100.
        """
        points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark])
        nose = points[self.mp_pose.PoseLandmark.NOSE]
        ears = points[
            [self.mp_pose.PoseLandmark.LEFT_EAR, self.mp_pose.PoseLandmark.RIGHT_EAR]
        ]
        shoulders = points[
            [
                self.mp_pose.PoseLandmark.LEFT_SHOULDER,
                self.mp_pose.PoseLandmark.RIGHT_SHOULDER,
            ]
        ]
        hips = points[
            [self.mp_pose.PoseLandmark.LEFT_HIP, self.mp_pose.PoseLandmark.RIGHT_HIP]
        ]

        mid_ear = np.mean(ears, axis=0)
        mid_shoulder = np.mean(shoulders, axis=0)
        mid_hip = np.mean(hips, axis=0)

        head_tilt_score = np.clip(
            1 - abs(nose[2] - mid_ear[2]) * self.score_thresholds["head_tilt"], 0, 1
        )
        neck_angle = self.angle_between(mid_ear - mid_shoulder, self.ideal_neck_vector)
        neck_vertical_score = np.clip(
            1 - abs(neck_angle) / self.score_thresholds["neck_angle"], 0, 1
        )

        shoulder_diff = shoulders[0] - shoulders[1]
        shoulder_scores = np.array(
            [
                np.clip(
                    1 - abs(shoulder_diff[1]) * self.score_thresholds["shoulder_level"],
                    0,
                    1,
                ),
                np.clip(
                    1 - abs(shoulder_diff[2]) * self.score_thresholds["shoulder_roll"],
                    0,
                    1,
                ),
            ]
        )

        spine_angle = self.angle_between(
            mid_shoulder - mid_hip, self.ideal_spine_vector
        )
        spine_alignment_score = np.clip(
            1 - abs(spine_angle) / self.score_thresholds["spine_angle"], 0, 1
        )

        ear_distance = np.linalg.norm(ears[1] - ears[0])
        shoulder_width = np.linalg.norm(shoulders[1] - shoulders[0])
        ideal_ear_distance = shoulder_width * 0.7
        head_rotation_score = np.clip(
            1 - abs(ear_distance - ideal_ear_distance) / (ideal_ear_distance + 1e-6),
            0,
            1,
        )
        head_side_tilt_score = np.clip(1 - abs(ears[0][1] - ears[1][1]) * 5, 0, 1)

        scores = np.array(
            [
                head_tilt_score,
                neck_vertical_score,
                shoulder_scores[0],
                shoulder_scores[1],
                spine_alignment_score,
                head_rotation_score,
                head_side_tilt_score,
            ]
        )
        return float(np.clip(np.dot(scores, self.weights) * 100, 0, 100))

    def _draw_posture_feedback(self, frame: np.ndarray, score: float) -> None:
        """
        Draw posture score and feedback on the frame.

        Args:
            frame (np.ndarray): Video frame to draw on.
            score (float): Posture score.
        """
        score_color = (
            0,
            int(min(255, score * 2.55)),
            int(min(255, (100 - score) * 2.55)),
        )
        cv2.putText(
            frame,
            f"Posture Score: {score:.1f}%",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            score_color,
            2,
        )
        if score < 60:
            cv2.putText(
                frame,
                "Please sit up straight!",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )


if __name__ == "__main__":
    detector = PoseDetector()
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame, score, _ = detector.process_frame(frame)
        cv2.imshow("Posture Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()
