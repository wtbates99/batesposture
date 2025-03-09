from PyQt6.QtWidgets import (
    QDialog,
    QTabWidget,
    QWidget,
    QFormLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QDialogButtonBox,
    QLabel,
    QComboBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QCheckBox,
)
import cv2

from settings import CUSTOMIZABLE_SETTINGS, save_user_settings


class SettingsInterface(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customizable Settings")
        self.resize(500, 400)
        self.tabs = QTabWidget()

        # Create tabs
        self.camera_tab = QWidget()
        self.general_tab = QWidget()
        self.tracking_tab = QWidget()

        self.init_camera_tab()
        self.init_general_tab()
        self.init_tracking_tab()

        self.tabs.addTab(self.camera_tab, "Camera")
        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.tracking_tab, "Tracking")

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.button_box)
        self.setLayout(main_layout)

    def init_camera_tab(self):
        layout = QFormLayout()
        # Default Camera selection using QComboBox with available cameras.
        self.camera_combo = QComboBox()
        cameras = self.get_available_cameras()
        if cameras:
            for cam_id, cam_name in cameras:
                self.camera_combo.addItem(cam_name, cam_id)
            current_cam = CUSTOMIZABLE_SETTINGS.get("DEFAULT_CAMERA_ID", 0)
            index = self.camera_combo.findData(current_cam)
            if index != -1:
                self.camera_combo.setCurrentIndex(index)
        else:
            self.camera_combo.addItem("No Camera Found", -1)
            self.camera_combo.setEnabled(False)
        layout.addRow("Default Camera:", self.camera_combo)

        # Frames Per Second setting
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(CUSTOMIZABLE_SETTINGS.get("DEFAULT_FPS", 30))
        layout.addRow("Frames Per Second:", self.fps_spinbox)

        # Frame width setting
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(100, 10000)
        self.width_spinbox.setValue(CUSTOMIZABLE_SETTINGS.get("FRAME_WIDTH", 1280))
        layout.addRow("Frame Width:", self.width_spinbox)

        # Frame height setting
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(100, 10000)
        self.height_spinbox.setValue(CUSTOMIZABLE_SETTINGS.get("FRAME_HEIGHT", 720))
        layout.addRow("Frame Height:", self.height_spinbox)

        # Model complexity setting
        self.model_complexity_spinbox = QSpinBox()
        self.model_complexity_spinbox.setRange(0, 2)
        self.model_complexity_spinbox.setValue(
            CUSTOMIZABLE_SETTINGS.get("MODEL_COMPLEXITY", 1)
        )
        layout.addRow("Model Complexity:", self.model_complexity_spinbox)

        self.camera_tab.setLayout(layout)

    def init_general_tab(self):
        layout = QFormLayout()

        # Notification Cooldown setting
        self.cooldown_spinbox = QSpinBox()
        self.cooldown_spinbox.setRange(1, 3600)
        self.cooldown_spinbox.setValue(
            CUSTOMIZABLE_SETTINGS.get("NOTIFICATION_COOLDOWN", 300)
        )
        layout.addRow("Notification Cooldown (sec):", self.cooldown_spinbox)

        # Poor Posture Threshold setting
        self.poor_posture_spinbox = QSpinBox()
        self.poor_posture_spinbox.setRange(1, 100)
        self.poor_posture_spinbox.setValue(
            CUSTOMIZABLE_SETTINGS.get("POOR_POSTURE_THRESHOLD", 60)
        )
        layout.addRow("Poor Posture Threshold:", self.poor_posture_spinbox)

        # Default Posture Message setting
        self.posture_message_lineedit = QLineEdit()
        self.posture_message_lineedit.setText(
            CUSTOMIZABLE_SETTINGS.get(
                "DEFAULT_POSTURE_MESSAGE", "Please sit up straight!"
            )
        )
        layout.addRow("Posture Message:", self.posture_message_lineedit)

        # Add this block:
        self.db_logging_checkbox = QCheckBox()
        self.db_logging_checkbox.setChecked(
            CUSTOMIZABLE_SETTINGS.get("ENABLE_DATABASE_LOGGING", False)
        )
        layout.addRow("Enable Database Logging", self.db_logging_checkbox)

        # Database write interval setting
        self.db_write_interval_spinbox = QSpinBox()
        self.db_write_interval_spinbox.setRange(1, 3600)
        self.db_write_interval_spinbox.setValue(
            CUSTOMIZABLE_SETTINGS.get("DB_WRITE_INTERVAL_SECONDS", 900)
        )
        layout.addRow("Database Write Interval (sec):", self.db_write_interval_spinbox)

        self.general_tab.setLayout(layout)

    def init_tracking_tab(self):
        main_layout = QVBoxLayout()

        # Table to display/edit tracking intervals
        self.tracking_table = QTableWidget()
        self.tracking_table.setColumnCount(2)
        self.tracking_table.setHorizontalHeaderLabels(["Label", "Minutes"])
        self.tracking_table.horizontalHeader().setStretchLastSection(True)
        self.populate_tracking_table()

        main_layout.addWidget(QLabel("Tracking Intervals (Label : Minutes):"))
        main_layout.addWidget(self.tracking_table)

        # Add tracking duration setting
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Tracking Duration (minutes):")
        self.tracking_duration_spinbox = QSpinBox()
        self.tracking_duration_spinbox.setRange(1, 60)  # 1 to 60 minutes
        self.tracking_duration_spinbox.setValue(
            CUSTOMIZABLE_SETTINGS.get("TRACKING_DURATION_MINUTES", 1)
        )
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.tracking_duration_spinbox)
        main_layout.addLayout(duration_layout)

        # Controls to add a new tracking interval
        add_layout = QHBoxLayout()
        self.new_interval_label_edit = QLineEdit()
        self.new_interval_label_edit.setPlaceholderText("Interval Label")
        self.new_interval_spinbox = QSpinBox()
        self.new_interval_spinbox.setRange(0, 1440)
        self.new_interval_spinbox.setValue(15)
        self.add_interval_button = QPushButton("Add Interval")
        self.add_interval_button.clicked.connect(self.add_tracking_interval)
        add_layout.addWidget(self.new_interval_label_edit)
        add_layout.addWidget(self.new_interval_spinbox)
        add_layout.addWidget(self.add_interval_button)
        main_layout.addLayout(add_layout)

        # Button to remove the selected tracking interval
        self.remove_interval_button = QPushButton("Remove Selected Interval")
        self.remove_interval_button.clicked.connect(self.remove_tracking_interval)
        main_layout.addWidget(self.remove_interval_button)

        self.tracking_tab.setLayout(main_layout)

    def populate_tracking_table(self):
        intervals = CUSTOMIZABLE_SETTINGS.get("TRACKING_INTERVALS", {})
        self.tracking_table.setRowCount(0)
        for label, minutes in intervals.items():
            row_position = self.tracking_table.rowCount()
            self.tracking_table.insertRow(row_position)
            self.tracking_table.setItem(row_position, 0, QTableWidgetItem(label))
            self.tracking_table.setItem(row_position, 1, QTableWidgetItem(str(minutes)))

    def add_tracking_interval(self):
        label = self.new_interval_label_edit.text().strip()
        if not label:
            return  # Optionally, you might show a warning message.
        minutes = self.new_interval_spinbox.value()
        row_position = self.tracking_table.rowCount()
        self.tracking_table.insertRow(row_position)
        self.tracking_table.setItem(row_position, 0, QTableWidgetItem(label))
        self.tracking_table.setItem(row_position, 1, QTableWidgetItem(str(minutes)))
        self.new_interval_label_edit.clear()

    def remove_tracking_interval(self):
        selected_rows = set()
        for item in self.tracking_table.selectedItems():
            selected_rows.add(item.row())
        for row in sorted(selected_rows, reverse=True):
            self.tracking_table.removeRow(row)

    def get_available_cameras(self, max_index=5):
        available = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append((i, f"Camera {i}"))
            cap.release()
        return available

    def accept(self):
        # Update Camera settings
        cam_id = self.camera_combo.currentData()
        if cam_id is None or cam_id == -1:
            cam_id = CUSTOMIZABLE_SETTINGS.get("DEFAULT_CAMERA_ID", 0)
        CUSTOMIZABLE_SETTINGS["DEFAULT_CAMERA_ID"] = cam_id
        CUSTOMIZABLE_SETTINGS["DEFAULT_FPS"] = self.fps_spinbox.value()
        CUSTOMIZABLE_SETTINGS["FRAME_WIDTH"] = self.width_spinbox.value()
        CUSTOMIZABLE_SETTINGS["FRAME_HEIGHT"] = self.height_spinbox.value()
        CUSTOMIZABLE_SETTINGS[
            "MODEL_COMPLEXITY"
        ] = self.model_complexity_spinbox.value()

        # Update General settings
        CUSTOMIZABLE_SETTINGS["NOTIFICATION_COOLDOWN"] = self.cooldown_spinbox.value()
        CUSTOMIZABLE_SETTINGS[
            "POOR_POSTURE_THRESHOLD"
        ] = self.poor_posture_spinbox.value()
        CUSTOMIZABLE_SETTINGS[
            "DEFAULT_POSTURE_MESSAGE"
        ] = self.posture_message_lineedit.text()

        # Add this line:
        CUSTOMIZABLE_SETTINGS[
            "ENABLE_DATABASE_LOGGING"
        ] = self.db_logging_checkbox.isChecked()
        CUSTOMIZABLE_SETTINGS[
            "DB_WRITE_INTERVAL_SECONDS"
        ] = self.db_write_interval_spinbox.value()

        # Update Tracking Intervals from table
        intervals = {}
        row_count = self.tracking_table.rowCount()
        for row in range(row_count):
            label_item = self.tracking_table.item(row, 0)
            minutes_item = self.tracking_table.item(row, 1)
            if label_item and minutes_item:
                label = label_item.text().strip()
                try:
                    minutes = int(minutes_item.text())
                except ValueError:
                    minutes = 0
                intervals[label] = minutes
        CUSTOMIZABLE_SETTINGS["TRACKING_INTERVALS"] = intervals
        CUSTOMIZABLE_SETTINGS[
            "TRACKING_DURATION_MINUTES"
        ] = self.tracking_duration_spinbox.value()

        save_user_settings()
        super().accept()
