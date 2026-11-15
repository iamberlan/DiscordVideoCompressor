"""
compressor.py - Video analysis, bitrate calculations, and 2-pass FFmpeg compression engine.
"""

import os
import sys
import re
import json
import time
import math
import shutil
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from ffmpeg_finder import get_ffmpeg_path, get_ffprobe_path


def format_bytes(num_bytes: int) -> str:
    """Format bytes to human readable string (e.g. 8.42 MB)."""
    if num_bytes <= 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"


def format_seconds(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    if seconds < 0 or math.isnan(seconds):
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    Extract video metadata (duration, resolution, codecs, filesize, fps)
    using ffprobe, with fallback to ffmpeg parsing.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    filesize = os.path.getsize(video_path)
    info = {
        "path": video_path,
        "filename": os.path.basename(video_path),
        "filesize": filesize,
        "filesize_str": format_bytes(filesize),
        "duration": 0.0,
        "duration_str": "00:00",
        "width": 0,
        "height": 0,
        "resolution_str": "Unknown",
        "video_codec": "Unknown",
        "audio_codec": "None",
        "has_audio": False,
        "fps": 0.0,
        "bitrate": 0
    }

    ffprobe_path = get_ffprobe_path()
    if ffprobe_path:
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            cmd = [
                ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                timeout=15
            )
            if res.returncode == 0:
                data = json.loads(res.stdout)
                fmt = data.get("format", {})
                duration = float(fmt.get("duration", 0.0))
                info["duration"] = duration
                info["duration_str"] = format_seconds(duration)
                info["bitrate"] = int(fmt.get("bit_rate", 0))

                for stream in data.get("streams", []):
                    codec_type = stream.get("codec_type")
                    if codec_type == "video" and info["width"] == 0:
                        info["width"] = int(stream.get("width", 0))
                        info["height"] = int(stream.get("height", 0))
                        info["video_codec"] = stream.get("codec_name", "Unknown")
                        info["resolution_str"] = f"{info['width']}x{info['height']}"

                        # Parse FPS
                        r_frame_rate = stream.get("r_frame_rate", "")
                        if "/" in r_frame_rate:
                            num, den = r_frame_rate.split("/")
                            if float(den) > 0:
                                info["fps"] = round(float(num) / float(den), 2)
                        elif r_frame_rate:
                            info["fps"] = round(float(r_frame_rate), 2)

                    elif codec_type == "audio":
                        info["has_audio"] = True
                        info["audio_codec"] = stream.get("codec_name", "Unknown")

                if info["duration"] > 0:
                    return info
        except Exception:
            pass

    # Fallback: Parse ffmpeg -i output
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path:
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            res = subprocess.run(
                [ffmpeg_path, "-i", video_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                timeout=10
            )
            output = res.stderr or res.stdout

            # Match duration: Duration: 00:01:23.45
            dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
            if dur_match:
                hours, mins, secs = dur_match.groups()
                dur = int(hours) * 3600 + int(mins) * 60 + float(secs)
                info["duration"] = dur
                info["duration_str"] = format_seconds(dur)

            # Match video stream: Stream #0:0... Video: h264..., 1920x1080
            vid_match = re.search(r"Stream\s*#\d+:\d+.*Video:\s*([a-zA-Z0-9_\-]+).*?(\d{2,5})x(\d{2,5})", output)
            if vid_match:
                info["video_codec"] = vid_match.group(1)
                info["width"] = int(vid_match.group(2))
                info["height"] = int(vid_match.group(3))
                info["resolution_str"] = f"{info['width']}x{info['height']}"

            # Match audio stream
            aud_match = re.search(r"Stream\s*#\d+:\d+.*Audio:\s*([a-zA-Z0-9_\-]+)", output)
            if aud_match:
                info["has_audio"] = True
                info["audio_codec"] = aud_match.group(1)

        except Exception:
            pass

    return info


def calculate_bitrates(
    target_size_mb: float,
    duration_sec: float,
    has_audio: bool = True,
    safety_margin: float = 0.96
) -> Dict[str, Any]:
    """
    Calculate optimal video and audio bitrates (in kbps) to ensure the file
    stays strictly within target_size_mb with safety margin.
    """
    if duration_sec <= 0:
        duration_sec = 1.0

    target_bytes = target_size_mb * 1_000_000 * safety_margin
    total_bits = target_bytes * 8
    total_bitrate_bps = total_bits / duration_sec

    # Dynamic Audio Bitrate Allocation
    if not has_audio:
        audio_bitrate_bps = 0
    elif total_bitrate_bps < 150_000:
        audio_bitrate_bps = 48_000   # 48 kbps
    elif total_bitrate_bps < 350_000:
        audio_bitrate_bps = 64_000   # 64 kbps
    elif total_bitrate_bps < 800_000:
        audio_bitrate_bps = 96_000   # 96 kbps
    else:
        audio_bitrate_bps = 128_000  # 128 kbps

    video_bitrate_bps = total_bitrate_bps - audio_bitrate_bps
    if video_bitrate_bps < 25_000:
        # Minimum absolute floor to prevent encode error
        video_bitrate_bps = 25_000

    video_kbps = max(20, int(video_bitrate_bps / 1000))
    audio_kbps = int(audio_bitrate_bps / 1000)
    total_kbps = video_kbps + audio_kbps

    estimated_bytes = (total_kbps * 1000 * duration_sec) / 8
    estimated_mb = estimated_bytes / 1_000_000

    return {
        "target_size_mb": target_size_mb,
        "duration_sec": duration_sec,
        "video_bitrate_kbps": video_kbps,
        "audio_bitrate_kbps": audio_kbps,
        "total_bitrate_kbps": total_kbps,
        "estimated_size_mb": round(estimated_mb, 2),
        "safety_margin": safety_margin
    }


def get_recommended_scale(video_bitrate_kbps: int, original_height: int) -> Optional[int]:
    """
    Determine auto downscale resolution based on video bitrate to prevent
    severe pixelation / compression artifacts.
    """
    if video_bitrate_kbps < 220:
        target = 360
    elif video_bitrate_kbps < 500:
        target = 480
    elif video_bitrate_kbps < 1200:
        target = 720
    elif video_bitrate_kbps < 2400:
        target = 1080
    else:
        target = original_height

    # Never upscale
    if original_height > 0 and target > original_height:
        return original_height
    return target


def unique_output_path(path: str) -> str:
    candidate = Path(path)
    count = 1
    while candidate.exists():
        candidate = Path(path).with_name(f"{Path(path).stem} ({count}){Path(path).suffix}")
        count += 1
    return str(candidate)


class VideoCompressor:
    """
    Handles two-pass FFmpeg compression with real-time progress callbacks,
    cancellation support, and automatic temporary file cleanup.
    """

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        """Cancel current encoding job."""
        with self._lock:
            self._cancelled = True
            if self._process:
                try:
                    self._process.kill()
                except Exception:
                    pass

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def compress(self, input_path, output_path, target_size_mb, preset="medium",
                 resolution_mode="Auto", keep_audio=True, safety_margin=0.96,
                 progress_callback=None, log_callback=None):
        """Encode privately, retry oversized results, and publish without overwriting."""
        if not math.isfinite(target_size_mb) or target_size_mb <= 0:
            raise ValueError("Choose a valid size greater than zero.")
        if os.path.normcase(os.path.abspath(input_path)) == os.path.normcase(os.path.abspath(output_path)):
            raise ValueError("Choose a different output file.")
        self._cancelled = False
        directory = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(directory, exist_ok=True)
        limit = target_size_mb * 1_000_000
        margin = safety_margin
        with tempfile.TemporaryDirectory(prefix=".dvc_", dir=directory) as temporary:
            staging = os.path.join(temporary, "video.mp4")
            for attempt in range(3):
                if self.is_cancelled:
                    raise RuntimeError("Compression cancelled.")
                if attempt and log_callback:
                    log_callback("Adjusting size and retrying...")
                result = self._compress_once(
                    input_path, staging, target_size_mb, preset, resolution_mode,
                    keep_audio, margin, progress_callback, log_callback)
                if self.is_cancelled:
                    raise RuntimeError("Compression cancelled.")
                if result["compressed_size"] <= limit:
                    # Exclusive creation also handles a file appearing during encoding.
                    destination = unique_output_path(output_path)
                    while True:
                        try:
                            with open(destination, "xb") as output:
                                try:
                                    with open(staging, "rb") as source:
                                        shutil.copyfileobj(source, output)
                                except BaseException:
                                    output.close()
                                    os.remove(destination)
                                    raise
                            break
                        except FileExistsError:
                            destination = unique_output_path(destination)
                    result["output_file"] = destination
                    result["under_target"] = True
                    return result
                margin *= (limit / result["compressed_size"]) * 0.90
            raise ValueError("Cannot fit this video. Try a larger size or a shorter clip.")

    def _compress_once(
        self,
        input_path: str,
        output_path: str,
        target_size_mb: float,
        preset: str = "medium",
        resolution_mode: str = "Auto",
        keep_audio: bool = True,
        safety_margin: float = 0.96,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Compress video using 2-pass FFmpeg to achieve target file size.

        progress_callback receives dict with:
            pass: 1 or 2
            current_sec: float
            duration: float
            speed: str
            pass_percent: float (0 - 100)
            overall_percent: float (0 - 100)
            eta_seconds: float
            status: str
        """
        ffmpeg_bin = get_ffmpeg_path()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable not found. Please configure FFmpeg path.")

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        info = get_video_info(input_path)
        duration = info["duration"]
        if duration <= 0:
            raise ValueError("Could not determine video duration. The file may be corrupt.")

        # Calculate bitrates
        has_audio = info["has_audio"] and keep_audio
        bitrates = calculate_bitrates(
            target_size_mb=target_size_mb,
            duration_sec=duration,
            has_audio=has_audio,
            safety_margin=safety_margin
        )
        video_kbps = bitrates["video_bitrate_kbps"]
        audio_kbps = bitrates["audio_bitrate_kbps"]

        # Build scale filter
        orig_height = info["height"]
        vf_filters = []
        if resolution_mode == "Auto":
            target_h = get_recommended_scale(video_kbps, orig_height)
            if target_h and orig_height > 0 and target_h < orig_height:
                vf_filters.append(f"scale=-2:'min(ih,{target_h})':flags=lanczos")
            else:
                vf_filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
        elif resolution_mode == "1080p":
            vf_filters.append("scale=-2:'min(ih,1080)':flags=lanczos")
        elif resolution_mode == "720p":
            vf_filters.append("scale=-2:'min(ih,720)':flags=lanczos")
        elif resolution_mode == "480p":
            vf_filters.append("scale=-2:'min(ih,480)':flags=lanczos")
        elif resolution_mode == "360p":
            vf_filters.append("scale=-2:'min(ih,360)':flags=lanczos")
        else:
            # Keep original, ensure even dimensions
            vf_filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

        vf_str = ",".join(vf_filters)

        # Temporary 2-pass log files
        temp_dir = tempfile.mkdtemp(prefix="dvc_pass_")
        pass_log_prefix = os.path.join(temp_dir, "ffmpeg2pass")
        null_device = "NUL" if os.name == "nt" else "/dev/null"

        start_time = time.time()

        def emit_log(msg: str):
            if log_callback:
                log_callback(msg)

        emit_log(f"Starting 2-Pass compression for {info['filename']}")
        emit_log(f"Target size: {target_size_mb} MB (with {int((1-safety_margin)*100)}% safety buffer)")
        emit_log(f"Calculated bitrates: Video {video_kbps} kbps | Audio {audio_kbps} kbps")
        emit_log(f"Duration: {info['duration_str']} | Preset: {preset} | Filter: {vf_str}")

        # Ensure output directory exists
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        try:
            # -------------------------------------------------------------
            # PASS 1
            # -------------------------------------------------------------
            pass1_cmd = [
                ffmpeg_bin, "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-b:v", f"{video_kbps}k",
                "-pass", "1",
                "-passlogfile", pass_log_prefix,
                "-preset", preset,
                "-vf", vf_str,
                "-an",
                "-f", "null",
                "-progress", "pipe:1",
                null_device
            ]

            emit_log(f"Executing Pass 1: {' '.join(pass1_cmd)}")
            success = self._run_ffmpeg_pass(
                pass_cmd=pass1_cmd,
                pass_num=1,
                duration=duration,
                progress_callback=progress_callback,
                log_callback=log_callback
            )

            if not success or self.is_cancelled:
                raise RuntimeError("Pass 1 cancelled or failed.")

            # -------------------------------------------------------------
            # PASS 2
            # -------------------------------------------------------------
            pass2_cmd = [
                ffmpeg_bin, "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-b:v", f"{video_kbps}k",
                "-pass", "2",
                "-passlogfile", pass_log_prefix,
                "-preset", preset,
                "-vf", vf_str,
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"
            ]

            if has_audio:
                pass2_cmd.extend(["-c:a", "aac", "-b:a", f"{audio_kbps}k"])
            else:
                pass2_cmd.append("-an")

            pass2_cmd.extend([
                "-progress", "pipe:1",
                output_path
            ])

            emit_log(f"Executing Pass 2: {' '.join(pass2_cmd)}")
            success = self._run_ffmpeg_pass(
                pass_cmd=pass2_cmd,
                pass_num=2,
                duration=duration,
                progress_callback=progress_callback,
                log_callback=log_callback
            )

            if not success or self.is_cancelled:
                raise RuntimeError("Pass 2 cancelled or failed.")

        finally:
            # Clean up temp 2-pass logs
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        if self.is_cancelled:
            # Remove partial output if cancelled
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            raise RuntimeError("Compression was cancelled by user.")

        if not os.path.exists(output_path):
            raise RuntimeError("Compression finished but output file was not created.")

        output_size = os.path.getsize(output_path)
        elapsed = time.time() - start_time
        reduction = (1.0 - (output_size / info["filesize"])) * 100.0 if info["filesize"] > 0 else 0

        result = {
            "success": True,
            "input_file": input_path,
            "output_file": output_path,
            "original_size": info["filesize"],
            "original_size_str": info["filesize_str"],
            "compressed_size": output_size,
            "compressed_size_str": format_bytes(output_size),
            "target_size_mb": target_size_mb,
            "reduction_percent": round(reduction, 1),
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_str": format_seconds(elapsed),
            "under_target": output_size <= (target_size_mb * 1_000_000)
        }

        emit_log(
            f"Compression completed in {result['elapsed_str']}! "
            f"Final size: {result['compressed_size_str']} "
            f"({result['reduction_percent']}% reduction)"
        )

        return result

    def _run_ffmpeg_pass(
        self,
        pass_cmd: list,
        pass_num: int,
        duration: float,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
        log_callback: Optional[Callable[[str], None]]
    ) -> bool:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        with self._lock:
            if self._cancelled:
                return False
            self._process = subprocess.Popen(
                pass_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                bufsize=1,
                universal_newlines=True
            )

        # Thread to read stderr so it doesn't block buffer and logs warnings/errors
        def read_stderr():
            try:
                for line in self._process.stderr:
                    line_clean = line.strip()
                    if line_clean and log_callback:
                        log_callback(f"[FFmpeg] {line_clean}")
            except Exception:
                pass

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()

        # Parse stdout (-progress pipe:1)
        speed = "1.0x"
        current_sec = 0.0
        pass_start_time = time.time()

        try:
            for line in self._process.stdout:
                if self.is_cancelled:
                    break

                line = line.strip()
                if not line:
                    continue

                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()

                    if key == "out_time_us":
                        try:
                            us = int(val)
                            current_sec = us / 1_000_000.0
                        except ValueError:
                            pass
                    elif key == "out_time_ms":
                        try:
                            ms = int(val)
                            current_sec = ms / 1_000_000.0
                        except ValueError:
                            pass
                    elif key == "speed":
                        speed = val

                    elif key == "progress":
                        # Compute progress
                        if duration > 0:
                            pass_percent = min(100.0, max(0.0, (current_sec / duration) * 100.0))
                        else:
                            pass_percent = 0.0

                        overall_percent = ((pass_num - 1) * 50.0) + (pass_percent * 0.5)

                        # ETA calculation
                        elapsed = time.time() - pass_start_time
                        eta_seconds = 0.0
                        if current_sec > 0 and duration > 0:
                            remaining_current_pass = max(0.0, duration - current_sec)
                            rate = current_sec / elapsed if elapsed > 0 else 1.0
                            current_pass_remaining_time = remaining_current_pass / rate if rate > 0 else 0
                            if pass_num == 1:
                                # Estimate pass 2 takes roughly same time
                                eta_seconds = current_pass_remaining_time + (duration / rate if rate > 0 else duration)
                            else:
                                eta_seconds = current_pass_remaining_time

                        if progress_callback:
                            progress_callback({
                                "pass": pass_num,
                                "current_sec": current_sec,
                                "duration": duration,
                                "speed": speed,
                                "pass_percent": round(pass_percent, 1),
                                "overall_percent": round(overall_percent, 1),
                                "eta_seconds": max(0, int(eta_seconds)),
                                "status": f"Pass {pass_num}/2: {'Analyzing' if pass_num == 1 else 'Compressing'}"
                            })

            self._process.wait()
            stderr_thread.join(timeout=2)
            return self._process.returncode == 0 and not self.is_cancelled

        except Exception as e:
            if log_callback:
                log_callback(f"Error in pass {pass_num}: {e}")
            return False
        finally:
            with self._lock:
                self._process = None

