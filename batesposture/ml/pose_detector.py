from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.request
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from ..services.settings_service import (
    DEFAULT_POSTURE_WEIGHTS,
    SettingsService,
    _default_posture_thresholds,
    get_app_data_dir,
)
from .mediapipe_compat import PoseLandmark

logger = logging.getLogger(__name__)

# model_complexity setting → Pose Landmarker model variant
_MODEL_VARIANTS = {0: "lite", 1: "full", 2: "heavy"}
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_{0}/float16/1/pose_landmarker_{0}.task"
)
_MODEL_SHA256 = {
    "lite": "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
    "full": "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1",
    "heavy": "64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b",
}


def _model_path(model_complexity: int) -> str:
    """Return a local path to the pose model, downloading it on first use."""
    variant = _MODEL_VARIANTS.get(model_complexity, "full")
    path = get_app_data_dir() / "models" / f"pose_landmarker_{variant}.task"
    if path.exists():
        return str(path)

    logger.info("Downloading %s pose model", variant)
    try:
        with urllib.request.urlopen(_MODEL_URL.format(variant), timeout=60) as resp:
            data = resp.read()
    except OSError as exc:
        raise RuntimeError(
            f"Could not download the {variant} pose model. An internet connection "
            "is needed the first time each model is used."
        ) from exc
    if hashlib.sha256(data).hexdigest() != _MODEL_SHA256[variant]:
        raise RuntimeError(f"Checksum mismatch for downloaded {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


# Below this mean hip visibility the hips are off-screen guesses, so the spine
# metric is noise and drops out of the score.
_HIP_VISIBILITY_MIN = 0.5
_SPINE_WEIGHT_INDEX = 4

# Motion gate: inference is skipped while a coarse grayscale thumbnail stays
# within this mean absolute difference (0–255) of the last inferred frame.
# Sensor noise on a still scene measures ~0.8 (p90 ~1.5).
_MOTION_THRESHOLD = 2.5
_MOTION_STRIDE = 16
# Re-run inference at least this often so slow drift is still caught.
_MAX_REUSE_S = 2.0


def _visibility(landmark: Any) -> float:
    value = getattr(landmark, "visibility", None)
    return 1.0 if value is None else float(value)


@dataclass
class PoseDetectionResult:
    results: Any
    metrics: dict[str, float]
    # (33, 3) normalized x, y, z landmark coordinates, for overlay drawing
    points: np.ndarray | None = None

    @property
    def pose_landmarks(self) -> Any:
        return getattr(self.results, "pose_landmarks", None)


class PoseDetector:
    """Detects human posture from webcam frames using MediaPipe Pose.

    Resizes each frame to the processing size, runs MediaPipe landmark
    detection (skipped while the scene is still — see ``_MOTION_THRESHOLD``), computes seven weighted posture metrics (head tilt, neck angle, shoulder
    level, shoulder roll, spine alignment, head rotation, head side tilt), and returns a
    0–100 posture score alongside the preprocessed frame and detailed metric dict.
    Drawing is left to the UI so frames nobody looks at cost nothing extra.

    process_frame() is infallible — all exceptions are caught and (frame, 0.0, None)
    is returned so the camera capture loop never stops due to a bad frame.
    """

    def __init__(self, settings: SettingsService) -> None:
        self._settings = settings
        self.posture_landmarks = settings.get_posture_landmarks()
        self.ideal_neck_vector = np.array([0, -1, 0])
        self.ideal_spine_vector = np.array([0, -1, 0])
        self.frame_width = 0
        self.frame_height = 0
        self.weights = np.array([], dtype=float)
        self.score_thresholds: dict[str, float] = {}
        self.pose = None
        self._last_timestamp_ms = 0
        self._reference_thumb: np.ndarray | None = None
        self._reference_at = 0.0
        self._reference_result: tuple[float, Any] = (0.0, None)
        self.inference_count = 0
        self.reload()
        # Pre-warm MediaPipe so the first real frame isn't delayed by model init.
        # Use a noise frame (not zeros) so MediaPipe does real work — better proxy
        # for actual inference cost on this hardware.
        self.prewarm_duration_ms: float = 0.0
        try:
            rng = np.random.default_rng(0)
            _dummy = rng.integers(50, 200, (480, 640, 3), dtype=np.uint8)
            _t0 = time.monotonic()
            self._detect_pose(_dummy)
            self.prewarm_duration_ms = (time.monotonic() - _t0) * 1000
            logger.debug(
                "MediaPipe model pre-warmed in %.0f ms", self.prewarm_duration_ms
            )
        except Exception:  # noqa: BLE001
            pass

    def _create_pose(self):
        ml_settings = self._settings.ml
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=_model_path(ml_settings.model_complexity)
            ),
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=ml_settings.min_detection_confidence,
            min_tracking_confidence=ml_settings.min_tracking_confidence,
        )
        return vision.PoseLandmarker.create_from_options(options)

    def reload(self) -> None:
        """Reload detector and scoring settings without restarting the app."""
        runtime = self._settings.runtime
        self.frame_width = runtime.frame_width
        self.frame_height = runtime.frame_height
        self.weights = self._normalize_weights(self._settings.ml.posture_weights)
        self.score_thresholds = self._normalize_thresholds(
            self._settings.ml.posture_thresholds
        )

        old_pose = getattr(self, "pose", None)
        try:
            new_pose = self._create_pose()
        except RuntimeError:
            if old_pose is None:
                raise
            # e.g. a newly selected model could not be downloaded while offline
            logger.exception("Keeping the current pose model")
            return
        self.pose = new_pose
        self._reference_thumb = None  # scoring settings may have changed
        if old_pose is not None and hasattr(old_pose, "close"):
            old_pose.close()

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, float, Any]:
        try:
            thumb = cv2.cvtColor(
                np.ascontiguousarray(frame[::_MOTION_STRIDE, ::_MOTION_STRIDE]),
                cv2.COLOR_BGR2GRAY,
            ).astype(np.int16)
            frame = self._preprocess_frame(frame)
            now = time.monotonic()
            if self._scene_unchanged(thumb, now):
                # Nothing moved: the previous landmarks still describe this frame.
                return (frame, *self._reference_result)
            score, bundle = self._infer(frame)
            self._reference_thumb = thumb
            self._reference_at = now
            self._reference_result = (score, bundle)
            return frame, score, bundle
        except (cv2.error, ValueError, np.linalg.LinAlgError) as exc:
            # Transient per-frame error (image conversion, bad landmark geometry) — skip frame
            logger.warning("Skipping frame due to recoverable error: %s", exc)
            return frame, 0.0, None
        except Exception:  # noqa: BLE001 - unexpected error; keep loop alive
            logger.exception("Unexpected error processing frame")
            return frame, 0.0, None

    def _scene_unchanged(self, thumb: np.ndarray, now: float) -> bool:
        reference = self._reference_thumb
        return (
            reference is not None
            and reference.shape == thumb.shape
            and now - self._reference_at < _MAX_REUSE_S
            and float(np.abs(thumb - reference).mean()) < _MOTION_THRESHOLD
        )

    def _infer(self, frame: np.ndarray) -> tuple[float, PoseDetectionResult | None]:
        self.inference_count += 1
        results = self._detect_pose(frame)
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks])
            hip_visibility = 0.5 * (
                _visibility(landmarks[PoseLandmark.LEFT_HIP])
                + _visibility(landmarks[PoseLandmark.RIGHT_HIP])
            )
            metrics = self._compute_posture_metrics_from_points(points, hip_visibility)
            return metrics["posture_score"], PoseDetectionResult(
                results, metrics, points
            )
        return 0.0, None

    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        # No contrast enhancement: on real webcam frames CLAHE detected no more
        # poses (fewer when dim) and cost ~25% of per-frame work.
        if frame.shape[1] != self.frame_width or frame.shape[0] != self.frame_height:
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))
        return frame

    def _detect_pose(self, frame: np.ndarray) -> Any:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        # VIDEO mode requires strictly increasing timestamps
        timestamp_ms = max(int(time.monotonic() * 1000), self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        result = self.pose.detect_for_video(image, timestamp_ms)
        # Expose the first pose in the legacy ``pose_landmarks.landmark`` shape
        # that scoring, drawing, and the database layer consume.
        pose_landmarks = (
            SimpleNamespace(landmark=result.pose_landmarks[0])
            if result.pose_landmarks
            else None
        )
        return SimpleNamespace(pose_landmarks=pose_landmarks)

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

    def calculate_posture_metrics(self, landmarks: Any) -> dict[str, float]:
        return self._compute_posture_metrics(landmarks)

    def _compute_posture_metrics(self, landmarks: Any) -> dict[str, float]:
        points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark])
        return self._compute_posture_metrics_from_points(points)

    def _compute_posture_metrics_from_points(
        self, points: np.ndarray, hip_visibility: float = 1.0
    ) -> dict[str, float]:
        nose = points[PoseLandmark.NOSE]
        ears = points[[PoseLandmark.LEFT_EAR, PoseLandmark.RIGHT_EAR]]
        shoulders = points[
            [
                PoseLandmark.LEFT_SHOULDER,
                PoseLandmark.RIGHT_SHOULDER,
            ]
        ]
        hips = points[[PoseLandmark.LEFT_HIP, PoseLandmark.RIGHT_HIP]]

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
        hips_visible = hip_visibility >= _HIP_VISIBILITY_MIN
        weights = self.weights
        if not hips_visible and weights.sum() > weights[_SPINE_WEIGHT_INDEX]:
            weights = weights.copy()
            weights[_SPINE_WEIGHT_INDEX] = 0.0
            weights /= weights.sum()
        posture_score = float(np.clip(np.dot(scores, weights) * 100, 0, 100))
        return {
            "posture_score": posture_score,
            "neck_angle": float(neck_angle),
            "shoulder_vertical_delta": float(abs(shoulder_diff[1])),
            "spine_angle": float(spine_angle),
            "head_tilt_score": float(head_tilt_score),
            "neck_vertical_score": float(neck_vertical_score),
            "shoulder_level_score": float(shoulder_scores[0]),
            "shoulder_roll_score": float(shoulder_scores[1]),
            "spine_alignment_score": float(spine_alignment_score),
            "head_rotation_score": float(head_rotation_score),
            "head_side_tilt_score": float(head_side_tilt_score),
            "hips_visible": float(hips_visible),
        }

    def _calculate_posture_score(self, landmarks: Any) -> float:
        return self._compute_posture_metrics(landmarks)["posture_score"]

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
        if len(coerced) != len(DEFAULT_POSTURE_WEIGHTS):
            raise ValueError(
                f"Expected {len(DEFAULT_POSTURE_WEIGHTS)} posture weights, got {len(coerced)}"
            )
        if any(value < 0 for value in coerced):
            raise ValueError("Posture weights cannot be negative")
        total = sum(coerced)
        if total <= 0:
            raise ValueError("Posture weights must sum to a positive value")
        return np.array([value / total for value in coerced], dtype=float)

    @staticmethod
    def _normalize_thresholds(thresholds: Any) -> dict[str, float]:
        if isinstance(thresholds, str):
            try:
                thresholds = json.loads(thresholds)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid posture thresholds configuration") from exc
        normalized = _default_posture_thresholds()
        if hasattr(thresholds, "items"):
            for key, value in thresholds.items():
                if key not in normalized:
                    continue
                coerced = float(value)
                if coerced <= 0:
                    raise ValueError("Posture thresholds must be positive")
                normalized[str(key)] = coerced
            return normalized
        raise ValueError("Invalid posture thresholds configuration")
