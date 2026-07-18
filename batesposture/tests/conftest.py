from __future__ import annotations

import os

import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
