from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from dataclasses import dataclass, field, fields
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Type,
    get_args,
    get_origin,
)

import mediapipe as mp
from PyQt6.QtCore import QSettings


SETTINGS_SCHEMA_VERSION = "1.1.0"
SETTINGS_ORGANIZATION = "PostureCorrector"
SETTINGS_APPLICATION = "PostureApp"
ENV_PREFIX = "POSTURE"
LEGACY_USER_SETTINGS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../user_settings.json")
)


class SettingsValidationError(ValueError):
    """Raised when attempting to set an invalid value on the settings store."""


def get_resource_path(relative_path: str) -> str:
    relative = Path(relative_path)
    candidates = []

    base_path = getattr(sys, "_MEIPASS", None)
    if base_path:
        pyinstaller_root = Path(base_path)
        candidates.append(pyinstaller_root / relative)
        if relative.parts and relative.parts[0] == "src":
            candidates.append(pyinstaller_root / Path(*relative.parts[1:]))

    module_path = Path(__file__).resolve()
    src_root = module_path.parent.parent
    project_root = src_root.parent

    for root in (project_root, src_root):
        candidates.append(root / relative)
        if relative.parts and relative.parts[0] == "src":
            candidates.append(root / Path(*relative.parts[1:]))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return str(Path.cwd() / relative)


def _default_tracking_intervals() -> Dict[str, int]:
    return {
        "Every 15 minutes": 15,
        "Every 30 minutes": 30,
        "Every hour": 60,
    }


def _default_posture_thresholds() -> Dict[str, float]:
    return {
        "head_tilt": 1.2,
        "neck_angle": 45.0,
        "shoulder_level": 5.0,
        "shoulder_roll": 2.0,
        "spine_angle": 45.0,
    }


def _default_posture_weights() -> List[float]:
    return [0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05]


@dataclass(frozen=True)
class ResourceSettings:
    icon_path: str = field(
        default_factory=lambda: get_resource_path("src/static/icon.png")
    )
    default_db_name: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(__file__), "../posture_data.db"
        )
    )


@dataclass
class RuntimeSettings:
    default_camera_id: int = 0
    default_fps: int = 30
    frame_width: int = 1280
    frame_height: int = 720
    notification_cooldown: int = 300
    poor_posture_threshold: int = 60
    default_posture_message: str = "Please sit up straight!"
    tracking_intervals: Dict[str, int] = field(
        default_factory=_default_tracking_intervals
    )
    tracking_duration_minutes: int = 1
    enable_database_logging: bool = False
    db_write_interval_seconds: int = 900
    notifications_enabled: bool = True
    focus_mode_enabled: bool = False


@dataclass
class MLTuningSettings:
    model_complexity: int = 1
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    posture_weights: List[float] = field(default_factory=_default_posture_weights)
    posture_thresholds: Dict[str, float] = field(
        default_factory=_default_posture_thresholds
    )
    score_buffer_size: int = 1000
    score_window_size: int = 5
    score_threshold: int = 65


@dataclass
class UserProfileSettings:
    has_completed_onboarding: bool = False
    baseline_posture_score: float = 75.0
    baseline_neck_angle: float = 10.0
    baseline_shoulder_level: float = 2.0
    preferred_theme: str = "system"
    language_code: str = "en_US"


POSTURE_LANDMARKS = [
    mp.solutions.pose.PoseLandmark.NOSE,
    mp.solutions.pose.PoseLandmark.LEFT_EYE_INNER,
    mp.solutions.pose.PoseLandmark.LEFT_EYE,
    mp.solutions.pose.PoseLandmark.LEFT_EYE_OUTER,
    mp.solutions.pose.PoseLandmark.RIGHT_EYE_INNER,
    mp.solutions.pose.PoseLandmark.RIGHT_EYE,
    mp.solutions.pose.PoseLandmark.RIGHT_EYE_OUTER,
    mp.solutions.pose.PoseLandmark.LEFT_EAR,
    mp.solutions.pose.PoseLandmark.RIGHT_EAR,
    mp.solutions.pose.PoseLandmark.MOUTH_LEFT,
    mp.solutions.pose.PoseLandmark.MOUTH_RIGHT,
    mp.solutions.pose.PoseLandmark.LEFT_SHOULDER,
    mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER,
    mp.solutions.pose.PoseLandmark.LEFT_ELBOW,
    mp.solutions.pose.PoseLandmark.RIGHT_ELBOW,
    mp.solutions.pose.PoseLandmark.LEFT_WRIST,
    mp.solutions.pose.PoseLandmark.RIGHT_WRIST,
    mp.solutions.pose.PoseLandmark.LEFT_HIP,
    mp.solutions.pose.PoseLandmark.RIGHT_HIP,
]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value)
    return value


def _coerce_primitive(expected_type: Type[Any], value: Any) -> Any:
    if expected_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        raise SettingsValidationError(f"Cannot coerce {value!r} to bool")
    if expected_type is int:
        return int(value)
    if expected_type is float:
        return float(value)
    if expected_type is str:
        return str(value)
    return value


def _deserialize_value(expected_type: Type[Any], raw_value: Any, fallback: Any) -> Any:
    if raw_value is None:
        return fallback

    origin = get_origin(expected_type)
    if origin is None:
        expected = expected_type
        if expected in (Any, type(fallback)):
            return raw_value
        return _coerce_primitive(expected, raw_value)

    args = get_args(expected_type)
    if origin in (dict, Dict, MutableMapping, Mapping):
        if isinstance(raw_value, str):
            try:
                raw_value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise SettingsValidationError(
                    "Invalid JSON for mapping setting"
                ) from exc
        if not isinstance(raw_value, Mapping):
            raise SettingsValidationError(
                f"Expected mapping for {expected_type}, got {type(raw_value)}"
            )
        key_type, value_type = args or (Any, Any)
        return {
            _deserialize_value(key_type, key, key): _deserialize_value(
                value_type, val, val
            )
            for key, val in raw_value.items()
        }

    if origin in (list, List, tuple, Tuple, Iterable):
        if isinstance(raw_value, str):
            try:
                raw_value = json.loads(raw_value)
            except json.JSONDecodeError:
                raw_value = [
                    part.strip() for part in raw_value.split(",") if part.strip()
                ]
        if not isinstance(raw_value, Iterable) or isinstance(raw_value, (str, bytes)):
            raise SettingsValidationError(
                f"Expected iterable for {expected_type}, got {type(raw_value)}"
            )
        item_type = args[0] if args else Any
        coerced = [_deserialize_value(item_type, item, item) for item in raw_value]
        return coerced if origin in (list, List, Iterable) else tuple(coerced)

    return raw_value


class SettingsStore:
    def __init__(
        self,
        qsettings: Optional[QSettings] = None,
        migrate_legacy: bool = True,
    ) -> None:
        self.resources = ResourceSettings()
        self.runtime = RuntimeSettings()
        self.ml = MLTuningSettings()
        self.profile = UserProfileSettings()
        self._settings = qsettings or QSettings(
            SETTINGS_ORGANIZATION, SETTINGS_APPLICATION
        )
        self._ensure_schema_version()
        if migrate_legacy:
            self._maybe_migrate_legacy_json()
        self._load_group("runtime", self.runtime)
        self._load_group("ml", self.ml)
        self._load_group("profile", self.profile)
        self._apply_env_overrides()
        self._normalize_loaded_settings()

    def _ensure_schema_version(self) -> None:
        stored_version = self._settings.value("metadata/schema_version", type=str)
        if stored_version != SETTINGS_SCHEMA_VERSION:
            self._settings.setValue("metadata/schema_version", SETTINGS_SCHEMA_VERSION)
            self._settings.sync()

    def _maybe_migrate_legacy_json(self) -> None:
        legacy_file = os.path.abspath(LEGACY_USER_SETTINGS_FILE)
        if not os.path.exists(legacy_file):
            return
        try:
            with open(legacy_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return

        for key, value in payload.items():
            if key not in KEY_TO_SECTION_FIELD:
                continue
            section_name, field_name = KEY_TO_SECTION_FIELD[key]
            self._set_field(section_name, field_name, value, persist=False)

        self.save_runtime()
        self.save_ml()
        self.save_profile()
        try:
            os.replace(legacy_file, legacy_file + ".legacy")
        except OSError:
            pass

    def _apply_env_overrides(self) -> None:
        overrides = {
            "runtime": self.runtime,
            "ml": self.ml,
            "profile": self.profile,
        }
        for section_name, section_obj in overrides.items():
            for field_info in fields(section_obj):
                env_key = (
                    f"{ENV_PREFIX}_{section_name.upper()}_{field_info.name.upper()}"
                )
                if env_key not in os.environ:
                    continue
                raw_value = os.environ[env_key]
                coerced = _deserialize_value(
                    field_info.type, raw_value, getattr(section_obj, field_info.name)
                )
                setattr(section_obj, field_info.name, coerced)

    def _normalize_loaded_settings(self) -> None:
        runtime_changed = False
        ml_changed = False

        intervals = self._coerce_tracking_intervals(self.runtime.tracking_intervals)
        if not intervals:
            intervals = _default_tracking_intervals()
        if intervals != self.runtime.tracking_intervals:
            self.runtime.tracking_intervals = intervals
            runtime_changed = True

        thresholds = self._coerce_threshold_mapping(self.ml.posture_thresholds)
        if not thresholds:
            thresholds = _default_posture_thresholds()
        if thresholds != self.ml.posture_thresholds:
            self.ml.posture_thresholds = thresholds
            ml_changed = True

        weights = self._coerce_weight_list(self.ml.posture_weights)
        if not weights:
            weights = _default_posture_weights()
        if weights != self.ml.posture_weights:
            self.ml.posture_weights = weights
            ml_changed = True

        if runtime_changed:
            self.save_runtime()
        if ml_changed:
            self.save_ml()

    @staticmethod
    def _coerce_tracking_intervals(raw: Any) -> Dict[str, int]:
        if isinstance(raw, Mapping):
            result: Dict[str, int] = {}
            for label, value in raw.items():
                minutes = SettingsStore._coerce_int(value)
                if minutes is None:
                    continue
                result[str(label).strip()] = minutes
            return result

        if isinstance(raw, str):
            parsed = SettingsStore._parse_interval_string(raw)
            if parsed:
                return parsed
            return {}

        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
            result: Dict[str, int] = {}
            for item in raw:
                if isinstance(item, Mapping):
                    result.update(SettingsStore._coerce_tracking_intervals(item))
                    continue
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    label = str(item[0]).strip()
                    minutes = SettingsStore._coerce_int(item[1])
                    if minutes is not None:
                        result[label] = minutes
            return result

        return {}

    @staticmethod
    def _parse_interval_string(payload: str) -> Dict[str, int]:
        payload = payload.strip()
        if not payload:
            return {}
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            try:
                decoded = ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                decoded = None
        if isinstance(decoded, Mapping):
            return SettingsStore._coerce_tracking_intervals(decoded)
        if isinstance(decoded, Iterable) and not isinstance(decoded, (str, bytes)):
            return SettingsStore._coerce_tracking_intervals(list(decoded))

        result: Dict[str, int] = {}
        fragments = [frag for frag in payload.split(",") if frag.strip()]
        for fragment in fragments:
            separator = ":" if ":" in fragment else "="
            if separator not in fragment:
                continue
            label_part, minutes_part = fragment.split(separator, 1)
            label = label_part.strip().strip("\"'{} ")
            minutes = SettingsStore._coerce_int(minutes_part)
            if minutes is not None:
                result[label] = minutes
        return result

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_threshold_mapping(raw: Any) -> Dict[str, float]:
        if isinstance(raw, Mapping):
            result: Dict[str, float] = {}
            for key, value in raw.items():
                coerced = SettingsStore._coerce_float(value)
                if coerced is None:
                    continue
                result[str(key)] = coerced
            return result

        if isinstance(raw, str):
            converted = SettingsStore._loads_flexible(raw)
            if isinstance(converted, Mapping):
                return SettingsStore._coerce_threshold_mapping(converted)
            if isinstance(converted, Iterable):
                return SettingsStore._coerce_threshold_mapping(converted)
            return {}

        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
            result: Dict[str, float] = {}
            for item in raw:
                if isinstance(item, Mapping):
                    result.update(SettingsStore._coerce_threshold_mapping(item))
                    continue
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    key = str(item[0]).strip()
                    value = SettingsStore._coerce_float(item[1])
                    if value is not None:
                        result[key] = value
            return result

        return {}

    @staticmethod
    def _coerce_weight_list(raw: Any) -> List[float]:
        if isinstance(raw, str):
            raw = SettingsStore._loads_flexible(raw)
        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
            result: List[float] = []
            for item in raw:
                value = SettingsStore._coerce_float(item)
                if value is not None:
                    result.append(value)
            return result
        if isinstance(raw, (int, float)):
            return [float(raw)]
        return []

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _loads_flexible(payload: str) -> Any:
        payload = payload.strip()
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                return None

    def _load_group(self, group_name: str, section_obj: Any) -> None:
        self._settings.beginGroup(group_name)
        try:
            for field_info in fields(section_obj):
                default = getattr(section_obj, field_info.name)
                raw_value = self._settings.value(field_info.name, None)
                value = _deserialize_value(field_info.type, raw_value, default)
                setattr(section_obj, field_info.name, value)
        finally:
            self._settings.endGroup()

    def _save_group(self, group_name: str, section_obj: Any) -> None:
        self._settings.beginGroup(group_name)
        try:
            for field_info in fields(section_obj):
                value = getattr(section_obj, field_info.name)
                self._settings.setValue(field_info.name, _serialize_value(value))
        finally:
            self._settings.endGroup()
        self._settings.sync()

    def save_runtime(self) -> None:
        self._save_group("runtime", self.runtime)

    def save_ml(self) -> None:
        self._save_group("ml", self.ml)

    def save_profile(self) -> None:
        self._save_group("profile", self.profile)

    def _set_field(
        self, section_name: str, field_name: str, value: Any, persist: bool = True
    ) -> None:
        section = getattr(self, section_name, None)
        if section is None:
            raise KeyError(f"Unknown settings section: {section_name}")

        for field_info in fields(section):
            if field_info.name != field_name:
                continue
            coerced = _deserialize_value(
                field_info.type, value, getattr(section, field_name)
            )
            setattr(section, field_name, coerced)
            if persist:
                if section_name == "runtime":
                    self.save_runtime()
                elif section_name == "ml":
                    self.save_ml()
                elif section_name == "profile":
                    self.save_profile()
            return

        raise KeyError(f"Unknown field {field_name} in section {section_name}")

    def get(self, key: str) -> Any:
        section_name, field_name = KEY_TO_SECTION_FIELD[key]
        section = getattr(self, section_name)
        return getattr(section, field_name)

    def update(self, key: str, value: Any) -> None:
        if key not in KEY_TO_SECTION_FIELD:
            raise KeyError(f"Unknown setting: {key}")
        section_name, field_name = KEY_TO_SECTION_FIELD[key]
        self._set_field(section_name, field_name, value)

    def update_runtime(self, **overrides: Any) -> None:
        for field_name, value in overrides.items():
            self._set_field("runtime", field_name, value, persist=False)
        self.save_runtime()

    def update_ml(self, **overrides: Any) -> None:
        for field_name, value in overrides.items():
            self._set_field("ml", field_name, value, persist=False)
        self.save_ml()

    def update_profile(self, **overrides: Any) -> None:
        for field_name, value in overrides.items():
            self._set_field("profile", field_name, value, persist=False)
        self.save_profile()


KEY_TO_SECTION_FIELD: Dict[str, Tuple[str, str]] = {
    "ICON_PATH": ("resources", "icon_path"),
    "DEFAULT_DB_NAME": ("resources", "default_db_name"),
    "POSTURE_WEIGHTS": ("ml", "posture_weights"),
    "POSTURE_THRESHOLDS": ("ml", "posture_thresholds"),
    "MIN_DETECTION_CONFIDENCE": ("ml", "min_detection_confidence"),
    "MIN_TRACKING_CONFIDENCE": ("ml", "min_tracking_confidence"),
    "SCORE_BUFFER_SIZE": ("ml", "score_buffer_size"),
    "SCORE_WINDOW_SIZE": ("ml", "score_window_size"),
    "SCORE_THRESHOLD": ("ml", "score_threshold"),
    "MODEL_COMPLEXITY": ("ml", "model_complexity"),
    "DEFAULT_CAMERA_ID": ("runtime", "default_camera_id"),
    "DEFAULT_FPS": ("runtime", "default_fps"),
    "FRAME_WIDTH": ("runtime", "frame_width"),
    "FRAME_HEIGHT": ("runtime", "frame_height"),
    "NOTIFICATION_COOLDOWN": ("runtime", "notification_cooldown"),
    "POOR_POSTURE_THRESHOLD": ("runtime", "poor_posture_threshold"),
    "DEFAULT_POSTURE_MESSAGE": ("runtime", "default_posture_message"),
    "TRACKING_INTERVALS": ("runtime", "tracking_intervals"),
    "TRACKING_DURATION_MINUTES": ("runtime", "tracking_duration_minutes"),
    "ENABLE_DATABASE_LOGGING": ("runtime", "enable_database_logging"),
    "DB_WRITE_INTERVAL_SECONDS": ("runtime", "db_write_interval_seconds"),
    "NOTIFICATIONS_ENABLED": ("runtime", "notifications_enabled"),
    "FOCUS_MODE_ENABLED": ("runtime", "focus_mode_enabled"),
    "HAS_COMPLETED_ONBOARDING": ("profile", "has_completed_onboarding"),
    "BASELINE_POSTURE_SCORE": ("profile", "baseline_posture_score"),
    "BASELINE_NECK_ANGLE": ("profile", "baseline_neck_angle"),
    "BASELINE_SHOULDER_LEVEL": ("profile", "baseline_shoulder_level"),
    "PREFERRED_THEME": ("profile", "preferred_theme"),
    "LANGUAGE_CODE": ("profile", "language_code"),
}


class SettingsService:
    """Façade over persistent settings with structured accessors."""

    def __init__(self, store: Optional[SettingsStore] = None) -> None:
        self._store = store or SettingsStore()

    @property
    def resources(self) -> ResourceSettings:
        return self._store.resources

    @property
    def runtime(self) -> RuntimeSettings:
        return self._store.runtime

    @property
    def ml(self) -> MLTuningSettings:
        return self._store.ml

    @property
    def profile(self) -> UserProfileSettings:
        return self._store.profile

    def update_runtime(self, **overrides: Any) -> None:
        self._store.update_runtime(**overrides)

    def update_ml(self, **overrides: Any) -> None:
        self._store.update_ml(**overrides)

    def update_profile(self, **overrides: Any) -> None:
        self._store.update_profile(**overrides)

    def save_all(self) -> None:
        self._store.save_runtime()
        self._store.save_ml()
        self._store.save_profile()

    def get_posture_landmarks(self) -> List[mp.solutions.pose.PoseLandmark]:
        return POSTURE_LANDMARKS

    @classmethod
    def for_testing(
        cls, path: Optional[os.PathLike[str] | str] = None
    ) -> "SettingsService":
        if path is None:
            temp_dir = tempfile.gettempdir()
            path = os.path.join(temp_dir, f"posture_test_{uuid.uuid4().hex}.ini")
        qsettings = QSettings(str(path), QSettings.Format.IniFormat)
        qsettings.clear()
        store = SettingsStore(qsettings=qsettings, migrate_legacy=False)
        return cls(store)
