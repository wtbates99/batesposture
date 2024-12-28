from PyQt6.QtWidgets import QApplication
from tray_application import PostureTrackerTray
import sys


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running when all windows are closed

    tray = PostureTrackerTray()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
