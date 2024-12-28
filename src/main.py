from PyQt6.QtWidgets import QApplication
from tray_application import PostureTrackerTray
import sys

# Global reference to prevent garbage collection
global_tray = None


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    global global_tray
    global_tray = PostureTrackerTray()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
