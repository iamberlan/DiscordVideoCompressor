"""
ffmpeg_finder.py - Utility to locate, configure, and verify FFmpeg and FFprobe binaries.
"""

import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import Optional, Tuple

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save config: {e}")


def _test_binary(binary_path: str) -> bool:
    """Test if the given binary can be executed with -version."""
    if not binary_path:
        return False
    try:
        # Hide console window on Windows if subprocess runs
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        res = subprocess.run(
            [binary_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
            timeout=5
        )
        return res.returncode == 0
    except Exception:
        return False


def find_binary(binary_name: str) -> Optional[str]:
    """
    Find ffmpeg or ffprobe executable:
    1. Check config.json custom path
    2. Check system PATH
    3. Check current folder and standard local paths
    """
    config = load_config()
    custom_path = config.get(f"{binary_name}_path")
    if custom_path and os.path.exists(custom_path) and _test_binary(custom_path):
        return custom_path

    # Check PATH
    found = shutil.which(binary_name)
    if found and _test_binary(found):
        return found

    # On Windows, check common .exe locations
    if os.name == "nt":
        exe_name = f"{binary_name}.exe"
        here = Path(__file__).resolve().parent
        candidate_paths = [
            here / exe_name,
            here / "bin" / exe_name,
            here / "ffmpeg" / "bin" / exe_name,
            Path("C:/ffmpeg/bin") / exe_name,
            Path("C:/Program Files/ffmpeg/bin") / exe_name,
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ffmpeg" / "bin" / exe_name,
            Path(os.environ.get("USERPROFILE", "")) / "ffmpeg" / "bin" / exe_name,
        ]
        for candidate in candidate_paths:
            if candidate.exists() and _test_binary(str(candidate)):
                return str(candidate)

    return None


def get_ffmpeg_path() -> Optional[str]:
    return find_binary("ffmpeg")


def get_ffprobe_path() -> Optional[str]:
    return find_binary("ffprobe")


def set_custom_ffmpeg_path(path: str) -> Tuple[bool, str]:
    """
    Validates and saves custom FFmpeg binary path.
    Also auto-detects ffprobe in the same directory if present.
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return False, f"File does not exist: {path}"

    if not _test_binary(path):
        return False, f"Could not execute '{path} -version'. Please ensure it is a valid FFmpeg binary."

    config = load_config()
    config["ffmpeg_path"] = path

    # Auto check ffprobe in the same directory
    dir_name = os.path.dirname(path)
    probe_name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    probe_path = os.path.join(dir_name, probe_name)
    if os.path.exists(probe_path) and _test_binary(probe_path):
        config["ffprobe_path"] = probe_path

    save_config(config)
    return True, "FFmpeg path saved successfully."


def get_ffmpeg_version(binary_path: Optional[str] = None) -> Optional[str]:
    path = binary_path or get_ffmpeg_path()
    if not path:
        return None
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        res = subprocess.run(
            [path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
            timeout=5
        )
        if res.returncode == 0:
            first_line = res.stdout.splitlines()[0] if res.stdout else ""
            return first_line.strip()
    except Exception:
        pass
    return None

