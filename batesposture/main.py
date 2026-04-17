import logging
import logging.handlers
import os
import sys

import psutil
from PyQt6.QtCore import QLockFile
from PyQt6.QtWidgets import QApplication

from .application import ApplicationFacade
from .services.settings_service import get_app_data_dir

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_LOG_DATE_FMT = "%H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    datefmt=_LOG_DATE_FMT,
)

# Also persist logs to a rotating file so they survive restarts
try:
    if sys.platform == "darwin":
        _log_dir = os.path.join(
            os.path.expanduser("~"), "Library", "Logs", "BatesPosture"
        )
    else:
        _log_dir = os.path.join(os.path.expanduser("~"), ".batesposture_logs")
    os.makedirs(_log_dir, exist_ok=True)
    _file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(_log_dir, "app.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    _file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FMT))
    logging.getLogger().addHandler(_file_handler)
except OSError as _e:
    logging.getLogger(__name__).warning("Could not set up log file: %s", _e)

logger = logging.getLogger(__name__)


def _process_looks_like_batesposture(pid: int) -> bool:
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False

    try:
        cmdline = " ".join(process.cmdline()).lower()
    except (psutil.AccessDenied, psutil.ZombieProcess):
        cmdline = ""
    if "batesposture" in cmdline:
        return True

    try:
        name = process.name().lower()
    except (psutil.AccessDenied, psutil.ZombieProcess):
        name = ""
    return "batesposture" in name


def _acquire_single_instance_lock(lock_file: str) -> QLockFile | None:
    """Acquire the app lock without terminating unrelated processes."""
    lock = QLockFile(lock_file)
    # Long-running GUI app: never treat an active lock as stale based on age alone.
    lock.setStaleLockTime(0)
    if lock.tryLock():
        return lock

    has_info, pid, hostname, appname = lock.getLockInfo()
    if pid is not None and not _process_looks_like_batesposture(pid):
        logger.warning(
            "Removing stale lock file for PID %s (host=%s, app=%s)",
            pid,
            hostname or "unknown",
            appname or "unknown",
        )
        if lock.removeStaleLockFile() and lock.tryLock():
            return lock

    logger.info("Another BatesPosture instance is already running")
    if has_info:
        logger.info(
            "Active lock details: pid=%s host=%s app=%s",
            pid,
            hostname or "unknown",
            appname or "unknown",
        )
    return None


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("BatesPosture")

    lock_file = os.path.join(get_app_data_dir(), "batesposture.lock")
    lock = _acquire_single_instance_lock(lock_file)
    if lock is None:
        sys.exit(0)

    try:
        app.setQuitOnLastWindowClosed(False)
        facade = ApplicationFacade(app)
        exit_code = facade.run()

    finally:
        if lock.isLocked():
            lock.unlock()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
