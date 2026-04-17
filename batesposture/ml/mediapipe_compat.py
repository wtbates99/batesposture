from __future__ import annotations

from importlib import import_module
from typing import Any

import mediapipe as mp


def load_mediapipe_solutions(mp_module: Any | None = None) -> Any:
    """Return the legacy MediaPipe solutions namespace across package layouts.

    Newer MediaPipe wheels still ship ``mediapipe.python.solutions`` but no longer
    reliably re-export it as ``mediapipe.solutions``. Prefer the public attribute
    when present, and otherwise fall back to the packaged legacy namespace.
    """

    module = mp_module or mp
    solutions = getattr(module, "solutions", None)
    if solutions is not None:
        return solutions
    return import_module("mediapipe.python.solutions")


MP_SOLUTIONS = load_mediapipe_solutions()
