<div align="center">

# BatesPosture

**Real-time desktop posture monitor. Webcam in, posture score out. 100% local.**

[![License](https://img.shields.io/github/license/wtbates99/batesposture?color=c9a84c&style=flat-square)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/wtbates99/batesposture?color=c9a84c&style=flat-square)](https://github.com/wtbates99/batesposture/stargazers)
[![Last commit](https://img.shields.io/github/last-commit/wtbates99/batesposture?color=c9a84c&style=flat-square)](https://github.com/wtbates99/batesposture/commits/main)
[![Python](https://img.shields.io/badge/python-3.10+-c9a84c?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Made with MediaPipe](https://img.shields.io/badge/pose-MediaPipe-e07830?style=flat-square)](https://google.github.io/mediapipe/)
[![Site](https://img.shields.io/badge/site-posture.palanbates.com-4d8a5e?style=flat-square)](https://posture.palanbates.com)

[**Website**](https://posture.palanbates.com) · [**Install**](#install) · [**How it works**](#how-it-works) · [**Privacy**](#privacy) · [**FAQ**](#faq)

</div>

---

> 🟢 **excellent** — streak running 12m
> 🟡 **fair** — corrections needed
> 🔴 **poor posture** — alert fired

A tiny tray app that watches your webcam, scores your posture every second on a 0–100 scale, and pings you when you start slouching. No cloud. No accounts. No telemetry. Just a webcam and `uv run`.

## Why

Most posture apps are either subscription SaaS or a Pomodoro timer that yells "stand up!" every 30 minutes. BatesPosture actually looks at you with MediaPipe, computes seven weighted geometric metrics (head tilt, neck angle, shoulder balance, spine alignment, …), and only nudges you when your score drops — calibrated to *your* posture, not a generic threshold.

It's free, open source, and the entire pipeline runs on-device. Nothing leaves your computer.

## Features

| | |
|---|---|
| 🎯 **Live 0–100 score** | Color-coded tray icon updated every second |
| 📊 **Session dashboard** | Sparkline history, average, min/max, best streak, duration |
| 🔔 **Smart alerts** | Native OS notifications with threshold + cooldown + focus mode |
| ⏱️ **Scheduling** | Continuous or interval tracking, plus 50-min break reminders |
| 💾 **Local logging** | Optional SQLite + CSV export, all on your machine |
| ⚡ **Adaptive performance** | Auto-downscales on slower hardware |
| 👤 **Auto-pause** | Stops counting away-from-desk time after ~2s no-detection |
| 🔒 **100% local** | No cloud, no accounts, no telemetry, ever |

## Install

Requires [Python 3.10+](https://www.python.org/) and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/wtbates99/batesposture.git
cd batesposture
uv sync --locked --all-groups
uv run batesposture
```

That's it. Grant camera permission, complete the 6-second calibration, and the tray icon takes over.

<details>
<summary><b>Linux: extra system libraries (Debian/Ubuntu)</b></summary>

```bash
sudo apt-get update
sudo apt-get install -y \
  libgl1 libglib2.0-0 \
  libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xfixes0 libxkbcommon-x11-0 libegl1
```

GNOME users may need the [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/).
</details>

## How it works

1. **Calibrate** — a 6-second baseline of your natural posture so alerts are tuned to *you*.
2. **Track** — MediaPipe extracts pose landmarks → seven weighted metrics → one 0–100 score → tray color.
3. **Alert** — score drops below your threshold → native desktop notification (with cooldown to prevent fatigue).
4. **Review** — open the dashboard for the live frame, score sparkline, session stats, and streaks.

## Configuration

Settings cover camera, notifications, tracking schedule, and advanced scoring controls. Anything in the UI can also be set via `POSTURE_<SECTION>_<FIELD>` env vars at launch:

```bash
POSTURE_RUNTIME_DEFAULT_CAMERA_ID=1 uv run batesposture     # use a different camera
POSTURE_RUNTIME_DEFAULT_FPS=15 uv run batesposture          # reduce camera load
POSTURE_RUNTIME_POOR_POSTURE_THRESHOLD=55 uv run batesposture
```

Environment names follow `POSTURE_<SECTION>_<FIELD>` for runtime, ML, and profile settings.

<details>
<summary><b>Default tuning values</b></summary>

| Constant | Default | Description |
| --- | --- | --- |
| `POOR_POSTURE_THRESHOLD_DEFAULT` | `60` | Score below which an alert can fire |
| `SCORE_THRESHOLD_DEFAULT` | `65` | Threshold for good-posture streak tracking |
| `DEFAULT_POSTURE_WEIGHTS` | `(0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05)` | Per-metric contribution to score |
| `BREAK_REMINDER_MINUTES` | `50` | Continuous sitting time before a break reminder |
| `CALIBRATION_DURATION_SECONDS` | `6` | Baseline capture time during onboarding |

</details>

## Data locations

| | |
|---|---|
| Database / lock | Linux `~/.local/share/BatesPosture/` · macOS `~/Library/Application Support/BatesPosture/` · Windows `%APPDATA%` |
| Logs | macOS `~/Library/Logs/BatesPosture/app.log` · other `~/.batesposture_logs/app.log` (5 MB rotation, 3 backups) |
| CSV exports | `~/posture_export_YYYYMMDD_HHMMSS.csv` |
| Settings | `QSettings` (platform-specific backing store) |

## Privacy

- **No video frames are uploaded.** MediaPipe runs locally.
- **No posture data leaves your machine.** Period.
- **No accounts, no telemetry, no analytics.**
- SQLite logging is **opt-in** and disabled by default.

## FAQ

**Does it work on macOS / Windows / Linux?** Yes — all three. Requires a webcam and Python 3.10+.

**Does it slow down my computer?** Adaptive resolution keeps processing manageable. Drop `POSTURE_RUNTIME_DEFAULT_FPS=15` for older hardware.

**Will it nag me constantly?** No. Notifications have a configurable cooldown, focus mode silences them entirely, and the score only fires alerts below your threshold.

**Can I export my data?** Yes — local SQLite + CSV export when logging is enabled.

**Are packaged installers available?** Not yet. The current release runs from source with `uv sync --locked && uv run batesposture`.

## Development

```bash
uv sync --locked --all-groups
QT_QPA_PLATFORM=offscreen uv run python -m pytest
uv run pre-commit run --all-files
```

## Troubleshooting

<details>
<summary><b>Camera does not open</b></summary>

- Try another camera index: `POSTURE_RUNTIME_DEFAULT_CAMERA_ID=1 uv run batesposture`
- Make sure another app is not already using the camera
- Check that only one BatesPosture instance is running
</details>

<details>
<summary><b>Tracking keeps pausing</b></summary>

If no person is detected for ~2 seconds, BatesPosture pauses the session on purpose so away-from-desk time doesn't pollute your stats. Make sure your head and shoulders are well lit and visible.
</details>

<details>
<summary><b>Performance is poor</b></summary>

- `POSTURE_RUNTIME_ADAPTIVE_RESOLUTION=true`
- `POSTURE_RUNTIME_DEFAULT_FPS=15`
- Reduce frame size in settings
- Lower model complexity in the Advanced section
</details>

<details>
<summary><b>Export is empty</b></summary>

Database logging must be enabled before data can be exported. Export writes saved score rows, not unsaved live state.
</details>

## Contributing

Issues and PRs welcome. If you change runtime behavior, update tests and keep the README in sync.

---

<div align="center">

**[posture.palanbates.com](https://posture.palanbates.com)** · AGPL-3.0 license · Built by [@wtbates99](https://github.com/wtbates99)

If BatesPosture saves your neck, ⭐ the repo — that's how more people find it.

</div>
