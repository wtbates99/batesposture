from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import cv2
import json
import mediapipe as mp
import numpy as np

from services.settings_service import SettingsService


@dataclass
class PoseDetectionResult:
    results: Any
    metrics: Dict[str, float]

    @property
    def pose_landmarks(self) -> Any:
        return getattr(self.results, "pose_landmarks", None)


class PoseDetector:
    def __init__(self, settings: SettingsService) -> None:
        self._settings = settings
        runtime = settings.runtime
        ml_settings = settings.ml

        self.frame_width = runtime.frame_width
        self.frame_height = runtime.frame_height
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=ml_settings.min_detection_confidence,
            min_tracking_confidence=ml_settings.min_tracking_confidence,
            model_complexity=ml_settings.model_complexity,
        )
        self.posture_landmarks = settings.get_posture_landmarks()
        self.ideal_neck_vector = np.array([0, -1, 0])
        self.ideal_spine_vector = np.array([0, -1, 0])
        self.weights = self._normalize_weights(ml_settings.posture_weights)
        self.score_thresholds = self._normalize_thresholds(
            ml_settings.posture_thresholds
        )

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float, Any]:
        try:
            frame = self._preprocess_frame(frame)
            results = self._detect_pose(frame)
            if results.pose_landmarks:
                self._draw_landmarks(frame, results)
                metrics = self._compute_posture_metrics(results.pose_landmarks)
                posture_score = metrics["posture_score"]
                self._draw_posture_feedback(frame, posture_score)
                return frame, posture_score, PoseDetectionResult(results, metrics)
            return frame, 0.0, None
        except Exception as exc:  # noqa: BLE001 - ensure downstream keeps running
            print(f"Error processing frame: {exc}")
            return frame, 0.0, None

    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        frame = cv2.resize(frame, (self.frame_width, self.frame_height))
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        enhanced = cv2.merge([l_channel, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def _detect_pose(self, frame: np.ndarray) -> Any:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return self.pose.process(rgb_frame)

    def _draw_landmarks(self, frame: np.ndarray, results: Any) -> None:
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
            mid_hip = np.mean(
                [
                    [
                        landmarks[self.mp_pose.PoseLandmark.LEFT_HIP].x,
                        landmarks[self.mp_pose.PoseLandmark.LEFT_HIP].y,
                    ],
                    [
                        landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP].x,
                        landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP].y,
                    ],
                ],
                axis=0,
            )
            mid_shoulder = np.mean(
                [
                    [
                        landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER].x,
                        landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER].y,
                    ],
                    [
                        landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].x,
                        landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].y,
                    ],
                ],
                axis=0,
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
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        if norm_v1 < 1e-6 or norm_v2 < 1e-6:
            return 0.0
        v1_norm = v1 / norm_v1
        v2_norm = v2 / norm_v2
        dot_product = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
        return float(np.degrees(np.arccos(dot_product)))

    def calculate_posture_metrics(self, landmarks: Any) -> Dict[str, float]:
        return self._compute_posture_metrics(landmarks)

    def _compute_posture_metrics(self, landmarks: Any) -> Dict[str, float]:
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
        posture_score = float(np.clip(np.dot(scores, self.weights) * 100, 0, 100))
        return {
            "posture_score": posture_score,
            "neck_angle": float(neck_angle),
            "shoulder_vertical_delta": float(abs(shoulder_diff[1])),
            "spine_angle": float(spine_angle),
            "head_tilt_score": float(head_tilt_score),
            "neck_vertical_score": float(neck_vertical_score),
            "spine_alignment_score": float(spine_alignment_score),
        }

    def _calculate_posture_score(self, landmarks: Any) -> float:
        return self._compute_posture_metrics(landmarks)["posture_score"]

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

    @staticmethod
    def _normalize_weights(weights: Any) -> np.ndarray:
        if isinstance(weights, str):
            try:
                decoded = json.loads(weights)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid posture weights configuration") from exc
            weights = decoded
        if not isinstance(weights, (list, tuple)):
            raise ValueError("Posture weights must be a list of numbers")
        coerced = [float(value) for value in weights]
        return np.array(coerced, dtype=float)

    @staticmethod
    def _normalize_thresholds(thresholds: Any) -> Dict[str, float]:
        if isinstance(thresholds, str):
            try:
                thresholds = json.loads(thresholds)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid posture thresholds configuration") from exc
        if hasattr(thresholds, "items"):
            return {str(key): float(value) for key, value in thresholds.items()}
        raise ValueError("Invalid posture thresholds configuration")
