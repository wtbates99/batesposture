import cv2
import mediapipe as mp
import numpy as np
from typing import Tuple


class pose_detector:
    def __init__(
        self,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        debug=False,
    ):
        self.debug = debug
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=2,  # Use the most detailed model
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

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        if results.pose_landmarks:
            self._draw_landmarks(frame, results)
            posture_score = self._calculate_posture_score(results.pose_landmarks)
            self._draw_posture_feedback(frame, posture_score)
            return frame, posture_score
        return frame, 0.0

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
    def angle_between(v1, v2):
        """Optimized angle calculation between vectors."""
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        # Handle zero vectors
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        dot_product = np.clip(np.dot(v1 / norm_v1, v2 / norm_v2), -1.0, 1.0)
        return np.degrees(np.arccos(dot_product))

    def _calculate_posture_score(self, landmarks) -> float:
        # Vectorized point extraction
        landmark_points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark])

        # Get relevant points using array indexing
        nose = landmark_points[self.mp_pose.PoseLandmark.NOSE]
        left_ear = landmark_points[self.mp_pose.PoseLandmark.LEFT_EAR]
        right_ear = landmark_points[self.mp_pose.PoseLandmark.RIGHT_EAR]
        left_shoulder = landmark_points[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmark_points[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_hip = landmark_points[self.mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = landmark_points[self.mp_pose.PoseLandmark.RIGHT_HIP]

        # Vectorized midpoint calculations
        mid_shoulder = (left_shoulder + right_shoulder) * 0.5
        mid_ear = (left_ear + right_ear) * 0.5
        mid_hip = (left_hip + right_hip) * 0.5

        # Vectorized score calculations
        head_forward_offset = nose[2] - mid_ear[2]
        head_tilt_score = max(0, 1 - abs(head_forward_offset) * 1.2)

        neck_vector = mid_ear - mid_shoulder
        neck_angle = self.angle_between(neck_vector, self.ideal_neck_vector)
        neck_vertical_score = max(0, 1 - abs(neck_angle) / 45)

        shoulder_scores = np.array(
            [
                max(0, 1 - abs(left_shoulder[1] - right_shoulder[1]) * 5),  # level
                max(0, 1 - abs(left_shoulder[2] - right_shoulder[2]) * 2),  # roll
            ]
        )

        spine_vector = mid_shoulder - mid_hip
        spine_angle = self.angle_between(spine_vector, self.ideal_spine_vector)
        spine_alignment_score = max(0, 1 - abs(spine_angle) / 45)

        ear_distance = np.linalg.norm(right_ear - left_ear)
        ideal_ear_distance = np.linalg.norm(right_shoulder - left_shoulder) * 0.7

        if ideal_ear_distance == 0:
            head_rotation_score = 0.0
        else:
            head_rotation_score = max(
                0, 1 - abs(ear_distance - ideal_ear_distance) / ideal_ear_distance
            )

        head_side_tilt_score = max(0, 1 - abs(left_ear[1] - right_ear[1]) * 5)

        # Vectorized weighted sum
        weights = np.array([0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05])
        scores = np.array(
            [
                head_tilt_score,
                neck_vertical_score,
                shoulder_scores[0],  # level
                shoulder_scores[1],  # roll
                spine_alignment_score,
                head_rotation_score,
                head_side_tilt_score,
            ]
        )

        final_score = np.clip(np.dot(scores, weights) * 100, 0, 100)

        if self.debug:
            score_names = [
                "Head Tilt",
                "Neck Vertical",
                "Shoulder Level",
                "Shoulder Roll",
                "Spine Alignment",
                "Head Rotation",
                "Head Side Tilt",
            ]
            for name, score in zip(score_names, scores):
                print(f"{name} Score: {score:.2f}")

        return final_score

    def _draw_posture_feedback(self, frame: np.ndarray, score: float) -> None:
        h, w, _ = frame.shape
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

        cv2.imshow("Posture Detection", frame)
