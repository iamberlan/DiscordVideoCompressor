# Discord Video Compressor

A simple desktop app for shrinking videos to a chosen upload size. Videos are processed locally with FFmpeg.

## Using the app

1. Drop a video into the window or select **Browse**.
2. Choose **20 MB · Free**, **50 MB · Basic**, **1 GB · Nitro**, or **Custom**.
3. Select **Compress**.
4. Click **Video** to open the result, drag it into Discord, or select **Copy** and paste it into Discord on Windows.

**Open Folder** shows the saved file. Files save beside the original unless you choose **Change location**. Existing files are preserved by adding a number to the filename.

**Advanced** contains resolution, audio, encoding speed, bitrate details, and logs. The app identifies videos that already fit and warns when the chosen size may produce low quality. It still allows compression when a video already fits.

## Run from source

You need Python with Tkinter, plus FFmpeg. FFprobe is recommended for reading video details. The current Windows build has been tested with Python 3.13.

Install the drag-and-drop dependency from the project folder:

```powershell
python -m pip install -r requirements.txt
```

Launch:

```powershell
python run.py
```

You can also double-click `run.bat` on Windows or use `bash run.sh` on macOS/Linux. Source launchers may show a terminal; the packaged Windows app does not.

FFmpeg can be on your system PATH or selected with **Locate FFmpeg**. Keep FFprobe beside FFmpeg for automatic detection. The app can also look for Windows binaries in its local `bin/` or `ffmpeg/bin/` folder.

Without `tkinterdnd2`, browsing and compression still work, but dragging files is unavailable. **Copy** transfers the file through the Windows clipboard; it is only available on Windows.

## Build the Windows app

Place the Windows x64 static `ffmpeg.exe` and `ffprobe.exe` in `vendor/ffmpeg/`, along with the download's license as `LICENSE.txt` and its `README.txt`. The binaries are ignored by Git. Keep `release/licenses/` in sync if you update dependencies.

From the project folder:

```powershell
python -m pip install -r requirements.txt pyinstaller
.\build.bat
```

Open the resulting application:

```text
dist/DiscordVideoCompressor/DiscordVideoCompressor.exe
```

The build includes Python, drag-and-drop support, FFmpeg and FFprobe, and disables the console window. Share **`dist/DiscordVideoCompressor-Windows-x64.zip`**. Recipients extract the entire ZIP and open `DiscordVideoCompressor.exe`; they do not need Python, FFmpeg, or build tools. Keep `_internal` beside the executable.

The ZIP includes short instructions and dependency license notices.

`build.bat` runs `tools/build_release.py` and regenerates `DiscordVideoCompressor.spec`. Generated build files and executables are ignored by Git.

## Compression behavior

- Two-pass H.264 encoding produces an MP4 with AAC audio when audio is retained.
- Automatic resolution scaling reduces resolution when the available bitrate is low.
- Encoding starts with a 4% size buffer. The actual finished size is checked, with up to two retries if it exceeds the target.
- Files are encoded in a temporary directory and published after they pass the size check. Cancellation and failed attempts clean up temporary output.
- If three attempts cannot meet the target, the app asks you to choose a larger size or a shorter clip.

Targets use decimal units: **1 MB = 1,000,000 bytes**, and **1 GB = 1,000 MB**. File-size labels currently use binary units, so the displayed size may differ from the target number. The presets are convenient choices; use **Custom** to match the upload limit shown by Discord.

## Project structure

```text
DiscordVideoCompressor/
├── app.py                  # Tkinter interface, background jobs, and file actions
├── compressor.py           # Video analysis, two-pass encoding, retries, and safe output
├── ffmpeg_finder.py        # FFmpeg/FFprobe detection and local configuration
├── file_clipboard.py       # Windows file clipboard support
├── run.py                  # Application entry point
├── run.bat                 # Windows source launcher
├── run.sh                  # Bash source launcher
├── build.bat               # Windows GUI build with PyInstaller
├── requirements.txt        # Native drag-and-drop dependency
├── test_compressor.py      # Calculation and configuration tests
├── test_output_safety.py   # Retry, cancellation, and file-preservation tests
├── .gitignore              # Generated output and local-only files
├── .gitattributes          # Git text normalization
└── README.md
```

Generated or local files, excluded from Git:

```text
build/           # PyInstaller working files
dist/            # Packaged application
run.spec         # Generated build configuration
__pycache__/     # Python bytecode
config.json      # Locally selected FFmpeg/FFprobe paths
```

## Checks

```powershell
python -m unittest -v
```

The configuration test writes and removes `config.json`; run it in a checkout without configuration you need to keep. Tests cover compression calculations and output safety. Actual drag/drop and clipboard paste into Discord require a manual desktop check.

## License

MIT License.
