"""BatesPosture package initialization."""

# Import MediaPipe before project PyQt6 modules on Windows. MediaPipe wheels can
# fail DLL initialization when PyQt6 is loaded first in the same process.
from .ml import mediapipe_compat as _mediapipe_compat  # noqa: F401
