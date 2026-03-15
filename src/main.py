import logging
import os
import sys

import psutil
from PyQt6.QtWidgets import QApplication

from application import ApplicationFacade

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _kill_existing_instance(lock_file: str) -> None:
    """Terminate a previous instance whose PID is stored in *lock_file*."""
    try:
        with open(lock_file) as f:
            old_pid = int(f.read().strip())
        try:
            process = psutil.Process(old_pid)
            if "python" in process.name().lower():
                process.terminate()
                process.wait(timeout=3)
                logger.info("Terminated previous instance (PID %d)", old_pid)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            pass
    except (FileNotFoundError, ValueError):
        pass

    if os.path.exists(lock_file):
        os.remove(lock_file)


def main() -> None:
    app = QApplication(sys.argv)

    lock_file = os.path.join(os.path.expanduser("~"), ".posture_tracker.lock")

    if os.path.exists(lock_file):
        _kill_existing_instance(lock_file)

    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))

        app.setQuitOnLastWindowClosed(False)
        facade = ApplicationFacade(app)
        exit_code = facade.run()

    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
