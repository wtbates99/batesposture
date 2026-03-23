# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for BatesPosture — Windows · Linux.

Build commands (run from repo root):
    uv run pyinstaller batesposture.spec --noconfirm
"""
from __future__ import annotations

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(SPECPATH)  # repo root (where this .spec lives)
SRC = os.path.join(ROOT, "src")

# ── data files ────────────────────────────────────────────────────────────────
# MediaPipe ships .tflite models and proto data that must be bundled.
datas = [
    (os.path.join(SRC, "static", "icon.png"), "src/static"),
    *collect_data_files("mediapipe"),
    *collect_data_files("cv2"),
    *collect_data_files("numpy"),
    *collect_data_files("plyer"),
]

# ── hidden imports ────────────────────────────────────────────────────────────
# PyInstaller's static analysis misses dynamically-loaded modules.
hidden_imports = [
    # application modules (all resolved relative to src/ via pathex)
    "application",
    "data.database",
    "ml.pose_detector",
    "services.camera_service",
    "services.notification_service",
    "services.score_service",
    "services.settings_service",
    "services.task_scheduler",
    "ui.dashboard",
    "ui.onboarding",
    "ui.settings_dialog",
    "ui.tray",
    "util__create_score_icon",
    "util__send_notification",
    # PyQt6 — platform plugins are auto-collected but these are sometimes missed
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.sip",
    # MediaPipe internals (large but necessary — tflite, protobuf, calculators)
    *collect_submodules("mediapipe"),
    # plyer platform backends
    "plyer.platforms",
    "plyer.platforms.win",
    "plyer.platforms.win.notification",
    "plyer.platforms.linux",
    "plyer.platforms.linux.notification",
    # stdlib modules sometimes missed in onefile mode
    "psutil",
    "sqlite3",
    "logging.handlers",
]

# ── platform icon ─────────────────────────────────────────────────────────────
# CI converts icon.png → .ico (Windows) before running PyInstaller.
# Fall back to .png if the platform-native format hasn't been generated yet.
if sys.platform == "win32":
    _ico = os.path.join(SRC, "static", "icon.ico")
    _icon = _ico if os.path.exists(_ico) else os.path.join(SRC, "static", "icon.png")
else:
    _icon = os.path.join(SRC, "static", "icon.png")

# ── analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[ROOT, SRC],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # not used by this app
        "tkinter", "_tkinter",
        "matplotlib",
        "IPython", "jupyter",
        "pandas", "scipy", "sklearn",
        "tensorflow", "torch",
        "anthropic",
        # test infrastructure never needed at runtime
        "pytest", "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BatesPosture",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUI app — no terminal window
    argv_emulation=False,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BatesPosture",
)
