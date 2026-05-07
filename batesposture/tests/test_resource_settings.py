from __future__ import annotations

from batesposture.services import settings_service


def test_default_icon_path_uses_ico_on_windows(monkeypatch):
    monkeypatch.setattr(settings_service.os, "name", "nt")
    monkeypatch.setattr(settings_service, "get_resource_path", lambda path: path)

    assert settings_service._default_icon_path() == "batesposture/static/icon.ico"


def test_default_icon_path_uses_png_off_windows(monkeypatch):
    monkeypatch.setattr(settings_service.os, "name", "posix")
    monkeypatch.setattr(settings_service, "get_resource_path", lambda path: path)

    assert settings_service._default_icon_path() == "batesposture/static/icon.png"
