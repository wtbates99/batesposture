from __future__ import annotations

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


def test_dashboard_stat_grid_remains_readable_at_minimum_size(qapp):
    dashboard = PostureDashboard(78.0, "light")
    dashboard.resize(dashboard.minimumSize())
    dashboard.show()
    qapp.processEvents()

    stats = [
        label
        for label in dashboard.findChildren(QLabel)
        if label.objectName() == "statCard"
    ]
    assert len(stats) == 5
    assert all(stat.width() >= 150 and stat.height() >= 54 for stat in stats)
    assert not dashboard.video_label.geometry().intersects(
        dashboard.sparkline.geometry()
    )

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
