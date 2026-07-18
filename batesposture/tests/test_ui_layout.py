from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel, QScrollArea

from ..services.settings_service import SettingsService, SettingsStore
from ..ui.dashboard import PostureDashboard
from ..ui.onboarding import OnboardingWizard
from ..ui.settings_dialog import SettingsDialog
from ..ui.theme import DARK


def test_settings_pages_fit_minimum_window_without_horizontal_scroll(qapp, tmp_path):
    settings = SettingsService.for_testing(tmp_path / "layout_settings.ini")
    dialog = SettingsDialog(settings)
    dialog.resize(dialog.minimumSize())
    dialog.show()
    qapp.processEvents()

    for scroll in dialog.findChildren(QScrollArea):
        assert scroll.horizontalScrollBar().maximum() == 0

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
    assert len(stats) == 6
    assert all(stat.width() >= 150 and stat.height() >= 54 for stat in stats)
    assert not dashboard.video_label.geometry().intersects(
        dashboard.sparkline.geometry()
    )

    dashboard.close()


def test_onboarding_has_visible_brand_asset(qapp, tmp_path):
    settings = SettingsService.for_testing(tmp_path / "onboarding_layout.ini")
    wizard = OnboardingWizard(settings)
    wizard.show()
    qapp.processEvents()

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
