from __future__ import annotations

from typing import Callable, Dict

from PyQt6.QtCore import QObject, QTimer


class TaskScheduler(QObject):
    """Lightweight scheduler built on QTimer for periodic tasks."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timers: Dict[str, QTimer] = {}

    def schedule(
        self, name: str, interval_ms: int, callback: Callable[[], None]
    ) -> None:
        if name in self._timers:
            self.cancel(name)
        timer = QTimer(self)
        timer.timeout.connect(callback)
        timer.start(interval_ms)
        self._timers[name] = timer

    def single_shot(self, delay_ms: int, callback: Callable[[], None]) -> None:
        QTimer.singleShot(delay_ms, callback)

    def cancel(self, name: str) -> None:
        timer = self._timers.pop(name, None)
        if timer:
            timer.stop()
            timer.deleteLater()

    def shutdown(self) -> None:
        for timer in self._timers.values():
            timer.stop()
            timer.deleteLater()
        self._timers.clear()
