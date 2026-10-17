from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel, QScrollArea

from ..services.settings_service import SettingsService, SettingsStore
from ..ui.dashboard import PostureDashboard
from ..ui.onboarding import CalibrationPage, OnboardingWizard
from ..ui.settings_dialog import SettingsDialog
from ..ui.theme import DARK


def test_settings_pages_fit_minimum_window_without_horizontal_scroll(qapp, tmp_path):
    settings = SettingsService.for_testing(tmp_path / "layout_settings.ini")
    dialog = SettingsDialog(settings)
    dialog.resize(dialog.minimumSize())
    dialog.show()
    qapp.processEvents()

    for index, (section, *_rest) in enumerate(dialog.SECTION_DEFS):
        dialog.section_stack.setCurrentIndex(index)
        qapp.processEvents()
        scroll = dialog.section_stack.currentWidget()
        assert isinstance(scroll, QScrollArea)
        assert scroll.horizontalScrollBar().maximum() == 0, section

    dialog.close()


def test_settings_theme_preview_updates_entire_dialog(qapp, tmp_path):
    settings = SettingsService.for_testing(tmp_path / "theme_settings.ini")
    dialog = SettingsDialog(settings)

    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("dark"))

    assert DARK.canvas in dialog.styleSheet()


def test_dashboard_breakdown_remains_readable_at_minimum_size(qapp):
    dashboard = PostureDashboard(78.0, "light")
    dashboard.resize(dashboard.minimumSize())
    dashboard.show()
    qapp.processEvents()

    rows = list(dashboard.component_rows.values())
    assert len(rows) == 5
    assert all(row.width() >= 150 and row.height() >= 38 for row in rows)
    assert dashboard.video_view.width() >= 320
    assert not dashboard.video_view.geometry().intersects(
        dashboard.sparkline.geometry()
    )

    dashboard.close()


def test_dashboard_highlights_worst_component_and_coaches_on_it(qapp):
    dashboard = PostureDashboard(78.0, "light")
    metrics = {
        "neck_angle": 30.0,
        "shoulder_vertical_delta": 0.0,
        "head_tilt_score": 0.9,
        "neck_vertical_score": 0.3,
        "head_side_tilt_score": 0.9,
        "head_rotation_score": 0.9,
        "shoulder_level_score": 0.95,
        "shoulder_roll_score": 0.95,
        "spine_alignment_score": 0.2,
        "hips_visible": 0.0,
    }

    dashboard.update_score(50.0, metrics, None)

    assert dashboard.component_rows["neck"].flagged
    assert dashboard.component_rows["spine"].value is None
    assert "head back" in dashboard.feedback_label.text()
    dashboard.close()


def test_dashboard_makes_paused_and_tracking_states_visible(qapp):
    dashboard = PostureDashboard(78.0, "light")

    dashboard.set_tracking_state("paused")

    assert dashboard.video_overlay.isVisible() is False
    dashboard.show()
    qapp.processEvents()
    assert dashboard.video_overlay.isVisible()
    assert "Paused" in dashboard.subtitle.text()

    dashboard.set_tracking_state("tracking")
    assert not dashboard.video_overlay.isVisible()
    assert dashboard.subtitle.text() == "Tracking posture"
    dashboard.close()


def test_calibration_progress_reports_detection_state(qapp, tmp_path):
    settings = SettingsService.for_testing(tmp_path / "calibration_progress.ini")
    page = CalibrationPage(settings)

    page._update_progress(50, 3, False)

    assert page.progress_bar.value() == 50
    assert "No posture detected" in page.status_label.text()


def test_settings_camera_picker_only_shows_verified_ids(qapp, tmp_path):
    settings = SettingsService.for_testing(tmp_path / "camera_picker.ini")
    dialog = SettingsDialog(settings, available_camera_ids=[0, 2])

    assert [dialog.camera_combo.itemData(i) for i in range(2)] == [0, 2]
    assert dialog.camera_combo.count() == 2
    dialog.close()


def test_onboarding_has_visible_brand_asset(qapp, tmp_path):
    settings = SettingsService.for_testing(tmp_path / "onboarding_layout.ini")
    wizard = OnboardingWizard(settings)

    pixmaps = [
        label.pixmap()
        for label in wizard.welcome_page.findChildren(QLabel)
        if label.pixmap() is not None
    ]
    assert pixmaps and not pixmaps[0].isNull()

    wizard.close()


def test_invalid_saved_theme_falls_back_to_system(tmp_path):
    qsettings = QSettings(
        str(tmp_path / "invalid_theme.ini"), QSettings.Format.IniFormat
    )
    qsettings.setValue("profile/preferred_theme", "neon")

    store = SettingsStore(qsettings=qsettings, migrate_legacy=False)

    assert store.profile.preferred_theme == "system"


def test_settings_camera_list_fills_in_after_background_detection(qapp, tmp_path):
    settings = SettingsService.for_testing(tmp_path / "camera_async.ini")
    dialog = SettingsDialog(settings)
    assert "Detecting cameras" in dialog.camera_help_label.text()

    dialog.set_available_cameras([0, 1])

    assert [dialog.camera_combo.itemData(i) for i in range(2)] == [0, 1]
    assert dialog.camera_combo.currentData() == 0
    assert "Detecting" not in dialog.camera_help_label.text()
    dialog.close()


def test_video_frames_head_and_shoulders_then_eases_back_out(qapp):
    import numpy as np

    from ..ui.dashboard import VideoView

    view = VideoView()
    view.resize(640, 360)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    points = np.full((33, 3), 0.5)
    points[[7, 8], 1] = 0.40  # ears
    points[[11, 12], 1] = 0.50  # shoulders: neck = 0.1 of the frame
    points[[11, 12], 0] = (0.45, 0.55)

    view.set_frame(frame, points)
    framed = view._crop
    assert framed.height() == pytest.approx(0.5 * 720)  # min zoom (4.5 * 0.1 < 0.5)
    assert framed.width() / framed.height() == pytest.approx(640 / 360)
    assert 0 <= framed.left() and framed.right() <= 1280

    for _ in range(30):  # nobody detected for a while
        view._crop_at -= 0.2
        view.set_frame(frame)
    assert view._crop.height() == pytest.approx(720, rel=0.02)
