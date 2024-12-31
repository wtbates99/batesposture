from typing import Tuple

import cv2
import mediapipe as mp
import numpy as np


class PoseDetector:
    def __init__(
        self,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        frame_width=1280,
        frame_height=720,
    ):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=1,  # Use the most detailed model
        )
        self.posture_landmarks = [
            self.mp_pose.PoseLandmark.NOSE,
            self.mp_pose.PoseLandmark.LEFT_EYE_INNER,
            self.mp_pose.PoseLandmark.LEFT_EYE,
            self.mp_pose.PoseLandmark.LEFT_EYE_OUTER,
            self.mp_pose.PoseLandmark.RIGHT_EYE_INNER,
            self.mp_pose.PoseLandmark.RIGHT_EYE,
            self.mp_pose.PoseLandmark.RIGHT_EYE_OUTER,
            self.mp_pose.PoseLandmark.LEFT_EAR,
            self.mp_pose.PoseLandmark.RIGHT_EAR,
            self.mp_pose.PoseLandmark.MOUTH_LEFT,
            self.mp_pose.PoseLandmark.MOUTH_RIGHT,
            self.mp_pose.PoseLandmark.LEFT_SHOULDER,
            self.mp_pose.PoseLandmark.RIGHT_SHOULDER,
            self.mp_pose.PoseLandmark.LEFT_ELBOW,
            self.mp_pose.PoseLandmark.RIGHT_ELBOW,
            self.mp_pose.PoseLandmark.LEFT_WRIST,
            self.mp_pose.PoseLandmark.RIGHT_WRIST,
            self.mp_pose.PoseLandmark.LEFT_HIP,
            self.mp_pose.PoseLandmark.RIGHT_HIP,
        ]

        # Pre-calculate the ideal vectors once
        self.ideal_neck_vector = np.array([0, -1, 0])
        self.ideal_spine_vector = np.array([0, -1, 0])

        # Pre-calculate constants for performance
        self.weights = np.array([0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05])
        self.score_thresholds = {
            "head_tilt": 1.2,  # head forward threshold
            "neck_angle": 45.0,  # max neck angle
            "shoulder_level": 5.0,  # shoulder level threshold
            "shoulder_roll": 2.0,  # shoulder roll threshold
            "spine_angle": 45.0,  # max spine angle
        }

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float, any]:
        # Resize frame to a consistent size for better performance
        # Height of 720p maintains good detail while being computationally efficient
        frame = cv2.resize(frame, (1280, 720))

        # Apply adaptive histogram equalization to improve contrast in different lighting
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        enhanced = cv2.merge([l_channel, a_channel, b_channel])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)

        results = self.pose.process(rgb_frame)

        if results.pose_landmarks:
            self._draw_landmarks(frame, results)
            posture_score = self._calculate_posture_score(results.pose_landmarks)
            self._draw_posture_feedback(frame, posture_score)
            return frame, posture_score, results
        return frame, 0.0, None

    def _draw_landmarks(self, frame: np.ndarray, results) -> None:
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
        """Calculate angle between vectors using robust method."""
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        # Avoid division by zero
        if norm_v1 < 1e-6 or norm_v2 < 1e-6:
            return 0.0

        # Normalize vectors and calculate dot product
        v1_norm = v1 / norm_v1
        v2_norm = v2 / norm_v2
        dot_product = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)

        return np.degrees(np.arccos(dot_product))

    def _calculate_posture_score(self, landmarks) -> float:
        # Vectorized point extraction - more efficient than individual access
        landmark_points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark])

        # Get all relevant points in one go using array indexing
        nose = landmark_points[self.mp_pose.PoseLandmark.NOSE]
        ears = landmark_points[
            [self.mp_pose.PoseLandmark.LEFT_EAR, self.mp_pose.PoseLandmark.RIGHT_EAR]
        ]
        shoulders = landmark_points[
            [
                self.mp_pose.PoseLandmark.LEFT_SHOULDER,
                self.mp_pose.PoseLandmark.RIGHT_SHOULDER,
            ]
        ]
        hips = landmark_points[
            [self.mp_pose.PoseLandmark.LEFT_HIP, self.mp_pose.PoseLandmark.RIGHT_HIP]
        ]

        # Efficient midpoint calculations using numpy operations
        mid_ear = np.mean(ears, axis=0)
        mid_shoulder = np.mean(shoulders, axis=0)
        mid_hip = np.mean(hips, axis=0)

        # Vectorized score calculations
        head_forward_offset = nose[2] - mid_ear[2]
        head_tilt_score = np.clip(
            1 - abs(head_forward_offset) * self.score_thresholds["head_tilt"], 0, 1
        )

        neck_vector = mid_ear - mid_shoulder
        neck_angle = self.angle_between(neck_vector, self.ideal_neck_vector)
        neck_vertical_score = np.clip(
            1 - abs(neck_angle) / self.score_thresholds["neck_angle"], 0, 1
        )

        # Efficient shoulder calculations
        shoulder_diff = shoulders[0] - shoulders[1]  # left - right
        shoulder_scores = np.array(
            [
                np.clip(
                    1 - abs(shoulder_diff[1]) * self.score_thresholds["shoulder_level"],
                    0,
                    1,
                ),  # level
                np.clip(
                    1 - abs(shoulder_diff[2]) * self.score_thresholds["shoulder_roll"],
                    0,
                    1,
                ),  # roll
            ]
        )

        spine_vector = mid_shoulder - mid_hip
        spine_angle = self.angle_between(spine_vector, self.ideal_spine_vector)
        spine_alignment_score = np.clip(
            1 - abs(spine_angle) / self.score_thresholds["spine_angle"], 0, 1
        )

        # Efficient head rotation calculation
        ear_distance = np.linalg.norm(ears[1] - ears[0])  # right - left
        shoulder_width = np.linalg.norm(shoulders[1] - shoulders[0])
        ideal_ear_distance = shoulder_width * 0.7

        head_rotation_score = np.clip(
            1 - abs(ear_distance - ideal_ear_distance) / (ideal_ear_distance + 1e-6),
            0,
            1,
        )

        head_side_tilt_score = np.clip(1 - abs(ears[0][1] - ears[1][1]) * 5, 0, 1)

        # Vectorized final score calculation
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

        final_score = np.clip(np.dot(scores, self.weights) * 100, 0, 100)

        return final_score

    def _draw_posture_feedback(self, frame: np.ndarray, score: float) -> None:
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
