from __future__ import annotations

from types import SimpleNamespace

from ..ml import mediapipe_compat


def test_load_mediapipe_solutions_prefers_public_namespace(monkeypatch):
    sentinel = object()
    fake_mp = SimpleNamespace(solutions=sentinel)

    assert mediapipe_compat.load_mediapipe_solutions(fake_mp) is sentinel


def test_load_mediapipe_solutions_falls_back_to_python_namespace(monkeypatch):
    sentinel = object()
    fake_mp = SimpleNamespace()

    def fake_import(name: str):
        assert name == "mediapipe.python.solutions"
        return sentinel

    monkeypatch.setattr(mediapipe_compat, "import_module", fake_import)

    assert mediapipe_compat.load_mediapipe_solutions(fake_mp) is sentinel
