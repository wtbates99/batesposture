from __future__ import annotations

from typing import Dict, List, Optional

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.settings_service import SettingsService


class SettingsDialog(QDialog):
    SECTION_DEFS = [
        ("camera", "Camera & Video", QStyle.StandardPixmap.SP_ComputerIcon),
        (
            "notifications",
            "Notifications",
            QStyle.StandardPixmap.SP_MessageBoxInformation,
        ),
        ("tracking", "Tracking", QStyle.StandardPixmap.SP_BrowserReload),
        ("advanced", "Advanced", QStyle.StandardPixmap.SP_FileDialogDetailedView),
    ]

    def __init__(
        self, settings_service: SettingsService, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings_service
        self.runtime_settings = settings_service.runtime
        self.ml_settings = settings_service.ml
        self.profile_settings = settings_service.profile
        self.validation_errors: Dict[str, str] = {}

        self.setWindowTitle("Posture Settings")
        self.resize(760, 560)

        self.hero_card = self._build_hero_card()
        self.section_list = self._build_section_list()
        self.section_stack = QStackedWidget()
        self.section_key_to_index: Dict[str, int] = {}

        for index, (key, _, _) in enumerate(self.SECTION_DEFS):
            page = self._build_section_widget(key)
            self.section_stack.addWidget(page)
            self.section_key_to_index[key] = index

        self.section_list.currentRowChanged.connect(self.section_stack.setCurrentIndex)
        self.section_list.setCurrentRow(0)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        body_layout = QHBoxLayout()
        body_layout.addWidget(self.section_list)
        body_layout.addWidget(self.section_stack, 1)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.hero_card)
        main_layout.addLayout(body_layout)
        main_layout.addWidget(self.button_box)
        self.setLayout(main_layout)

        self._handle_advanced_toggle(self.show_advanced_checkbox.isChecked())

    def _build_hero_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("heroCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)

        title = QLabel("Personalized posture coaching")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() + 2)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("Tune camera, alerts, and tracking in one place.")
        subtitle.setStyleSheet("color: #50535a;")

        summary = QLabel(self._summary_text())
        summary.setObjectName("heroSummary")
        summary.setWordWrap(True)

        self.show_advanced_checkbox = QCheckBox("Show advanced controls")
        self.show_advanced_checkbox.setChecked(False)
        self.show_advanced_checkbox.toggled.connect(self._handle_advanced_toggle)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(summary)
        layout.addWidget(
            self.show_advanced_checkbox, alignment=Qt.AlignmentFlag.AlignRight
        )

        card.setStyleSheet(
            """
            QFrame#heroCard {
                background-color: #f4f6fa;
                border: 1px solid #d6d9e0;
                border-radius: 8px;
                padding: 12px;
            }
            QLabel#heroSummary {
                color: #50535a;
            }
            """
        )
        self.hero_summary_label = summary
        return card

    def _summary_text(self) -> str:
        profile = self.profile_settings
        runtime = self.runtime_settings
        return (
            f"Baseline posture score: {profile.baseline_posture_score:.1f}%\n"
            f"Calibration status: {'Complete' if profile.has_completed_onboarding else 'Pending'}\n"
            f"Notifications: {'On' if runtime.notifications_enabled else 'Off'}"
        )

    def _build_section_list(self) -> QListWidget:
        widget = QListWidget()
        widget.setFixedWidth(220)
        widget.setSpacing(4)
        widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        widget.setAlternatingRowColors(True)
        for key, label, icon_name in self.SECTION_DEFS:
            icon = self.style().standardIcon(icon_name)
            item = QListWidgetItem(icon, label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            widget.addItem(item)
        return widget

    def _build_section_widget(self, key: str) -> QWidget:
        if key == "camera":
            return self._create_camera_page()
        if key == "notifications":
            return self._create_notifications_page()
        if key == "tracking":
            return self._create_tracking_page()
        if key == "advanced":
            return self._create_advanced_page()
        return QWidget()

    def _create_camera_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        capture_group = QGroupBox("Capture")
        capture_form = QFormLayout()
        self.camera_combo = QComboBox()
        cameras = self._available_cameras()
        if cameras:
            for cam_id, cam_name in cameras:
                self.camera_combo.addItem(cam_name, cam_id)
            current_cam = self.runtime_settings.default_camera_id
            index = self.camera_combo.findData(current_cam)
            if index != -1:
                self.camera_combo.setCurrentIndex(index)
        else:
            self.camera_combo.addItem("No camera found", -1)
            self.camera_combo.setEnabled(False)
        capture_form.addRow("Default camera:", self.camera_combo)

        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(self.runtime_settings.default_fps)
        capture_form.addRow("Frames per second:", self.fps_spinbox)

        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(100, 10000)
        self.width_spinbox.setValue(self.runtime_settings.frame_width)
        capture_form.addRow("Frame width:", self.width_spinbox)

        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(100, 10000)
        self.height_spinbox.setValue(self.runtime_settings.frame_height)
        capture_form.addRow("Frame height:", self.height_spinbox)

        capture_group.setLayout(capture_form)
        layout.addWidget(capture_group)
        layout.addWidget(
            self._help_label(
                "Choose the camera and resolution you typically use. Higher resolution improves detection at the cost of performance."
            )
        )
        layout.addStretch(1)
        return container

    def _create_notifications_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        alerts_group = QGroupBox("Alerts")
        alerts_form = QFormLayout()

        self.notifications_enabled_checkbox = QCheckBox("Enable desktop notifications")
        self.notifications_enabled_checkbox.setChecked(
            self.runtime_settings.notifications_enabled
        )
        alerts_form.addRow(self.notifications_enabled_checkbox)

        self.focus_mode_checkbox = QCheckBox("Pause reminders during focus mode")
        self.focus_mode_checkbox.setChecked(self.runtime_settings.focus_mode_enabled)
        alerts_form.addRow(self.focus_mode_checkbox)

        self.cooldown_spinbox = QSpinBox()
        self.cooldown_spinbox.setRange(30, 3600)
        self.cooldown_spinbox.setValue(self.runtime_settings.notification_cooldown)
        alerts_form.addRow("Notification cooldown (sec):", self.cooldown_spinbox)

        self.poor_posture_spinbox = QSpinBox()
        self.poor_posture_spinbox.setRange(10, 100)
        self.poor_posture_spinbox.setValue(self.runtime_settings.poor_posture_threshold)
        alerts_form.addRow("Poor posture threshold:", self.poor_posture_spinbox)

        self.posture_message_lineedit = QLineEdit()
        self.posture_message_lineedit.setText(
            self.runtime_settings.default_posture_message
        )
        self.posture_message_lineedit.textChanged.connect(
            self._validate_posture_message
        )
        alerts_form.addRow("Posture message:", self.posture_message_lineedit)

        self.posture_message_error = self._error_label()
        alerts_form.addRow("", self.posture_message_error)

        alerts_group.setLayout(alerts_form)

        logging_group = QGroupBox("Data logging")
        logging_form = QFormLayout()
        self.db_logging_checkbox = QCheckBox("Persist session data to the database")
        self.db_logging_checkbox.setChecked(
            self.runtime_settings.enable_database_logging
        )
        logging_form.addRow(self.db_logging_checkbox)

        self.db_write_interval_spinbox = QSpinBox()
        self.db_write_interval_spinbox.setRange(60, 3600)
        self.db_write_interval_spinbox.setSingleStep(60)
        self.db_write_interval_spinbox.setValue(
            self.runtime_settings.db_write_interval_seconds
        )
        logging_form.addRow(
            "Database write interval (sec):", self.db_write_interval_spinbox
        )
        logging_group.setLayout(logging_form)

        layout.addWidget(alerts_group)
        layout.addWidget(
            self._help_label(
                "Set thresholds and messaging for posture alerts. Focus mode keeps monitoring active but suppresses notifications."
            )
        )
        layout.addWidget(logging_group)
        layout.addWidget(
            self._help_label(
                "Enable logging to review history or export data. The interval controls how often entries are written."
            )
        )
        layout.addStretch(1)
        return container

    def _create_tracking_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        schedule_group = QGroupBox("Tracking cadence")
        schedule_layout = QVBoxLayout()

        self.tracking_table = QTableWidget()
        self.tracking_table.setColumnCount(2)
        self.tracking_table.setHorizontalHeaderLabels(["Label", "Minutes"])
        self.tracking_table.horizontalHeader().setStretchLastSection(True)
        self.tracking_table.verticalHeader().setVisible(False)
        self._populate_tracking_table()
        schedule_layout.addWidget(self.tracking_table)

        table_help = self._help_label(
            "Use descriptive labels so tray quick actions stay clear. Minutes can be zero for always-on tracking."
        )
        schedule_layout.addWidget(table_help)

        controls_layout = QHBoxLayout()
        self.new_interval_label_edit = QLineEdit()
        self.new_interval_label_edit.setPlaceholderText("Interval label")
        self.new_interval_spinbox = QSpinBox()
        self.new_interval_spinbox.setRange(0, 1440)
        self.new_interval_spinbox.setValue(30)
        self.add_interval_button = QPushButton("Add interval")
        self.add_interval_button.clicked.connect(self._add_tracking_interval)
        controls_layout.addWidget(self.new_interval_label_edit)
        controls_layout.addWidget(self.new_interval_spinbox)
        controls_layout.addWidget(self.add_interval_button)
        schedule_layout.addLayout(controls_layout)

        self.remove_interval_button = QPushButton("Remove selected")
        self.remove_interval_button.clicked.connect(self._remove_tracking_interval)
        schedule_layout.addWidget(self.remove_interval_button)

        self.interval_error_label = self._error_label()
        schedule_layout.addWidget(self.interval_error_label)

        schedule_group.setLayout(schedule_layout)

        duration_layout = QHBoxLayout()
        duration_label = QLabel("Tracking duration (minutes):")
        self.tracking_duration_spinbox = QSpinBox()
        self.tracking_duration_spinbox.setRange(1, 60)
        self.tracking_duration_spinbox.setValue(
            self.runtime_settings.tracking_duration_minutes
        )
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.tracking_duration_spinbox)

        layout.addWidget(schedule_group)
        layout.addLayout(duration_layout)
        layout.addWidget(
            self._help_label(
                "Intervals define how often tracking restarts. Duration controls how long each session runs when scheduled."
            )
        )
        layout.addStretch(1)
        return container

    def _create_advanced_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        core_group = QGroupBox("Detection tuning")
        core_form = QFormLayout()

        self.model_complexity_spinbox = QSpinBox()
        self.model_complexity_spinbox.setRange(0, 2)
        self.model_complexity_spinbox.setValue(self.ml_settings.model_complexity)
        core_form.addRow("Model complexity:", self.model_complexity_spinbox)

        self.detection_confidence_spinbox = QDoubleSpinBox()
        self.detection_confidence_spinbox.setRange(0.0, 1.0)
        self.detection_confidence_spinbox.setSingleStep(0.05)
        self.detection_confidence_spinbox.setDecimals(2)
        self.detection_confidence_spinbox.setValue(
            self.ml_settings.min_detection_confidence
        )
        core_form.addRow("Min detection confidence:", self.detection_confidence_spinbox)

        self.tracking_confidence_spinbox = QDoubleSpinBox()
        self.tracking_confidence_spinbox.setRange(0.0, 1.0)
        self.tracking_confidence_spinbox.setSingleStep(0.05)
        self.tracking_confidence_spinbox.setDecimals(2)
        self.tracking_confidence_spinbox.setValue(
            self.ml_settings.min_tracking_confidence
        )
        core_form.addRow("Min tracking confidence:", self.tracking_confidence_spinbox)

        self.score_buffer_spinbox = QSpinBox()
        self.score_buffer_spinbox.setRange(10, 10000)
        self.score_buffer_spinbox.setValue(self.ml_settings.score_buffer_size)
        core_form.addRow("Score buffer size:", self.score_buffer_spinbox)

        self.score_window_spinbox = QSpinBox()
        self.score_window_spinbox.setRange(1, 100)
        self.score_window_spinbox.setValue(self.ml_settings.score_window_size)
        core_form.addRow("Score window size:", self.score_window_spinbox)

        self.score_threshold_spinbox = QSpinBox()
        self.score_threshold_spinbox.setRange(0, 100)
        self.score_threshold_spinbox.setValue(self.ml_settings.score_threshold)
        core_form.addRow("Score threshold:", self.score_threshold_spinbox)

        core_group.setLayout(core_form)

        thresholds_group = QGroupBox("Posture thresholds")
        thresholds_form = QFormLayout()
        self.threshold_spinboxes: Dict[str, QDoubleSpinBox] = {}
        for key, value in self.ml_settings.posture_thresholds.items():
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(2)
            spinbox.setRange(0.0, 180.0)
            spinbox.setSingleStep(0.5)
            spinbox.setValue(float(value))
            label = key.replace("_", " ").title()
            thresholds_form.addRow(f"{label}:", spinbox)
            self.threshold_spinboxes[key] = spinbox
        thresholds_group.setLayout(thresholds_form)

        weights_group = QGroupBox("Posture weights")
        weights_form = QFormLayout()
        self.weight_spinboxes: List[QDoubleSpinBox] = []
        for index, weight in enumerate(self.ml_settings.posture_weights, start=1):
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(3)
            spinbox.setRange(0.0, 1.0)
            spinbox.setSingleStep(0.05)
            spinbox.setValue(float(weight))
            weights_form.addRow(f"Weight {index}:", spinbox)
            self.weight_spinboxes.append(spinbox)
        weights_group.setLayout(weights_form)

        layout.addWidget(core_group)
        layout.addWidget(
            self._help_label(
                "Adjust these values when experimenting with new models or unusual environments."
            )
        )
        layout.addWidget(thresholds_group)
        layout.addWidget(weights_group)
        layout.addStretch(1)
        return container

    def _help_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        help_font = QFont(label.font())
        help_font.setPointSize(max(help_font.pointSize() - 1, 8))
        label.setFont(help_font)
        label.setStyleSheet("color: #5e6066;")
        return label

    def _error_label(self) -> QLabel:
        label = QLabel("")
        label.setStyleSheet("color: #c13434;")
        label.setWordWrap(True)
        label.setVisible(False)
        return label

    def _handle_advanced_toggle(self, checked: bool) -> None:
        index = self.section_key_to_index.get("advanced")
        if index is None:
            return
        item = self.section_list.item(index)
        item.setHidden(not checked)
        if not checked and self.section_list.currentRow() == index:
            self.section_list.setCurrentRow(0)

    def _populate_tracking_table(self) -> None:
        intervals = self.runtime_settings.tracking_intervals
        self.tracking_table.setRowCount(0)
        for label, minutes in intervals.items():
            row_position = self.tracking_table.rowCount()
            self.tracking_table.insertRow(row_position)
            self.tracking_table.setItem(row_position, 0, QTableWidgetItem(label))
            self.tracking_table.setItem(row_position, 1, QTableWidgetItem(str(minutes)))

    def _add_tracking_interval(self) -> None:
        label = self.new_interval_label_edit.text().strip()
        if not label:
            self._show_error(
                "tracking_intervals",
                self.interval_error_label,
                "Provide a label before adding an interval.",
            )
            return
        minutes = self.new_interval_spinbox.value()
        row_position = self.tracking_table.rowCount()
        self.tracking_table.insertRow(row_position)
        self.tracking_table.setItem(row_position, 0, QTableWidgetItem(label))
        self.tracking_table.setItem(row_position, 1, QTableWidgetItem(str(minutes)))
        self.new_interval_label_edit.clear()
        self._clear_error("tracking_intervals", self.interval_error_label)

    def _remove_tracking_interval(self) -> None:
        selected_rows = {item.row() for item in self.tracking_table.selectedItems()}
        for row in sorted(selected_rows, reverse=True):
            self.tracking_table.removeRow(row)
        if selected_rows:
            self._clear_error("tracking_intervals", self.interval_error_label)

    def _available_cameras(self, max_index: int = 5):
        available = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append((i, f"Camera {i}"))
            cap.release()
        return available

    def _show_error(self, key: str, label: QLabel, message: str) -> None:
        self.validation_errors[key] = message
        label.setText(message)
        label.setVisible(True)

    def _clear_error(self, key: str, label: QLabel) -> None:
        self.validation_errors.pop(key, None)
        label.clear()
        label.setVisible(False)

    def _validate_posture_message(self) -> bool:
        message = self.posture_message_lineedit.text().strip()
        if not message:
            self._show_error(
                "posture_message",
                self.posture_message_error,
                "Posture message cannot be empty.",
            )
            return False
        if len(message) < 3:
            self._show_error(
                "posture_message",
                self.posture_message_error,
                "Use at least three characters for the reminder.",
            )
            return False
        self._clear_error("posture_message", self.posture_message_error)
        return True

    def _collect_tracking_intervals(self) -> Dict[str, int]:
        intervals: Dict[str, int] = {}
        for row in range(self.tracking_table.rowCount()):
            label_item = self.tracking_table.item(row, 0)
            minutes_item = self.tracking_table.item(row, 1)
            label = label_item.text().strip() if label_item else ""
            if not label:
                raise ValueError("Each interval needs a label.")
            try:
                minutes = int(minutes_item.text()) if minutes_item else 0
            except (TypeError, ValueError):
                raise ValueError(f"Minutes for '{label}' must be a whole number.")
            if minutes < 0:
                raise ValueError("Minutes cannot be negative.")
            intervals[label] = minutes
        if not intervals:
            raise ValueError("Add at least one tracking interval.")
        return intervals

    def _validate_tracking_intervals(self) -> Optional[Dict[str, int]]:
        try:
            intervals = self._collect_tracking_intervals()
        except ValueError as error:
            self._show_error(
                "tracking_intervals", self.interval_error_label, str(error)
            )
            return None
        self._clear_error("tracking_intervals", self.interval_error_label)
        return intervals

    def _validate_all(self) -> Optional[Dict[str, int]]:
        message_valid = self._validate_posture_message()
        intervals = self._validate_tracking_intervals()
        if not message_valid or intervals is None:
            return None
        return intervals

    def accept(self) -> None:
        intervals = self._validate_all()
        if intervals is None:
            QMessageBox.warning(
                self, "Settings", "Please resolve the highlighted fields before saving."
            )
            return

        runtime_updates: Dict[str, object] = {}

        cam_id = self.camera_combo.currentData()
        if cam_id is None or cam_id == -1:
            cam_id = self.runtime_settings.default_camera_id
        runtime_updates["default_camera_id"] = cam_id
        runtime_updates["default_fps"] = self.fps_spinbox.value()
        runtime_updates["frame_width"] = self.width_spinbox.value()
        runtime_updates["frame_height"] = self.height_spinbox.value()
        runtime_updates[
            "notifications_enabled"
        ] = self.notifications_enabled_checkbox.isChecked()
        runtime_updates["focus_mode_enabled"] = self.focus_mode_checkbox.isChecked()
        runtime_updates["notification_cooldown"] = self.cooldown_spinbox.value()
        runtime_updates["poor_posture_threshold"] = self.poor_posture_spinbox.value()
        runtime_updates[
            "default_posture_message"
        ] = self.posture_message_lineedit.text().strip()
        runtime_updates[
            "enable_database_logging"
        ] = self.db_logging_checkbox.isChecked()
        runtime_updates[
            "db_write_interval_seconds"
        ] = self.db_write_interval_spinbox.value()
        runtime_updates["tracking_intervals"] = intervals
        runtime_updates[
            "tracking_duration_minutes"
        ] = self.tracking_duration_spinbox.value()

        ml_updates = {
            "model_complexity": self.model_complexity_spinbox.value(),
            "min_detection_confidence": self.detection_confidence_spinbox.value(),
            "min_tracking_confidence": self.tracking_confidence_spinbox.value(),
            "score_buffer_size": self.score_buffer_spinbox.value(),
            "score_window_size": self.score_window_spinbox.value(),
            "score_threshold": self.score_threshold_spinbox.value(),
            "posture_thresholds": {
                key: spinbox.value()
                for key, spinbox in self.threshold_spinboxes.items()
            },
            "posture_weights": [spinbox.value() for spinbox in self.weight_spinboxes],
        }

        self._settings.update_runtime(**runtime_updates)
        self._settings.update_ml(**ml_updates)
        self._settings.save_all()
        self.hero_summary_label.setText(self._summary_text())
        super().accept()
