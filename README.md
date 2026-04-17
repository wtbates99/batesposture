# BatesPosture

BatesPosture is a tray-first desktop posture monitor built with PyQt6, OpenCV, and MediaPipe. It watches your webcam locally, scores posture in real time, shows a live dashboard, and nudges you when your posture drops below a threshold you control.

The app is designed to stay out of the way:

- the tray icon reflects your current posture score
- tracking can run continuously or on a schedule
- notifications have cooldown and focus-mode controls
- session stats exclude time when no person is on camera
- optional SQLite logging enables CSV export and persistent dashboard history

All pose processing stays on your machine. No video frames or posture data are uploaded anywhere.

## Highlights

- Real-time 0-100 posture score with a color-coded tray icon
- Live dashboard with webcam preview, metrics, sparkline history, and session stats
- Automatic pause when no human is detected for about 2 seconds
- Continuous or scheduled tracking with configurable scan duration
- Good-posture streak tracking and break reminders
- Desktop notifications with cooldown throttling and focus-mode suppression
- Onboarding calibration for baseline posture values
- Optional SQLite logging with configurable sampling interval
- CSV export for saved posture score history
- Persistent dashboard sparkline history across app restarts
- Adaptive resolution fallback for slower hardware
- Single-instance locking to avoid duplicate camera access
- Local rotating log files for diagnostics

## Install

BatesPosture is published on [PyPI](https://pypi.org/project/batesposture/).

```bash
pip install batesposture
batesposture
```

You can also launch it as a module:

```bash
pip install batesposture
python -m batesposture
```

### Requirements

- Python 3.10 or newer
- A webcam
- A desktop environment with system tray support

GNOME users may need the [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/) for tray support.

### MediaPipe compatibility

The app currently depends on the MediaPipe "Solutions" API and ships with a pinned, known-good MediaPipe version through package metadata. If you force-upgrade `mediapipe` separately inside the same environment, BatesPosture may stop launching.

## How It Works

1. Launch `batesposture`. The tray icon starts in an idle state.
2. Click `Start Tracking` or press `Ctrl+Shift+T`.
3. BatesPosture opens the configured camera, scores posture continuously, and updates the tray icon color and tooltip.
4. Open the dashboard with `Ctrl+Shift+D` to see the live frame, rolling score, metrics, and session summary.
5. If no person is detected for about 2 seconds, tracking pauses automatically and away time does not count toward session duration or streaks.
6. When a person is detected again, tracking resumes automatically.
7. If database logging is enabled, posture scores and landmarks are written to SQLite on the configured interval and can be exported as CSV later.

Useful shortcuts:

- `Ctrl+Shift+T`: start or stop tracking
- `Ctrl+Shift+D`: show or hide the dashboard
- `Ctrl+,`: open settings
- `Ctrl+Q`: quit

## What You Can Configure

The settings dialog covers four main areas:

- Camera and video: camera device, FPS, frame width, frame height
- Notifications: enable or disable alerts, focus mode, cooldown, posture threshold, alert message
- Tracking: interval schedule, scan duration, database logging, database write interval
- Advanced: model complexity, detection and tracking confidence, scoring thresholds, metric weights, score buffer and window sizes, GPU mode toggle

Advanced controls stay hidden by default behind `Show advanced controls`.

## Data, Settings, and File Locations

BatesPosture stores runtime data in per-user locations instead of writing into the installed package directory.

### Database and lock file

The default SQLite database and single-instance lock file live in the app data directory returned by Qt. Typical locations are:

- Linux: `~/.local/share/BatesPosture/`
- macOS: `~/Library/Application Support/BatesPosture/`
- Windows: your user AppData location

By default the database filename is `posture_data.db` and the lock filename is `batesposture.lock`.

### Settings storage

Settings are stored through `QSettings`, so the exact backing file or registry path depends on the platform. Environment variables can override settings at startup.

### Logs

Log files are written here:

- macOS: `~/Library/Logs/BatesPosture/app.log`
- other platforms: `~/.batesposture_logs/app.log`

Logs rotate at 5 MB with 3 backups.

### CSV exports

CSV exports are written to your home directory as files named like:

```text
~/posture_export_YYYYMMDD_HHMMSS.csv
```

## Environment Variable Overrides

You can override settings at launch with variables named `POSTURE_<SECTION>_<FIELD>`.

Examples:

```bash
# Use a different camera
POSTURE_RUNTIME_DEFAULT_CAMERA_ID=1 batesposture

# Reduce camera load
POSTURE_RUNTIME_DEFAULT_FPS=15 batesposture

# Allow adaptive fallback to 640x480 on slower hardware
POSTURE_RUNTIME_ADAPTIVE_RESOLUTION=true batesposture

# Enable database logging immediately
POSTURE_RUNTIME_ENABLE_DATABASE_LOGGING=true batesposture

# Save to SQLite every 5 minutes
POSTURE_RUNTIME_DB_WRITE_INTERVAL_SECONDS=300 batesposture

# Disable notifications
POSTURE_RUNTIME_NOTIFICATIONS_ENABLED=false batesposture

# Keep monitoring active but suppress reminders
POSTURE_RUNTIME_FOCUS_MODE_ENABLED=true batesposture

# Change the posture alert threshold and message
POSTURE_RUNTIME_POOR_POSTURE_THRESHOLD=55 \
POSTURE_RUNTIME_DEFAULT_POSTURE_MESSAGE="Shoulders back." \
batesposture

# Enable the GPU mode setting (uses the highest-complexity pose model)
POSTURE_ML_ENABLE_GPU=true batesposture
```

For the full mapping, see `KEY_TO_SECTION_FIELD` in `batesposture/services/settings_service.py`.

## Default Tuning Values

| Constant | Default | Description |
| --- | --- | --- |
| `POOR_POSTURE_THRESHOLD_DEFAULT` | `60` | Score below which a posture alert can fire |
| `SCORE_THRESHOLD_DEFAULT` | `65` | Score threshold used for good-posture streak tracking |
| `DEFAULT_POSTURE_WEIGHTS` | `(0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05)` | Per-metric contribution to the posture score |
| `BREAK_REMINDER_MINUTES` | `50` | Continuous sitting time before a break reminder |
| `CALIBRATION_DURATION_SECONDS` | `6` | Baseline capture time during onboarding |
| `CALIBRATION_TIMEOUT_MARGIN_SECONDS` | `6` | Extra timeout allowed for calibration cleanup |

## Development

This repo uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install runtime and dev dependencies
uv sync --all-groups

# Run the app
uv run batesposture

# Or run the package module directly
uv run python -m batesposture

# Run tests
QT_QPA_PLATFORM=offscreen uv run python -m pytest

# Run formatting and lint hooks
uv run pre-commit run --all-files
```

## Release Process

When cutting a release:

1. Bump the version in `pyproject.toml`.
2. Refresh the lockfile with `uv lock`.
3. Run tests and pre-commit locally.
4. Build the sdist and wheel with `uv build`.
5. Smoke-test the built wheel in a clean environment.
6. Commit, push `main`, then create and push a `vX.Y.Z` tag.

Example smoke test:

```bash
uv venv --clear --seed /tmp/batesposture-pip-test
/tmp/batesposture-pip-test/bin/pip install dist/*.whl
cd /tmp
QT_QPA_PLATFORM=offscreen \
/tmp/batesposture-pip-test/bin/python -c "import batesposture.main; print('pip install import ok')"
```

GitHub Actions then:

- runs `pytest`
- builds the distribution
- installs the built wheel into a clean temp environment
- verifies `import batesposture.main`
- publishes to PyPI
- creates a GitHub Release

The first publish requires a PyPI [trusted publisher](https://docs.pypi.org/trusted-publishers/) configured for this repository and the `pypi` environment.

## Troubleshooting

### Camera does not open

- Try another camera index: `POSTURE_RUNTIME_DEFAULT_CAMERA_ID=1 batesposture`
- Make sure another app is not already using the camera
- Check that only one BatesPosture instance is running

### Tracking keeps pausing

If no person is detected for about 2 seconds, BatesPosture pauses the active session on purpose. This prevents away-from-desk time from polluting your stats. Make sure your head and shoulders are well lit and visible in frame.

### Export is disabled or empty

- Database logging must be enabled before data can be exported
- Export writes saved score rows, not unsaved live state
- CSV export goes to your home directory

### Linux launch errors involving Qt or OpenCV libraries

On Debian or Ubuntu systems, install the same shared libraries used in CI:

```bash
sudo apt-get update
sudo apt-get install -y \
  libgl1 libglib2.0-0 \
  libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xfixes0 libxkbcommon-x11-0 libegl1
```

### Performance is poor

- Enable adaptive resolution: `POSTURE_RUNTIME_ADAPTIVE_RESOLUTION=true`
- Lower FPS: `POSTURE_RUNTIME_DEFAULT_FPS=15`
- Reduce frame size in settings
- Lower model complexity in the Advanced section

### You forced a different MediaPipe version and the app no longer starts

Create a fresh virtual environment and reinstall `batesposture`. The package metadata pins a compatible MediaPipe release for you.

## Privacy

All webcam processing happens locally on your machine.

- No video frames are uploaded
- No posture data is sent to a server
- SQLite logging is optional and disabled by default
- CSV exports are written locally to your home directory

## Contributing

Issues and pull requests are welcome. If you are changing runtime behavior, update tests and keep the README in sync with the shipped package and release flow.
