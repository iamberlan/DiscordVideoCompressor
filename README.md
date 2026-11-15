# Discord Video Compressor 🎬

A modern, responsive Tkinter desktop application that compresses videos using 2-pass **FFmpeg** encoding to precisely hit Discord file size upload limits without sacrificing more quality than necessary.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green.svg)
![GUI](https://img.shields.io/badge/GUI-Tkinter-purple.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

---

## ✨ Features

- **🎯 Exact Target Size Presets:**
  - **8 MB** — Free Discord tier upload limit
  - **20 MB** — Boosted server / legacy upload limit
  - **50 MB** — Discord Nitro Basic upload limit
  - **Custom Target** — Any desired size in MB (e.g., `10`, `25`, `100`)
- **⚖️ 2-Pass FFmpeg Encoding:** Guarantees precise target size without overshooting the Discord limit while maximizing video fidelity.
- **🛡️ Built-in Safety Margin (4%):** Files are encoded to ~96% of the exact limit (e.g. 7.68 MB for 8 MB) to prevent Discord from rejecting uploads due to container metadata overhead.
- **📐 Intelligent Auto-Resolution Scaling:** Automatically downscales high-resolution videos (1080p/4K) if the calculated bitrate is too low, preventing muddy, macroblocked videos.
- **🔊 Smart Audio Allocation:** Dynamic audio bitrate (48 kbps – 128 kbps) based on target size, with an option to mute/strip audio to give 100% of the bits to video.
- **🚀 Web-Optimized (`+faststart`):** Embeds moov atom at the front of the file so videos stream and play instantly in Discord chat.
- **📊 Real-Time Progress & ETA:** Live dual-stage progress bar (Pass 1 analysis + Pass 2 encoding), encoding speed multiplier (e.g. `2.5x`), and estimated time remaining.
- **🎨 Sleek Discord-Themed Dark UI:** Clean dark interface with Discord Blurple accenting.
- **📂 One-Click Actions:** Open output folder or directly play the compressed video upon completion.
- **📋 Collapsible Log Drawer:** View real-time FFmpeg terminal output for diagnostics.
- **🔎 Auto FFmpeg Detection & Config:** Automatically detects system FFmpeg or allows selecting a custom executable.

---

## 📋 Prerequisites

1. **Python 3.8+** (with Tkinter included by default in standard Python installers).
2. **FFmpeg** and **FFprobe** (must be on system `PATH` or located via the app's *Locate FFmpeg* button).

### Installing FFmpeg:
- **Windows:** Download from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) (or run `winget install Gyan.FFmpeg` or `choco install ffmpeg`).
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

---

## 🚀 Quick Start

1. **Clone or download this repository:**
   ```bash
   git clone https://github.com/isaac/DiscordVideoCompressor.git
   cd DiscordVideoCompressor
   ```

2. *(Optional)* Install drag-and-drop support:
   ```bash
   pip install -r requirements.txt
   ```
   > *Note: External dependencies are optional. The app runs completely on Python's standard library!*

3. **Launch the application:**
   - **Using Bash (Git Bash / WSL / macOS / Linux):**
     ```bash
     ./run.sh
     ```
   - **Using Windows Command Prompt / Double-click:**
     ```cmd
     run.bat
     ```
   - **Directly with Python:**
     ```bash
     python run.py
     ```

---

## 🛠️ How It Works (Bitrate Calculation)

The application calculates the exact mathematical target bitrates required to fit into the specified size:

$$\text{Effective Target Bytes} = \text{Target MB} \times 1024 \times 1024 \times 0.96$$

$$\text{Total Bitrate (bps)} = \frac{\text{Effective Target Bytes} \times 8}{\text{Video Duration in Seconds}}$$

$$\text{Video Bitrate} = \text{Total Bitrate} - \text{Audio Bitrate}$$

- **Pass 1:** Analyzes video motion vectors and complexity without rendering audio (`-an -f null`).
- **Pass 2:** Allocates bits intelligently to complex frames and writes the final `.mp4` file with `yuv420p` pixel format and `+faststart` flags for universal compatibility across Discord desktop, mobile, and web clients.

---

## 📁 Project Structure

```
DiscordVideoCompressor/
├── app.py              # Modern Tkinter GUI with Discord dark theme & background workers
├── compressor.py       # Core video analysis, bitrate calculations, and 2-pass FFmpeg engine
├── ffmpeg_finder.py    # Binary locator, version check, and configuration manager
├── run.py              # Simple launcher entry point
├── test_compressor.py  # Unit tests for calculations and presets
├── requirements.txt    # Optional dependencies
└── README.md           # Documentation
```

---

## 📄 License

MIT License. Free to use and modify!
