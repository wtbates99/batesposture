# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get the current directory
current_dir = os.getcwd()

# Collect all data files and submodules
mediapipe_data = collect_data_files('mediapipe')
opencv_data = collect_data_files('cv2')
numpy_data = collect_data_files('numpy')
plyer_data = collect_data_files('plyer')
matplotlib_data = collect_data_files('matplotlib')

# Collect all submodules
mediapipe_modules = collect_submodules('mediapipe')
opencv_modules = collect_submodules('cv2')
matplotlib_modules = collect_submodules('matplotlib')

# Define the main script
main_script = os.path.join(current_dir, 'src', 'main.py')

# Define data files to include - Fix icon path handling
data_files = [
    # Static assets - Use relative path for better bundling
    ('src/static/icon.png', 'src/static'),

    # Include all collected data files
    *mediapipe_data,
    *opencv_data,
    *numpy_data,
    *plyer_data,
    *matplotlib_data,
]

# Define hidden imports
hidden_imports = [
    # Core application modules
    'src.tray_interface',
    'src.pose_detector',
    'src.webcam',
    'src.database',
    'src.notifications',
    'src.settings_interface',
    'src.util__settings',
    'src.util__scores',
    'src.util__send_notification',
    'src.util__create_score_icon',

    # PyQt6 modules
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',

    # MediaPipe modules
    *mediapipe_modules,

    # OpenCV modules
    *opencv_modules,

    # Matplotlib modules (required by MediaPipe)
    *matplotlib_modules,

    # Other dependencies
    'numpy',
    'cv2',
    'mediapipe',
    'plyer',
    'psutil',
    'sqlite3',
    'json',
    'platform',
    'threading',
    'time',
    'datetime',
    'os',
    'sys',
    'signal',
]

# Platform-specific settings
if sys.platform == 'darwin':  # macOS
    # macOS specific settings
    target_arch = None
    codesign_identity = None
    entitlements_file = None

    # Include macOS specific frameworks
    frameworks = []

elif sys.platform == 'win32':  # Windows
    # Windows specific settings
    target_arch = None

elif sys.platform.startswith('linux'):  # Linux
    # Linux specific settings
    target_arch = None

# Analysis configuration
a = Analysis(
    [main_script],
    pathex=[current_dir, os.path.join(current_dir, 'src')],
    binaries=[],
    datas=data_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'IPython',
        'jupyter',
        'pandas',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PyZ configuration
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Executable configuration
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='opencv2-posture-corrector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to False for GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
    codesign_identity=codesign_identity,
    entitlements_file=entitlements_file,
    icon='src/static/icon.png',  # Use relative path for icon
)

# Collection configuration
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='opencv2-posture-corrector',
)

# macOS specific app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='opencv2-posture-corrector.app',
        icon='src/static/icon.png',  # Use relative path for icon
        bundle_identifier='com.opencv2.posture.corrector',
        info_plist={
            'CFBundleName': 'OpenCV2 Posture Corrector',
            'CFBundleDisplayName': 'OpenCV2 Posture Corrector',
            'CFBundleIdentifier': 'com.opencv2.posture.corrector',
            'CFBundleVersion': '0.1.0',
            'CFBundleShortVersionString': '0.1.0',
            'CFBundlePackageType': 'APPL',
            'CFBundleSignature': '????',
            'LSMinimumSystemVersion': '10.15.0',
            'NSHighResolutionCapable': True,
            'LSUIElement': False,  # Makes it a background app (no dock icon)
            'NSAppTransportSecurity': {
                'NSAllowsArbitraryLoads': True
            },
        },
    )
