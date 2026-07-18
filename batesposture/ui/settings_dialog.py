from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.settings_service import SettingsService
from .theme import settings_stylesheet, theme_colors


class SettingsDialog(QDialog):
    SECTION_DEFS = [
        ("appearance", "Appearance", QStyle.StandardPixmap.SP_DesktopIcon),
        ("camera", "Camera & Video", QStyle.StandardPixmap.SP_ComputerIcon),
        (
            "notifications",
            "Notifications",
            QStyle.StandardPixmap.SP_MessageBoxInformation,
        ),
        ("tracking", "Tracking", QStyle.StandardPixmap.SP_BrowserReload),
        ("data", "Data", QStyle.StandardPixmap.SP_DriveHDIcon),
        ("advanced", "Advanced", QStyle.StandardPixmap.SP_FileDialogDetailedView),
    ]

    _PAGE_META = {
        "appearance": ("Appearance", "Choose how BatesPosture fits your desktop."),
        "camera": (
            "Camera & Video",
            "Configure your camera source and capture resolution.",
        ),
        "notifications": (
            "Notifications",
            "Control when and how posture alerts are delivered.",
        ),
        "tracking": ("Tracking", "Define tracking schedules and session duration."),
        "data": ("Data", "Configure session data logging and storage."),
        "advanced": ("Advanced", "Fine-tune detection models and scoring parameters."),
    }

    def __init__(
        self, settings_service: SettingsService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings_service
        self.runtime_settings = settings_service.runtime
        self.ml_settings = settings_service.ml
        self.profile_settings = settings_service.profile
        self.validation_errors: dict[str, str] = {}

        self.setWindowTitle("BatesPosture Settings")
        self.setMinimumSize(800, 560)
        self.resize(960, 700)
        self._apply_theme(self.profile_settings.preferred_theme)

        self.section_list = self._build_nav_list()
        self.section_stack = QStackedWidget()
        self.section_key_to_index: dict[str, int] = {}

        for index, (key, _, _) in enumerate(self.SECTION_DEFS):
            self.section_stack.addWidget(self._build_section_widget(key))
            self.section_key_to_index[key] = index

        self.section_list.currentRowChanged.connect(self.section_stack.setCurrentIndex)
        self.section_list.setCurrentRow(0)

        self.show_advanced_checkbox = QCheckBox("Show Advanced")
        self.show_advanced_checkbox.setObjectName("advancedToggle")
        self.show_advanced_checkbox.setChecked(False)
        self.show_advanced_checkbox.toggled.connect(self._handle_advanced_toggle)

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        brand_name = QLabel("BatesPosture")
        brand_name.setObjectName("brandName")
        brand_name.setContentsMargins(16, 18, 16, 0)
        brand_detail = QLabel("Posture monitor")
        brand_detail.setObjectName("brandDetail")
        brand_detail.setContentsMargins(16, 0, 16, 12)
        sidebar_layout.addWidget(brand_name)
        sidebar_layout.addWidget(brand_detail)
        sidebar_layout.addWidget(self.section_list, 1)
        sidebar_layout.addWidget(self.show_advanced_checkbox)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(208)
        sidebar.setLayout(sidebar_layout)

        self._status_label = QLabel(self._status_text())
        self._status_label.setObjectName("statusLabel")

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Save Settings")
        ok_btn.setObjectName("primaryButton")

        bottom_bar = QFrame()
        bottom_bar.setObjectName("bottomBar")
        bottom_bar.setFixedHeight(52)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 0, 16, 0)
        bottom_layout.addWidget(self._status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(sidebar)
        body.addWidget(sep)
        body.addWidget(self.section_stack, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(body, 1)
        root.addWidget(bottom_bar)

        self._handle_advanced_toggle(False)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _status_text(self) -> str:
        p = self.profile_settings
        r = self.runtime_settings
        status = "Calibrated" if p.has_completed_onboarding else "Not calibrated"
        notif = "on" if r.notifications_enabled else "off"
        return (
            f"Baseline: {p.baseline_posture_score:.0f}%  ·  {status}"
            f"  ·  Notifications {notif}"
        )

    def _build_nav_list(self) -> QListWidget:
        widget = QListWidget()
        widget.setObjectName("navList")
        widget.setSpacing(2)
        widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        for _, label, icon_name in self.SECTION_DEFS:
            icon = self.style().standardIcon(icon_name)
            item = QListWidgetItem(icon, f"  {label}")
            item.setSizeHint(QSize(0, 44))
            widget.addItem(item)
        return widget

    def _build_section_widget(self, key: str) -> QWidget:
        builders = {
            "appearance": self._create_appearance_page,
            "camera": self._create_camera_page,
            "notifications": self._create_notifications_page,
            "tracking": self._create_tracking_page,
            "data": self._create_data_page,
            "advanced": self._create_advanced_page,
        }
        inner = builders.get(key, QWidget)()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(inner)
        return scroll

    def _page_header(self, key: str) -> QWidget:
        title_text, sub_text = self._PAGE_META[key]
        title = QLabel(title_text)
        title.setObjectName("pageTitle")
        sub = QLabel(sub_text)
        sub.setObjectName("pageSubtitle")
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addWidget(div)
        return w

    def _card_shell(self, title: str) -> tuple[QFrame, QWidget]:
        card = QFrame()
        card.setObjectName("card")

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        header = QLabel(title)
        header.setObjectName("cardHeader")
        header.setContentsMargins(16, 12, 16, 11)
        vbox.addWidget(header)

        sep = QFrame()
        sep.setObjectName("cardSep")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        vbox.addWidget(sep)

        body = QWidget()
        body.setObjectName("cardBody")
        vbox.addWidget(body)
        return card, body

    def _make_card(self, title: str) -> tuple[QFrame, QFormLayout]:
        card, body = self._card_shell(title)
        form = QFormLayout(body)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setContentsMargins(16, 14, 16, 16)
        return card, form

    def _make_card_vbox(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Titled white card with a free-form VBox body (for tables, custom rows, etc.)."""
        card, body = self._card_shell(title)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 16)
        body_layout.setSpacing(10)
        return card, body_layout

    def _help_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("helpText")
        label.setWordWrap(True)
        return label

    def _error_label(self) -> QLabel:
        label = QLabel("")
        label.setObjectName("errorText")
        label.setWordWrap(True)
        label.setVisible(False)
        return label

    def _page_container(self) -> tuple[QWidget, QVBoxLayout]:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        return container, layout

    # ── pages ─────────────────────────────────────────────────────────────────

    def _create_appearance_page(self) -> QWidget:
        container, layout = self._page_container()
        layout.addWidget(self._page_header("appearance"))

        card, form = self._make_card("Theme")
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Use system appearance", "system")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        index = self.theme_combo.findData(self.profile_settings.preferred_theme)
        self.theme_combo.setCurrentIndex(max(0, index))
        self.theme_combo.currentIndexChanged.connect(
            lambda: self._apply_theme(self.theme_combo.currentData())
        )
        form.addRow("Color theme:", self.theme_combo)

        calibration = (
            "Calibrated"
            if self.profile_settings.has_completed_onboarding
            else "Calibration required"
        )
        profile_status = QLabel(
            f"{calibration} · baseline {self.profile_settings.baseline_posture_score:.0f}%"
        )
        profile_status.setObjectName("helpText")
        form.addRow("Profile:", profile_status)

        layout.addWidget(card)
        layout.addStretch()
        return container

    def _apply_theme(self, preference: str) -> None:
        self.setStyleSheet(settings_stylesheet(preference))

    def _create_camera_page(self) -> QWidget:
        container, layout = self._page_container()
        layout.addWidget(self._page_header("camera"))

        card, form = self._make_card("Capture")

        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        cameras = self._available_cameras()
        if cameras:
            for cam_id, cam_name in cameras:
                self.camera_combo.addItem(cam_name, cam_id)
            idx = self.camera_combo.findData(self.runtime_settings.default_camera_id)
            if idx != -1:
                self.camera_combo.setCurrentIndex(idx)
        else:
            self.camera_combo.addItem("No camera found", -1)
            self.camera_combo.setEnabled(False)
        form.addRow("Default camera:", self.camera_combo)

        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(self.runtime_settings.default_fps)
        self.fps_spinbox.setSuffix(" fps")
        self.fps_spinbox.setMinimumWidth(120)
        form.addRow("Frame rate:", self.fps_spinbox)

        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(100, 10000)
        self.width_spinbox.setValue(self.runtime_settings.frame_width)
        self.width_spinbox.setSuffix(" px")
        self.width_spinbox.setMinimumWidth(110)

        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(100, 10000)
        self.height_spinbox.setValue(self.runtime_settings.frame_height)
        self.height_spinbox.setSuffix(" px")
        self.height_spinbox.setMinimumWidth(110)

        res_row = QHBoxLayout()
        res_row.setSpacing(8)
        res_row.addWidget(self.width_spinbox)
        x_lbl = QLabel("×")
        x_lbl.setObjectName("helpText")
        res_row.addWidget(x_lbl)
        res_row.addWidget(self.height_spinbox)
        res_row.addStretch()
        form.addRow("Resolution:", res_row)

        self.adaptive_resolution_checkbox = QCheckBox(
            "Automatically lower resolution on slow hardware"
        )
        self.adaptive_resolution_checkbox.setChecked(
            self.runtime_settings.adaptive_resolution
        )
        self.adaptive_resolution_checkbox.setToolTip(
            "Drops to 640×480 at startup if MediaPipe initialisation takes over 100 ms."
        )
        form.addRow("Adaptive resolution:", self.adaptive_resolution_checkbox)

        layout.addWidget(card)
        layout.addWidget(
            self._help_label(
                "Higher resolution improves detection accuracy but increases CPU usage."
            )
        )
        layout.addStretch()
        return container

    def _create_notifications_page(self) -> QWidget:
        container, layout = self._page_container()
        layout.addWidget(self._page_header("notifications"))

        card, form = self._make_card("Alerts")

        self.notifications_enabled_checkbox = QCheckBox("Enable desktop notifications")
        self.notifications_enabled_checkbox.setChecked(
            self.runtime_settings.notifications_enabled
        )
        form.addRow(self.notifications_enabled_checkbox)

        self.focus_mode_checkbox = QCheckBox("Pause reminders during focus mode")
        self.focus_mode_checkbox.setChecked(self.runtime_settings.focus_mode_enabled)
        form.addRow(self.focus_mode_checkbox)

        self.cooldown_spinbox = QSpinBox()
        self.cooldown_spinbox.setRange(30, 3600)
        self.cooldown_spinbox.setValue(self.runtime_settings.notification_cooldown)
        self.cooldown_spinbox.setSuffix(" sec")
        self.cooldown_spinbox.setMinimumWidth(130)
        form.addRow("Cooldown between alerts:", self.cooldown_spinbox)

        self.poor_posture_spinbox = QSpinBox()
        self.poor_posture_spinbox.setRange(10, 100)
        self.poor_posture_spinbox.setValue(self.runtime_settings.poor_posture_threshold)
        self.poor_posture_spinbox.setSuffix("%")
        self.poor_posture_spinbox.setMinimumWidth(100)
        form.addRow("Alert threshold:", self.poor_posture_spinbox)

        self.posture_message_lineedit = QLineEdit()
        self.posture_message_lineedit.setText(
            self.runtime_settings.default_posture_message
        )
        self.posture_message_lineedit.setMinimumWidth(260)
        self.posture_message_lineedit.setPlaceholderText("e.g. Sit up straight!")
        self.posture_message_lineedit.textChanged.connect(
            self._validate_posture_message
        )
        form.addRow("Reminder message:", self.posture_message_lineedit)

        self.posture_message_error = self._error_label()
        form.addRow("", self.posture_message_error)

        layout.addWidget(card)
        layout.addStretch()
        return container

    def _create_tracking_page(self) -> QWidget:
        container, layout = self._page_container()
        layout.addWidget(self._page_header("tracking"))

        intervals_card, intervals_body = self._make_card_vbox("Tracking Intervals")

        self.tracking_table = QTableWidget()
        self.tracking_table.setColumnCount(2)
        self.tracking_table.setHorizontalHeaderLabels(["Label", "Minutes"])
        self.tracking_table.setMinimumHeight(160)
        self.tracking_table.setAlternatingRowColors(True)
        self.tracking_table.verticalHeader().setVisible(False)
        hdr = self.tracking_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tracking_table.setColumnWidth(1, 90)
        self._populate_tracking_table()
        intervals_body.addWidget(self.tracking_table)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.new_interval_label_edit = QLineEdit()
        self.new_interval_label_edit.setPlaceholderText("Interval label")
        self.new_interval_spinbox = QSpinBox()
        self.new_interval_spinbox.setRange(0, 1440)
        self.new_interval_spinbox.setValue(30)
        self.new_interval_spinbox.setSuffix(" min")
        self.new_interval_spinbox.setFixedWidth(100)
        self.add_interval_button = QPushButton("Add")
        self.add_interval_button.setObjectName("addBtn")
        self.add_interval_button.setFixedWidth(64)
        self.add_interval_button.clicked.connect(self._add_tracking_interval)
        add_row.addWidget(self.new_interval_label_edit)
        add_row.addWidget(self.new_interval_spinbox)
        add_row.addWidget(self.add_interval_button)
        intervals_body.addLayout(add_row)

        self.remove_interval_button = QPushButton("Remove Selected")
        self.remove_interval_button.setObjectName("removeBtn")
        self.remove_interval_button.clicked.connect(self._remove_tracking_interval)
        intervals_body.addWidget(self.remove_interval_button)

        self.interval_error_label = self._error_label()
        intervals_body.addWidget(self.interval_error_label)

        layout.addWidget(intervals_card)
        layout.addWidget(
            self._help_label(
                "Intervals define how often tracking restarts. "
                "Set minutes to 0 for always-on continuous tracking."
            )
        )

        duration_card, duration_form = self._make_card("Session Duration")
        self.tracking_duration_spinbox = QSpinBox()
        self.tracking_duration_spinbox.setRange(1, 60)
        self.tracking_duration_spinbox.setValue(
            self.runtime_settings.tracking_duration_minutes
        )
        self.tracking_duration_spinbox.setSuffix(" min")
        self.tracking_duration_spinbox.setMinimumWidth(110)
        duration_form.addRow("Duration per session:", self.tracking_duration_spinbox)
        layout.addWidget(duration_card)

        layout.addStretch()
        return container

    def _create_data_page(self) -> QWidget:
        container, layout = self._page_container()
        layout.addWidget(self._page_header("data"))

        card, form = self._make_card("Session Logging")

        self.db_logging_checkbox = QCheckBox("Persist session data to database")
        self.db_logging_checkbox.setChecked(
            self.runtime_settings.enable_database_logging
        )
        form.addRow(self.db_logging_checkbox)

        self.db_write_interval_spinbox = QSpinBox()
        self.db_write_interval_spinbox.setRange(60, 3600)
        self.db_write_interval_spinbox.setSingleStep(60)
        self.db_write_interval_spinbox.setValue(
            self.runtime_settings.db_write_interval_seconds
        )
        self.db_write_interval_spinbox.setSuffix(" sec")
        self.db_write_interval_spinbox.setMinimumWidth(130)
        self.db_write_interval_spinbox.setToolTip(
            "How often scored frames are flushed to the database."
        )
        form.addRow("Write interval:", self.db_write_interval_spinbox)

        layout.addWidget(card)
        layout.addWidget(
            self._help_label(
                "Logged data can be used to analyse posture trends over time. "
                "Disable to reduce disk writes."
            )
        )
        layout.addStretch()
        return container

    def _create_advanced_page(self) -> QWidget:
        container, layout = self._page_container()
        layout.addWidget(self._page_header("advanced"))

        # ── Detection Tuning ──────────────────────────────────────────────────
        tuning_card, tuning_form = self._make_card("Detection Tuning")

        self.model_complexity_combo = QComboBox()
        self.model_complexity_combo.addItem("0 – Lite  (fastest, least accurate)", 0)
        self.model_complexity_combo.addItem("1 – Full  (balanced)", 1)
        self.model_complexity_combo.addItem("2 – Heavy  (most accurate, slowest)", 2)
        idx = self.model_complexity_combo.findData(self.ml_settings.model_complexity)
        self.model_complexity_combo.setCurrentIndex(max(0, idx))
        self.model_complexity_combo.setMinimumWidth(260)
        tuning_form.addRow("Model complexity:", self.model_complexity_combo)

        self.detection_confidence_spinbox = QDoubleSpinBox()
        self.detection_confidence_spinbox.setRange(0.0, 1.0)
        self.detection_confidence_spinbox.setSingleStep(0.05)
        self.detection_confidence_spinbox.setDecimals(2)
        self.detection_confidence_spinbox.setValue(
            self.ml_settings.min_detection_confidence
        )
        self.detection_confidence_spinbox.setMinimumWidth(110)
        tuning_form.addRow(
            "Min detection confidence:", self.detection_confidence_spinbox
        )

        self.tracking_confidence_spinbox = QDoubleSpinBox()
        self.tracking_confidence_spinbox.setRange(0.0, 1.0)
        self.tracking_confidence_spinbox.setSingleStep(0.05)
        self.tracking_confidence_spinbox.setDecimals(2)
        self.tracking_confidence_spinbox.setValue(
            self.ml_settings.min_tracking_confidence
        )
        self.tracking_confidence_spinbox.setMinimumWidth(110)
        tuning_form.addRow("Min tracking confidence:", self.tracking_confidence_spinbox)

        self.score_buffer_spinbox = QSpinBox()
        self.score_buffer_spinbox.setRange(10, 10000)
        self.score_buffer_spinbox.setValue(self.ml_settings.score_buffer_size)
        self.score_buffer_spinbox.setSuffix(" frames")
        self.score_buffer_spinbox.setMinimumWidth(140)
        tuning_form.addRow("Score buffer size:", self.score_buffer_spinbox)

        self.score_window_spinbox = QSpinBox()
        self.score_window_spinbox.setRange(1, 100)
        self.score_window_spinbox.setValue(self.ml_settings.score_window_size)
        self.score_window_spinbox.setSuffix(" frames")
        self.score_window_spinbox.setMinimumWidth(140)
        tuning_form.addRow("Score window size:", self.score_window_spinbox)

        self.score_threshold_spinbox = QSpinBox()
        self.score_threshold_spinbox.setRange(0, 100)
        self.score_threshold_spinbox.setValue(self.ml_settings.score_threshold)
        self.score_threshold_spinbox.setSuffix("%")
        self.score_threshold_spinbox.setMinimumWidth(100)
        tuning_form.addRow("Score threshold:", self.score_threshold_spinbox)

        layout.addWidget(tuning_card)

        # ── Posture Thresholds ────────────────────────────────────────────────
        thresholds_card, thresholds_form = self._make_card("Posture Thresholds")
        self.threshold_spinboxes: dict[str, QDoubleSpinBox] = {}
        for key, value in self.ml_settings.posture_thresholds.items():
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(2)
            spinbox.setRange(0.01, 180.0)
            spinbox.setSingleStep(0.5)
            spinbox.setValue(float(value))
            spinbox.setMinimumWidth(120)
            thresholds_form.addRow(f"{key.replace('_', ' ').title()}:", spinbox)
            self.threshold_spinboxes[key] = spinbox
        layout.addWidget(thresholds_card)

        # ── Posture Weights ───────────────────────────────────────────────────
        weights_card, weights_form = self._make_card("Posture Weights")
        self.weight_spinboxes: list[QDoubleSpinBox] = []
        for index, weight in enumerate(self.ml_settings.posture_weights, start=1):
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(3)
            spinbox.setRange(0.0, 1.0)
            spinbox.setSingleStep(0.05)
            spinbox.setValue(float(weight))
            spinbox.setMinimumWidth(120)
            spinbox.valueChanged.connect(self._update_weights_sum)
            weights_form.addRow(f"Weight {index}:", spinbox)
            self.weight_spinboxes.append(spinbox)
        self.weights_sum_label = QLabel()
        self.weights_sum_label.setObjectName("helpText")
        self._update_weights_sum()
        weights_form.addRow("Sum:", self.weights_sum_label)
        self.weights_error_label = self._error_label()
        weights_form.addRow("", self.weights_error_label)
        layout.addWidget(weights_card)

        layout.addStretch()
        return container

    def _update_weights_sum(self) -> None:
        total = sum(s.value() for s in self.weight_spinboxes)
        colors = theme_colors(self.theme_combo.currentData())
        color = colors.accent if 0.99 <= total <= 1.01 else colors.highlight
        self.weights_sum_label.setText(
            f'<span style="color:{color}; font-weight:600;">{total:.3f}</span>'
            f'  <span style="color:{colors.muted};">(ideally 1.000)</span>'
        )

    # ── section visibility ────────────────────────────────────────────────────

    def _handle_advanced_toggle(self, checked: bool) -> None:
        index = self.section_key_to_index.get("advanced")
        if index is None:
            return
        self.section_list.item(index).setHidden(not checked)
        if not checked and self.section_list.currentRow() == index:
            self.section_list.setCurrentRow(0)

    # ── tracking table management ─────────────────────────────────────────────

    def _populate_tracking_table(self) -> None:
        self.tracking_table.setRowCount(0)
        for label, minutes in self.runtime_settings.tracking_intervals.items():
            row = self.tracking_table.rowCount()
            self.tracking_table.insertRow(row)
            self.tracking_table.setItem(row, 0, QTableWidgetItem(label))
            self.tracking_table.setItem(row, 1, QTableWidgetItem(str(minutes)))

    def _add_tracking_interval(self) -> None:
        label = self.new_interval_label_edit.text().strip()
        if not label:
            self._show_error(
                "tracking_intervals",
                self.interval_error_label,
                "Provide a label before adding an interval.",
            )
            return
        row = self.tracking_table.rowCount()
        self.tracking_table.insertRow(row)
        self.tracking_table.setItem(row, 0, QTableWidgetItem(label))
        self.tracking_table.setItem(
            row, 1, QTableWidgetItem(str(self.new_interval_spinbox.value()))
        )
        self.new_interval_label_edit.clear()
        self._clear_error("tracking_intervals", self.interval_error_label)

    def _remove_tracking_interval(self) -> None:
        selected_rows = {item.row() for item in self.tracking_table.selectedItems()}
        for row in sorted(selected_rows, reverse=True):
            self.tracking_table.removeRow(row)
        if selected_rows:
            self._clear_error("tracking_intervals", self.interval_error_label)

    # ── camera detection ──────────────────────────────────────────────────────

    def _available_cameras(self, max_index: int = 5):
        camera_ids = list(range(max_index))
        current = self.runtime_settings.default_camera_id
        if current not in camera_ids:
            camera_ids.append(current)
        return [(camera_id, f"Camera {camera_id}") for camera_id in camera_ids]

    # ── validation ────────────────────────────────────────────────────────────

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
                "Reminder message cannot be empty.",
            )
            return False
        if len(message) < 3:
            self._show_error(
                "posture_message",
                self.posture_message_error,
                "Use at least three characters.",
            )
            return False
        self._clear_error("posture_message", self.posture_message_error)
        return True

    def _collect_tracking_intervals(self) -> dict[str, int]:
        intervals: dict[str, int] = {}
        for row in range(self.tracking_table.rowCount()):
            label_item = self.tracking_table.item(row, 0)
            minutes_item = self.tracking_table.item(row, 1)
            label = label_item.text().strip() if label_item else ""
            if not label:
                raise ValueError("Each interval needs a label.")
            try:
                minutes = int(minutes_item.text()) if minutes_item else 0
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Minutes for '{label}' must be a whole number."
                ) from exc
            if minutes < 0:
                raise ValueError("Minutes cannot be negative.")
            intervals[label] = minutes
        if not intervals:
            raise ValueError("Add at least one tracking interval.")
        return intervals

    def _validate_tracking_intervals(self) -> dict[str, int] | None:
        try:
            intervals = self._collect_tracking_intervals()
        except ValueError as error:
            self._show_error(
                "tracking_intervals", self.interval_error_label, str(error)
            )
            return None
        self._clear_error("tracking_intervals", self.interval_error_label)
        return intervals

    def _validate_posture_weights(self) -> bool:
        total = sum(s.value() for s in self.weight_spinboxes)
        if total <= 0:
            self._show_error(
                "posture_weights",
                self.weights_error_label,
                "At least one posture weight must be greater than zero.",
            )
            return False
        self._clear_error("posture_weights", self.weights_error_label)
        return True

    def _validate_all(self) -> dict[str, int] | None:
        message_valid = self._validate_posture_message()
        intervals = self._validate_tracking_intervals()
        weights_valid = self._validate_posture_weights()
        if not message_valid or intervals is None or not weights_valid:
            return None
        return intervals

    # ── accept ────────────────────────────────────────────────────────────────

    def accept(self) -> None:
        intervals = self._validate_all()
        if intervals is None:
            QMessageBox.warning(
                self, "Settings", "Please resolve the highlighted fields before saving."
            )
            return

        cam_id = self.camera_combo.currentData()
        if cam_id is None or cam_id == -1:
            cam_id = self.runtime_settings.default_camera_id

        self._settings.update_runtime(
            default_camera_id=cam_id,
            default_fps=self.fps_spinbox.value(),
            frame_width=self.width_spinbox.value(),
            frame_height=self.height_spinbox.value(),
            adaptive_resolution=self.adaptive_resolution_checkbox.isChecked(),
            notifications_enabled=self.notifications_enabled_checkbox.isChecked(),
            focus_mode_enabled=self.focus_mode_checkbox.isChecked(),
            notification_cooldown=self.cooldown_spinbox.value(),
            poor_posture_threshold=self.poor_posture_spinbox.value(),
            default_posture_message=self.posture_message_lineedit.text().strip(),
            enable_database_logging=self.db_logging_checkbox.isChecked(),
            db_write_interval_seconds=self.db_write_interval_spinbox.value(),
            tracking_intervals=intervals,
            tracking_duration_minutes=self.tracking_duration_spinbox.value(),
        )
        self._settings.update_ml(
            model_complexity=self.model_complexity_combo.currentData(),
            min_detection_confidence=self.detection_confidence_spinbox.value(),
            min_tracking_confidence=self.tracking_confidence_spinbox.value(),
            score_buffer_size=self.score_buffer_spinbox.value(),
            score_window_size=self.score_window_spinbox.value(),
            score_threshold=self.score_threshold_spinbox.value(),
            posture_thresholds={
                k: s.value() for k, s in self.threshold_spinboxes.items()
            },
            posture_weights=[s.value() for s in self.weight_spinboxes],
        )
        self._settings.update_profile(preferred_theme=self.theme_combo.currentData())
        self._status_label.setText(self._status_text())
        super().accept()
