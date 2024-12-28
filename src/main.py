from PyQt6.QtWidgets import QApplication
from tray_application import PostureTrackerTray
import sys
import os


def main():
    app = QApplication(sys.argv)

    lock_file = os.path.join(os.path.expanduser("~"), ".posture_tracker.lock")

    if os.path.exists(lock_file):
        print("Application is already running!")
        sys.exit(1)

    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))

        app.setQuitOnLastWindowClosed(False)
        tray = PostureTrackerTray()
        exit_code = app.exec()

    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
