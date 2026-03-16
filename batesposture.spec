# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for BatesPosture — macOS · Windows · Linux.

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
    "plyer.platforms.macosx",
    "plyer.platforms.macosx.notification",
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
# CI converts icon.png → .icns (macOS) / .ico (Windows) before running PyInstaller.
# Fall back to .png if the platform-native format hasn't been generated yet.
def _icon_path(stem: str, ext: str) -> str:
    candidate = os.path.join(SRC, "static", f"{stem}.{ext}")
    fallback = os.path.join(SRC, "static", f"{stem}.png")
    return candidate if os.path.exists(candidate) else fallback

if sys.platform == "darwin":
    _icon = _icon_path("icon", "icns")
elif sys.platform == "win32":
    _icon = _icon_path("icon", "ico")
else:
    _icon = _icon_path("icon", "png")

# ── platform-specific EXE kwargs ──────────────────────────────────────────────
_exe_kwargs: dict = {}
if sys.platform == "darwin":
    # Code-signing is handled post-build in CI; leave identity as None here.
    _exe_kwargs["codesign_identity"] = None
    _exe_kwargs["entitlements_file"] = None

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
    argv_emulation=False,   # not needed for a system-tray app
    icon=_icon,
    **_exe_kwargs,
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

# ── macOS .app bundle ─────────────────────────────────────────────────────────
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="BatesPosture.app",
        icon=_icon,
        bundle_identifier="com.wtbates99.batesposture",
        info_plist={
            "CFBundleName": "BatesPosture",
            "CFBundleDisplayName": "BatesPosture",
            "CFBundleIdentifier": "com.wtbates99.batesposture",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundlePackageType": "APPL",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            # LSUIElement = True → background-only app; no Dock icon, no menu bar
            "LSUIElement": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSCameraUsageDescription": (
                "BatesPosture needs camera access to monitor your posture in real time. "
                "No video is recorded or transmitted."
            ),
        },
    )
