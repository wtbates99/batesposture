from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import anthropic as _anthropic
    _AVAILABLE = True
except ImportError:
    _anthropic = None  # type: ignore[assignment]
    _AVAILABLE = False

# Haiku for real-time chat: fast, cheap, perfectly capable for coaching
_MODEL = "claude-haiku-4-5"

_SYSTEM_TEMPLATE = """\
You are a friendly, expert posture coach embedded in a live posture-monitoring app.
You have real-time data from the user's current tracking session.

Session data:
- Current score : {score:.0f}/100  ({grade})
- Session avg   : {avg:.0f}   Min: {min:.0f}   Max: {max:.0f}
- Duration      : {duration}
- Best streak of good posture: {best_streak}
- Current streak: {current_streak}
{issues_line}

Guidelines:
- Be conversational, warm, and specific. Use their real numbers.
- Keep answers short (2-4 sentences) unless asked for more.
- Give actionable, concrete advice — not generic platitudes.
- Suggest specific stretches or exercises when relevant.
- If no session data is available yet, answer general posture questions helpfully.
"""


def _fmt_duration(seconds: float) -> str:
    m, s = int(seconds) // 60, int(seconds) % 60
    return f"{m}m {s:02d}s" if m > 0 else f"{s}s"


def _grade(score: float) -> str:
    if score >= 85: return "Excellent"
    if score >= 70: return "Good"
    if score >= 55: return "Fair"
    return "Poor"


class AiCoachService:
    """Wraps the Anthropic client for streaming posture coaching conversations."""

    def __init__(self) -> None:
        self._client: Any = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """True when the anthropic package is installed."""
        return _AVAILABLE

    @staticmethod
    def is_configured() -> bool:
        """True when an API key is present in the environment."""
        return _AVAILABLE and bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    def build_system_prompt(
        self,
        session_stats: dict,
        metrics: Optional[dict] = None,
    ) -> str:
        count = session_stats.get("count", 0)
        avg = session_stats.get("avg", 0.0) if count else 0.0

        issues: list[str] = []
        if metrics:
            if metrics.get("neck_angle", 0.0) > 15.0:
                issues.append("forward head / neck angle")
            if metrics.get("shoulder_vertical_delta", 0.0) > 0.05:
                issues.append("uneven shoulders")
            if metrics.get("spine_angle", 0.0) > 10.0:
                issues.append("spinal tilt")
        issues_line = (
            f"Issues detected: {', '.join(issues)}." if issues
            else "No significant postural issues currently detected."
        )

        return _SYSTEM_TEMPLATE.format(
            score=avg,
            grade=_grade(avg),
            avg=avg,
            min=session_stats.get("min", 0.0),
            max=session_stats.get("max", 0.0),
            duration=_fmt_duration(session_stats.get("duration_s", 0.0)),
            best_streak=_fmt_duration(session_stats.get("best_streak_s", 0.0)),
            current_streak=_fmt_duration(session_stats.get("current_streak_s", 0.0)),
            issues_line=issues_line,
        )

    def stream(self, messages: list[dict], system_prompt: str) -> Any:
        """Return a synchronous streaming context manager (use with `with`)."""
        if not _AVAILABLE:
            raise RuntimeError("anthropic package not installed")
        if self._client is None:
            self._client = _anthropic.Anthropic()
        return self._client.messages.stream(
            model=_MODEL,
            max_tokens=512,
            system=system_prompt,
            messages=messages,
        )
