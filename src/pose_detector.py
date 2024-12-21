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

    def _calculate_posture_score(self, landmarks) -> float:
        def angle_between(v1, v2):
            """Calculate the angle in degrees between two vectors."""
            v1_norm = v1 / np.linalg.norm(v1)
            v2_norm = v2 / np.linalg.norm(v2)
            dot_product = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
            return np.degrees(np.arccos(dot_product))

        def get_point(landmark):
            return np.array([landmark.x, landmark.y, landmark.z])

        # Get all relevant landmarks
        nose = get_point(landmarks.landmark[self.mp_pose.PoseLandmark.NOSE])
        left_ear = get_point(landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_EAR])
        right_ear = get_point(landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_EAR])
        left_shoulder = get_point(
            landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        )
        right_shoulder = get_point(
            landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
        )
        left_hip = get_point(landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_HIP])
        right_hip = get_point(landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_HIP])

        # Calculate midpoints
        mid_shoulder = (left_shoulder + right_shoulder) / 2
        mid_ear = (left_ear + right_ear) / 2
        mid_hip = (left_hip + right_hip) / 2

        # 1. Head Forward Tilt (Forward Head Posture)
        head_forward_offset = nose[2] - mid_ear[2]
        head_tilt_score = max(0, 1 - abs(head_forward_offset) * 1.2)

        # 2. Neck Vertical Alignment
        neck_vector = mid_ear - mid_shoulder
        ideal_neck_vector = np.array([0, -1, 0])
        neck_angle = angle_between(neck_vector, ideal_neck_vector)
        neck_vertical_score = max(0, 1 - abs(neck_angle) / 45)

        # 3. Shoulder Level (Check if shoulders are even)
        shoulder_height_diff = abs(left_shoulder[1] - right_shoulder[1])
        shoulder_level_score = max(0, 1 - shoulder_height_diff * 5)

        # 4. Shoulder Roll (Forward/Backward rotation)
        shoulder_depth_diff = abs(left_shoulder[2] - right_shoulder[2])
        shoulder_roll_score = max(0, 1 - shoulder_depth_diff * 2)

        # 5. Upper Spine Alignment
        spine_vector = mid_shoulder - mid_hip
        ideal_spine_vector = np.array([0, -1, 0])
        spine_angle = angle_between(spine_vector, ideal_spine_vector)
        spine_alignment_score = max(0, 1 - abs(spine_angle) / 45)

        # 6. Head Rotation (Left/Right)
        ear_distance = np.linalg.norm(right_ear - left_ear)
        ideal_ear_distance = np.linalg.norm(right_shoulder - left_shoulder) * 0.7
        head_rotation_score = max(
            0, 1 - abs(ear_distance - ideal_ear_distance) / ideal_ear_distance
        )

        # 7. Head Side Tilt
        ear_height_diff = abs(left_ear[1] - right_ear[1])
        head_side_tilt_score = max(0, 1 - ear_height_diff * 5)

        # Weighted combination of all scores
        weights = {
            "head_tilt": 0.2,  # Forward head posture
            "neck_vertical": 0.2,  # Neck alignment
            "shoulder_level": 0.15,  # Even shoulders
            "shoulder_roll": 0.15,  # Shoulder forward/back
            "spine": 0.15,  # Upper spine alignment
            "head_rotation": 0.1,  # Head rotation
            "head_side_tilt": 0.05,  # Head side tilt
        }

        # Calculate final score
        final_score = (
            head_tilt_score * weights["head_tilt"]
            + neck_vertical_score * weights["neck_vertical"]
            + shoulder_level_score * weights["shoulder_level"]
            + shoulder_roll_score * weights["shoulder_roll"]
            + spine_alignment_score * weights["spine"]
            + head_rotation_score * weights["head_rotation"]
            + head_side_tilt_score * weights["head_side_tilt"]
        ) * 100

        if self.debug:
            print(f"Head Tilt Score: {head_tilt_score:.2f}")
            print(f"Neck Vertical Score: {neck_vertical_score:.2f}")
            print(f"Shoulder Level Score: {shoulder_level_score:.2f}")
            print(f"Shoulder Roll Score: {shoulder_roll_score:.2f}")
            print(f"Spine Alignment Score: {spine_alignment_score:.2f}")
            print(f"Head Rotation Score: {head_rotation_score:.2f}")
            print(f"Head Side Tilt Score: {head_side_tilt_score:.2f}")

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
