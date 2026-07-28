from __future__ import annotations

from unittest.mock import MagicMock

from .. import application as application_module
from ..application import ApplicationFacade
from ..data.database import DatabaseInitializationError
from ..services.settings_service import SettingsService


def _patch_application_services(monkeypatch, settings):
    detector = MagicMock(prewarm_duration_ms=0.0)
    monkeypatch.setattr(application_module, "SettingsService", lambda: settings)
    monkeypatch.setattr(application_module, "TaskScheduler", MagicMock)
    monkeypatch.setattr(application_module, "PoseDetector", lambda value: detector)
    monkeypatch.setattr(application_module, "CameraService", MagicMock)
    monkeypatch.setattr(application_module, "ScoreService", MagicMock)
    monkeypatch.setattr(application_module, "NotificationService", MagicMock)
    monkeypatch.setattr(application_module, "PostureTrackerTray", MagicMock)


def test_startup_opens_database_when_logging_is_enabled(qapp, tmp_path, monkeypatch):
    settings = SettingsService.for_testing(tmp_path / "startup_settings.ini")
    settings.update_runtime(enable_database_logging=True)
    _patch_application_services(monkeypatch, settings)
    database = MagicMock()
    database_factory = MagicMock()
    database_factory.from_settings.return_value = database
    monkeypatch.setattr(application_module, "Database", database_factory)

    facade = ApplicationFacade(qapp)

    assert facade.database is database
    database_factory.from_settings.assert_called_once_with(settings)


def test_startup_continues_when_database_cannot_open(qapp, tmp_path, monkeypatch):
    settings = SettingsService.for_testing(tmp_path / "startup_settings.ini")
    settings.update_runtime(enable_database_logging=True)
    _patch_application_services(monkeypatch, settings)
    database_factory = MagicMock()
    database_factory.from_settings.side_effect = DatabaseInitializationError(
        "database unavailable"
    )
    monkeypatch.setattr(application_module, "Database", database_factory)
    warning = MagicMock()
    monkeypatch.setattr(application_module.QMessageBox, "warning", warning)

    facade = ApplicationFacade(qapp)

    assert facade.database is None
    assert not settings.runtime.enable_database_logging
    warning.assert_called_once()
