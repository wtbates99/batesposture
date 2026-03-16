# BatesPosture

A real-time posture monitoring application that uses computer vision to analyse your posture through your webcam. Integrated into the system tray, it provides instant visual feedback, configurable alerts, and session analytics to help maintain proper ergonomics while working.

## Features

- Real-time posture scoring (0–100) with colour-coded tray icon
- System tray integration — always visible, never in your way
- Live dashboard with sparkline history and session statistics (avg, min, max, best streak)
- Persistent dashboard history — sparkline survives closing and reopening the window
- Configurable tracking intervals (continuous or scheduled) with break reminders
- Desktop notifications with cooldown throttling and focus-mode suppression
- Onboarding wizard with 6-second calibration to capture your personal baseline
- SQLite database logging with CSV export
- Rotating log files for persistent diagnostics (`~/Library/Logs/BatesPosture/` on macOS)
- Adaptive resolution — automatically drops to 640×480 on low-end hardware when enabled
- GPU acceleration toggle (forces MediaPipe complexity-2 model)
- Cross-platform: macOS, Windows, Linux
- All processing happens locally — no video or pose data leaves your machine

## Technical Stack

- **MediaPipe** — pose landmark detection (33 body landmarks, configurable model complexity)
- **OpenCV** — frame capture, CLAHE enhancement, landmark visualisation
- **PyQt6** — system tray, dashboard window, settings dialog, onboarding wizard
- **NumPy** — vectorised posture metric computation and rolling score buffer
- **SQLite3** (WAL mode) — persistent storage for scores, landmarks, and dashboard history
- **psutil** — hardware detection for adaptive resolution
- Python `threading.Lock` — thread-safe score buffering between camera and UI threads
- `logging.handlers.RotatingFileHandler` — 5 MB / 3-backup rotating log files

## Download

Pre-built binaries for every platform are available on the **[releases page](https://github.com/wtbates99/batesposture/releases/latest)**, or via the **[download website](https://wtbates99.github.io/batesposture/)** which auto-detects your OS.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `BatesPosture-vX.X.X-macOS-arm64.dmg` |
| macOS (Intel) | `BatesPosture-vX.X.X-macOS-x86_64.dmg` |
| Windows | `BatesPosture-vX.X.X-Windows.zip` |
| Linux | `BatesPosture-vX.X.X-Linux.tar.gz` |

## Development Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install all dependencies (including dev/test tools)
uv sync --all-groups

# Run the application
uv run python src/main.py

# Run tests
uv run --group dev python -m pytest
```

## Building from Source

To produce a standalone executable locally:

```bash
# macOS / Linux
./scripts/build_local.sh

# Windows
scripts\build_local.bat
```

Or run PyInstaller directly:

```bash
uv run pyinstaller batesposture.spec --noconfirm
```

Output is written to `dist/BatesPosture/` (or `dist/BatesPosture.app` on macOS).

### Releasing a new version

1. Bump the version in `pyproject.toml`
2. Commit and push, then tag the commit:
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
3. GitHub Actions builds all three platforms automatically and publishes a GitHub Release with the artifacts attached.

### macOS

Camera permissions are required. Grant access in **System Settings → Privacy & Security → Camera**.

### Linux

Install system dependencies for PyQt6:

```bash
sudo apt install -y \
    libxcb1 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxkbcommon-x11-0 \
    libxcb-render0 \
    libxcb-render-util0
```

### Windows

Install Visual C++ Redistributable if MediaPipe fails to load:

```bash
pip install msvc-runtime
```

## Usage

1. Launch the app — the tray icon appears (grey circle when idle)
2. Click the tray icon → **Start Tracking** (or `Ctrl+Shift+T`)
3. The icon updates in real time: red (poor) → amber (fair) → green (excellent)
4. Open the dashboard (`Ctrl+Shift+D`) to see live video, sparkline, and session stats
5. Configure alerts, intervals, and thresholds via **Settings** (`Ctrl+,`)
6. Export session data to CSV via **Export Data as CSV…**

## Configuration via Environment Variables

All settings can be overridden at startup with the prefix `POSTURE_<SECTION>_<FIELD>`:

```bash
# Run at 15 FPS on a slower machine
POSTURE_RUNTIME_DEFAULT_FPS=15 uv run python src/main.py

# Automatically drop to 640×480 on low-end hardware
POSTURE_RUNTIME_ADAPTIVE_RESOLUTION=true uv run python src/main.py

# Enable GPU-optimised MediaPipe model
POSTURE_ML_ENABLE_GPU=true uv run python src/main.py

# Silence notifications
POSTURE_RUNTIME_NOTIFICATIONS_ENABLED=false uv run python src/main.py

# Use a different camera
POSTURE_RUNTIME_DEFAULT_CAMERA_ID=1 uv run python src/main.py
```

See `src/services/settings_service.py` → `KEY_TO_SECTION_FIELD` for a full list of available keys.

## Default Tuning Values

These constants are defined in `settings_service.py` and imported wherever used:

| Constant | Default | Description |
|---|---|---|
| `POOR_POSTURE_THRESHOLD_DEFAULT` | 60 | Score below which a notification fires |
| `SCORE_THRESHOLD_DEFAULT` | 65 | Score used to track good-posture streaks |
| `DEFAULT_POSTURE_WEIGHTS` | `(0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05)` | Per-metric contribution to overall score |
| `BREAK_REMINDER_MINUTES` | 50 | Minutes of continuous tracking before a break prompt |
| `CALIBRATION_DURATION_SECONDS` | 6 | Baseline sample length during onboarding |
| `CALIBRATION_TIMEOUT_MARGIN_SECONDS` | 6 | Extra seconds before the calibration thread is cancelled |

## Privacy

All video processing runs locally. Pose landmarks and scores are only written to the local SQLite database when database logging is explicitly enabled. No data is transmitted externally.

## Troubleshooting

**Camera not detected**
- macOS: grant camera permission in System Settings → Privacy & Security → Camera
- Try a different camera index: `POSTURE_RUNTIME_DEFAULT_CAMERA_ID=1`

**Calibration fails during onboarding**
- Ensure adequate lighting and that your head and shoulders are fully in frame
- Move closer to the camera and try again

**Performance issues / lag**
- Enable adaptive resolution: `POSTURE_RUNTIME_ADAPTIVE_RESOLUTION=true`
- Reduce frame rate: `POSTURE_RUNTIME_DEFAULT_FPS=15`
- Lower model complexity in **Settings → Advanced → Model complexity** (0 is fastest)

**GPU acceleration not working**
- The `enable_gpu` toggle forces MediaPipe complexity-2 and relies on the device's ONNX Runtime or Metal/CUDA support. If unavailable, it falls back to CPU silently.

**Log files**
- macOS: `~/Library/Logs/BatesPosture/app.log` (rotates at 5 MB, keeps 3 backups)
- Other platforms: `~/.batesposture_logs/app.log`

## Contributing

Contributions are welcome. Please open an issue or pull request on GitHub.
