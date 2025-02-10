import json
import os

# Path where user-customizable settings are saved/restored.
USER_SETTINGS_FILE = "user_settings.json"

# ---------------------------
# Immutable settings - these cannot be changed through the UI.
# ---------------------------
IMMUTABLE_SETTINGS = {
    "ICON_PATH": "icon.png",
    "DEFAULT_DB_NAME": "posture_data.db",
    # Core algorithm weights and thresholds that shouldn't be modified
    "POSTURE_WEIGHTS": [0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05],
    "POSTURE_THRESHOLDS": {
        "head_tilt": 1.2,  # head forward threshold
        "neck_angle": 45.0,  # max neck angle
        "shoulder_level": 5.0,  # shoulder level threshold
        "shoulder_roll": 2.0,  # shoulder roll threshold
        "spine_angle": 45.0,  # max spine angle
    },
}

# ---------------------------
# Customizable settings - these can be modified by the user.
# ---------------------------
CUSTOMIZABLE_SETTINGS = {
    # Camera settings
    "DEFAULT_CAMERA_ID": 0,
    "DEFAULT_FPS": 30,
    # Pose detection settings
    "MIN_DETECTION_CONFIDENCE": 0.5,
    "MIN_TRACKING_CONFIDENCE": 0.5,
    "FRAME_WIDTH": 1280,
    "FRAME_HEIGHT": 720,
    "MODEL_COMPLEXITY": 1,
    # Score history settings
    "SCORE_BUFFER_SIZE": 1000,
    "SCORE_WINDOW_SIZE": 5,
    "SCORE_THRESHOLD": 65,
    # Notification settings
    "NOTIFICATION_COOLDOWN": 300,  # 5 minutes
    "POOR_POSTURE_THRESHOLD": 60,
    "DEFAULT_POSTURE_MESSAGE": "Please sit up straight!",
    # Tracking intervals
    "TRACKING_INTERVALS": {
        "Continuous": 0,
        "Every 15 minutes": 15,
        "Every 30 minutes": 30,
        "Every hour": 60,
        "Every 2 hours": 120,
        "Every 4 hours": 240,
    },
}


def load_user_settings():
    """Load user settings from a JSON file and update the customizable settings."""
    try:
        if os.path.exists(USER_SETTINGS_FILE):
            with open(USER_SETTINGS_FILE, "r") as f:
                user_settings = json.load(f)
            CUSTOMIZABLE_SETTINGS.update(user_settings)
    except Exception as e:
        print(f"Error loading user settings: {e}")


def save_user_settings():
    """Save the current customizable settings to a JSON file."""
    try:
        with open(USER_SETTINGS_FILE, "w") as f:
            json.dump(CUSTOMIZABLE_SETTINGS, f, indent=4)
    except Exception as e:
        print(f"Error saving user settings: {e}")


def get_setting(key):
    """Get a setting value, checking both immutable and customizable settings."""
    if key in IMMUTABLE_SETTINGS:
        return IMMUTABLE_SETTINGS[key]
    if key in CUSTOMIZABLE_SETTINGS:
        return CUSTOMIZABLE_SETTINGS[key]
    raise KeyError(f"Unknown setting: {key}")


def update_setting(key, value):
    """Update a customizable setting. Raises KeyError if trying to update an immutable setting."""
    if key in IMMUTABLE_SETTINGS:
        raise KeyError(f"Cannot modify immutable setting: {key}")
    if key in CUSTOMIZABLE_SETTINGS:
        CUSTOMIZABLE_SETTINGS[key] = value
        save_user_settings()
    else:
        raise KeyError(f"Unknown setting: {key}")


# Load user settings on module import
load_user_settings()

# Remove all the individual settings variables since they're now in the dictionaries
