import os
import sys

import psutil
from PyQt6.QtWidgets import QApplication

from tray_application import PostureTrackerTray


def kill_existing_instance(lock_file):
    """Kill existing instance using PID from lock file"""
    try:
        with open(lock_file, "r") as f:
            old_pid = int(f.read().strip())

        try:
            process = psutil.Process(old_pid)
            if "python" in process.name().lower():  # Verify it's a Python process
                process.terminate()
                process.wait(timeout=3)  # Wait for process to terminate
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            pass

    except (FileNotFoundError, ValueError):
        pass

    # Remove stale lock file
    if os.path.exists(lock_file):
        os.remove(lock_file)


def main():
    app = QApplication(sys.argv)

    lock_file = os.path.join(os.path.expanduser("~"), ".posture_tracker.lock")

    if os.path.exists(lock_file):
        kill_existing_instance(lock_file)

    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))

        app.setQuitOnLastWindowClosed(False)
        PostureTrackerTray()
        exit_code = app.exec()

    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
