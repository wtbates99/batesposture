from __future__ import annotations

from unittest.mock import MagicMock

from batesposture.services import platform_notification
from batesposture.services.platform_notification import _plyer_notification_kwargs


def test_plyer_notification_kwargs_include_existing_ico(tmp_path):
    icon = tmp_path / "icon.ico"
    icon.write_bytes(b"\x00\x00\x01\x00")

    kwargs = _plyer_notification_kwargs("message", "title", str(icon))

    assert kwargs == {
        "title": "title",
        "message": "message",
        "timeout": 10,
        "app_icon": str(icon),
    }


def test_plyer_notification_kwargs_omit_unsupported_icon(tmp_path):
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"png")

    kwargs = _plyer_notification_kwargs("message", "title", str(icon))

    assert kwargs == {"title": "title", "message": "message", "timeout": 10}


def test_plyer_notification_kwargs_omit_missing_icon(tmp_path):
    kwargs = _plyer_notification_kwargs(
        "message", "title", str(tmp_path / "missing.ico")
    )

    assert kwargs == {"title": "title", "message": "message", "timeout": 10}


def test_notification_backend_failure_does_not_escape(monkeypatch, caplog):
    sender = MagicMock(side_effect=FileNotFoundError("notify-send missing"))
    monkeypatch.setattr(platform_notification.platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform_notification, "_send_linux", sender)

    platform_notification.send_notification("message", "title", "icon.png")

    assert "could not be delivered" in caplog.text
