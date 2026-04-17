from __future__ import annotations

from importlib import import_module
from typing import Any

import mediapipe as mp


def load_mediapipe_solutions(mp_module: Any | None = None) -> Any:
    """Return the legacy MediaPipe solutions namespace across package layouts.

    Some MediaPipe wheels expose the legacy namespace as ``mediapipe.solutions``,
    while older layouts package it under ``mediapipe.python.solutions``. Prefer
    the public attribute when present, and otherwise fall back to the legacy path.
    """

    module = mp_module or mp
    solutions = getattr(module, "solutions", None)
    if solutions is not None:
        return solutions
    return import_module("mediapipe.python.solutions")


MP_SOLUTIONS = load_mediapipe_solutions()
