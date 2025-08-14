# OpenCV2 Posture Corrector

A real-time posture monitoring application that uses computer vision to analyze your posture through your webcam. Integrated into your system tray, it provides instant feedback and alerts to help maintain proper ergonomics while working.

## Features

- Real-time posture scoring (0-100)
- System tray integration
- Visual feedback with color-coded scores
- Configurable tracking intervals
- Optional live video feed
- Automatic posture alerts
- Cross-platform support (Windows, macOS, Linux)
- Local processing only - no data stored or transmitted

## Technical Stack

- MediaPipe for pose detection
- OpenCV for video processing
- PyQt6 for system tray interface
- Native platform notifications

## Installation

### Windows

1. Install Python 3.10
2. Install dependencies:
   ```bash
   py -3.10 -m pip install -r requirements.txt
   ```
3. Install Visual C++ Redistributable if needed
4. For MSVC runtime issues:
   ```bash
   py -3.10 -m pip install msvc-runtime
   ```

### Linux

1. Install system dependencies:
   ```bash
   sudo apt install -y \
       libxcb1 \
       libxcb-xinerama0 \
       libxcb-cursor0 \
       libxkbcommon-x11-0 \
       libxcb-render0 \
       libxcb-render-util0
   ```

2. Optional packages for additional features:
   ```bash
   sudo apt install -y \
       qt6-base-dev \
       qt6-wayland \
       libqt5x11extras5
   ```

### General

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python src/main.py
   ```

## Usage

1. Click the system tray icon and select "Start Tracking"
2. Optionally enable video feed to see real-time analysis
3. Set your preferred tracking interval
4. Monitor your posture score (0-100) via the tray icon
5. Receive alerts when posture needs correction

## Privacy

All video processing happens locally on your machine. No data is stored, shared, or transmitted over the internet.

## Contributing

Contributions are welcome. Please read our contribution guidelines to get started.
