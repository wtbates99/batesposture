from __future__ import annotations

import json

from PyQt6.QtCore import QSettings

from ..services import settings_service as settings_module


def test_legacy_json_settings_are_migrated_once(tmp_path, monkeypatch):
    legacy_path = tmp_path / "user_settings.json"
    legacy_path.write_text(
        json.dumps({"DEFAULT_FPS": 15, "UNKNOWN_SETTING": "ignored"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_module, "LEGACY_USER_SETTINGS_FILE", str(legacy_path))
    qsettings = QSettings(
        str(tmp_path / "migrated_settings.ini"), QSettings.Format.IniFormat
    )

    store = settings_module.SettingsStore(qsettings=qsettings, migrate_legacy=True)

    assert store.runtime.default_fps == 15
    assert not legacy_path.exists()
    assert (tmp_path / "user_settings.json.legacy").exists()
    assert qsettings.value("runtime/default_fps", type=int) == 15


def test_testing_settings_keep_all_writes_in_temporary_directory(tmp_path):
    service = settings_module.SettingsService.for_testing(tmp_path / "settings.ini")

    assert service.resources.default_db_name == str(tmp_path / "posture_data.db")
