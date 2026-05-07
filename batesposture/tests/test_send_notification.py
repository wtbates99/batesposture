from __future__ import annotations

from batesposture.util__send_notification import _plyer_notification_kwargs


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


def test_plyer_notification_kwargs_omit_png_icon(tmp_path):
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"png")

    kwargs = _plyer_notification_kwargs("message", "title", str(icon))

    assert kwargs == {
        "title": "title",
        "message": "message",
        "timeout": 10,
    }


def test_plyer_notification_kwargs_omit_missing_ico(tmp_path):
    icon = tmp_path / "missing.ico"

    kwargs = _plyer_notification_kwargs("message", "title", str(icon))

    assert kwargs == {
        "title": "title",
        "message": "message",
        "timeout": 10,
    }
