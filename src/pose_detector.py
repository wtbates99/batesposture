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

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, bool, float]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        if results.pose_landmarks:
            self._draw_landmarks(frame, results)
            posture_score = self._calculate_posture_score(results.pose_landmarks)
            self._draw_posture_feedback(frame, posture_score)
            return frame, True, posture_score
        return frame, False, 0.0

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

    def _calculate_posture_score(self, landmarks) -> float:
        def angle_between(v1, v2):
            """Calculate the angle in degrees between two vectors."""
            dot_product = np.dot(v1, v2)
            # Clip to handle floating point errors
            dot_product = np.clip(dot_product, -1.0, 1.0)
            angle_rad = np.arccos(dot_product)
            return np.degrees(angle_rad)

        def get_point(landmark):
            return np.array([landmark.x, landmark.y, landmark.z])

        # Get key points
        nose = get_point(landmarks.landmark[self.mp_pose.PoseLandmark.NOSE])
        left_shoulder = get_point(
            landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        )
        right_shoulder = get_point(
            landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
        )
        left_ear = get_point(landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_EAR])
        right_ear = get_point(landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_EAR])

        mid_shoulder = (left_shoulder + right_shoulder) / 2
        mid_ear = (left_ear + right_ear) / 2

        # Calculate head forward tilt
        head_forward_offset = nose[2] - mid_ear[2]
        head_tilt_score = max(
            0, 1 - abs(head_forward_offset) * 1.5
        )  # Less strict on forward head tilt

        # Calculate neck alignment
        neck_vector = mid_ear - mid_shoulder
        ideal_neck_vector = np.array([0, -1, 0])  # Straight up
        neck_angle = angle_between(
            neck_vector / np.linalg.norm(neck_vector), ideal_neck_vector
        )
        neck_score = max(
            0, 1 - abs(neck_angle) / 45
        )  # Less strict: penalize after 45 degrees

        # Calculate ear alignment with shoulders
        ear_shoulder_diff = abs(mid_ear[0] - mid_shoulder[0])
        ear_alignment_score = max(
            0, 1 - ear_shoulder_diff * 2
        )  # Less strict on lateral alignment

        # Weighted scoring with emphasis on key indicators
        weights = {
            "head_tilt": 0.4,  # Forward head posture
            "neck": 0.4,  # Neck angle
            "ear_alignment": 0.2,  # Side tilt
        }

        final_score = (
            head_tilt_score * weights["head_tilt"]
            + neck_score * weights["neck"]
            + ear_alignment_score * weights["ear_alignment"]
        ) * 100

        if self.debug:
            print(f"Head Tilt Score: {head_tilt_score:.2f}")
            print(f"Neck Score: {neck_score:.2f}")
            print(f"Ear Alignment Score: {ear_alignment_score:.2f}")

        return min(100, max(0, final_score))

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
