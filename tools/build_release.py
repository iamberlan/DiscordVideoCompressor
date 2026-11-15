"""Build a portable Windows folder and a ZIP for friends. Run via build.bat."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    vendor = ROOT / "vendor" / "ffmpeg"

    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm",
        "--windowed", "--name", "DiscordVideoCompressor",
        "--collect-all", "tkinterdnd2",
        "--add-binary", f"{vendor / 'ffmpeg.exe'};bin",
        "--add-binary", f"{vendor / 'ffprobe.exe'};bin", "run.py",
    ], cwd=ROOT, check=True)
    output = ROOT / "dist" / "DiscordVideoCompressor"
    shutil.copytree(ROOT / "release", output, dirs_exist_ok=True)
    notices = output / "licenses"
    notices.mkdir(exist_ok=True)
    shutil.copy2(vendor / "LICENSE.txt", notices / "FFmpeg-GPL.txt")
    if (vendor / "README.txt").is_file():
        shutil.copy2(vendor / "README.txt", notices / "FFmpeg-README.txt")
    archive = Path(shutil.make_archive(str(ROOT / "dist" / "DiscordVideoCompressor-Windows-x64"),
                                      "zip", output.parent, output.name))
    print(f"Share: {archive} ({archive.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
