import json
import os
import mediapipe as mp

# Path where user-customizable settings are saved/restored.
USER_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "user_settings.json")

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
# ---------------------------
# Immutable settings - these cannot be changed through the UI.
# ---------------------------
IMMUTABLE_SETTINGS = {
    "ICON_PATH": os.path.join(os.path.dirname(__file__), "static", "icon.png"),
    "DEFAULT_DB_NAME": os.path.join(os.path.dirname(__file__), "posture_data.db"),
    # Core algorithm weights and thresholds that shouldn't be modified
    "POSTURE_WEIGHTS": [0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05],
    "POSTURE_THRESHOLDS": {
        "head_tilt": 1.2,  # head forward threshold
        "neck_angle": 45.0,  # max neck angle
        "shoulder_level": 5.0,  # shoulder level threshold
        "shoulder_roll": 2.0,  # shoulder roll threshold
        "spine_angle": 45.0,  # max spine angle
    },
    "MIN_DETECTION_CONFIDENCE": 0.5,
    "MIN_TRACKING_CONFIDENCE": 0.5,
    "SCORE_BUFFER_SIZE": 1000,
    "SCORE_WINDOW_SIZE": 5,
    "SCORE_THRESHOLD": 65,
}


# ---------------------------
# Customizable settings - these can be modified by the user.
# ---------------------------
CUSTOMIZABLE_SETTINGS = {
    # Camera settings
    "DEFAULT_CAMERA_ID": 0,
    "DEFAULT_FPS": 30,
    # Pose detection settings
    "FRAME_WIDTH": 1280,
    "FRAME_HEIGHT": 720,
    "MODEL_COMPLEXITY": 1,
    # Notification settings
    "NOTIFICATION_COOLDOWN": 300,  # 5 minutes
    "POOR_POSTURE_THRESHOLD": 60,
    "DEFAULT_POSTURE_MESSAGE": "Please sit up straight!",
    # Tracking intervals: defaults are now just 15, 30, and 60 minutes.
    "TRACKING_INTERVALS": {
        "Every 15 minutes": 15,
        "Every 30 minutes": 30,
        "Every hour": 60,
    },
    "TRACKING_DURATION_MINUTES": 1,
    "ENABLE_DATABASE_LOGGING": False,
    "DB_WRITE_INTERVAL_SECONDS": 900,
}


def load_user_settings():
    try:
        if os.path.exists(USER_SETTINGS_FILE):
            with open(USER_SETTINGS_FILE, "r") as f:
                user_settings = json.load(f)
            CUSTOMIZABLE_SETTINGS.update(user_settings)
    except Exception as e:
        print(f"Error loading user settings: {e}")


def save_user_settings():
    try:
        with open(USER_SETTINGS_FILE, "w") as f:
            json.dump(CUSTOMIZABLE_SETTINGS, f, indent=4)
    except Exception as e:
        print(f"Error saving user settings: {e}")


def get_setting(key):
    if key in IMMUTABLE_SETTINGS:
        return IMMUTABLE_SETTINGS[key]
    if key in CUSTOMIZABLE_SETTINGS:
        return CUSTOMIZABLE_SETTINGS[key]
    raise KeyError(f"Unknown setting: {key}")


def update_setting(key, value):
    if key in IMMUTABLE_SETTINGS:
        raise KeyError(f"Cannot modify immutable setting: {key}")
    if key in CUSTOMIZABLE_SETTINGS:
        CUSTOMIZABLE_SETTINGS[key] = value
        save_user_settings()
    else:
        raise KeyError(f"Unknown setting: {key}")


load_user_settings()
