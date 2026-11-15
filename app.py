"""
app.py - Modern Tkinter GUI for Discord Video Compressor.
"""

import os
import sys
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, Any

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
    BaseTk = TkinterDnD.Tk
except ImportError:
    HAS_DND = False
    BaseTk = tk.Tk

from compressor import (
    VideoCompressor,
    get_video_info,
    calculate_bitrates,
    format_bytes,
    format_seconds,
    get_recommended_scale
)
import ffmpeg_finder


# ---------------------------------------------------------------------------
# Color Palette (Discord-inspired dark theme)
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#1e1f22",
    "card": "#2b2d31",
    "card_border": "#383a40",
    "input_bg": "#313338",
    "text": "#f2f3f5",
    "text_muted": "#949ba4",
    "accent": "#5865f2",        # Discord Blurple
    "accent_hover": "#4752c4",
    "accent_active": "#3c45a5",
    "success": "#23a55a",       # Discord Green
    "danger": "#da373c",        # Discord Red
    "danger_hover": "#a1282c",
    "warning": "#f0b232",
    "highlight": "#3ba55c"
}

FONT_FAMILY = "Segoe UI" if os.name == "nt" else "Helvetica"


class DiscordVideoCompressorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Discord Video Compressor")
        self.root.geometry("780x880")
        self.root.minsize(700, 750)
        self.root.configure(bg=COLORS["bg"])

        self.compressor = VideoCompressor()
        self.is_compressing = False
        self.video_info: Optional[Dict[str, Any]] = None

        # State Variables
        self.input_file_var = tk.StringVar()
        self.output_file_var = tk.StringVar()
        self.preset_var = tk.StringVar(value="8")  # "8", "20", "50", "custom"
        self.custom_size_var = tk.StringVar(value="8")
        self.speed_var = tk.StringVar(value="medium")
        self.resolution_var = tk.StringVar(value="Auto")
        self.audio_var = tk.StringVar(value="keep")
        self.safety_margin_var = tk.StringVar(value="4%")
        self.show_logs_var = tk.BooleanVar(value=False)

        self.setup_styles()
        self.create_widgets()
        self.check_ffmpeg_status()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=(FONT_FAMILY, 10))
        self.style.configure("TFrame", background=COLORS["bg"])
        self.style.configure("Card.TFrame", background=COLORS["card"], relief="flat")
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=(FONT_FAMILY, 10))
        self.style.configure("Card.TLabel", background=COLORS["card"], foreground=COLORS["text"], font=(FONT_FAMILY, 10))
        self.style.configure("Muted.TLabel", background=COLORS["card"], foreground=COLORS["text_muted"], font=(FONT_FAMILY, 9))
        self.style.configure("Header.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=(FONT_FAMILY, 16, "bold"))
        self.style.configure("Section.TLabel", background=COLORS["card"], foreground=COLORS["text"], font=(FONT_FAMILY, 11, "bold"))

        # Primary Blurple Button
        self.style.configure(
            "Primary.TButton",
            background=COLORS["accent"],
            foreground="#ffffff",
            font=(FONT_FAMILY, 11, "bold"),
            padding=(16, 10),
            borderwidth=0
        )
        self.style.map("Primary.TButton",
            background=[("active", COLORS["accent_hover"]), ("disabled", "#4e5058")],
            foreground=[("disabled", "#80848e")]
        )

        # Danger Button (Cancel)
        self.style.configure(
            "Danger.TButton",
            background=COLORS["danger"],
            foreground="#ffffff",
            font=(FONT_FAMILY, 10, "bold"),
            padding=(12, 8),
            borderwidth=0
        )
        self.style.map("Danger.TButton",
            background=[("active", COLORS["danger_hover"]), ("disabled", "#4e5058")],
            foreground=[("disabled", "#80848e")]
        )

        # Secondary Button
        self.style.configure(
            "Secondary.TButton",
            background=COLORS["input_bg"],
            foreground=COLORS["text"],
            font=(FONT_FAMILY, 9),
            padding=(10, 6),
            borderwidth=0
        )
        self.style.map("Secondary.TButton",
            background=[("active", COLORS["card_border"])]
        )

        # Radio & Checkbutton
        self.style.configure(
            "TRadiobutton",
            background=COLORS["card"],
            foreground=COLORS["text"],
            font=(FONT_FAMILY, 10),
            focuscolor=COLORS["card"]
        )
        self.style.map("TRadiobutton",
            background=[("active", COLORS["card"])],
            foreground=[("active", COLORS["text"])]
        )

        self.style.configure(
            "TCheckbutton",
            background=COLORS["card"],
            foreground=COLORS["text"],
            font=(FONT_FAMILY, 9),
            focuscolor=COLORS["card"]
        )

        # Progressbar
        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor=COLORS["input_bg"],
            background=COLORS["accent"],
            thickness=14
        )

        # Combobox
        self.style.configure(
            "TCombobox",
            fieldbackground=COLORS["input_bg"],
            background=COLORS["input_bg"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"]
        )

    def create_widgets(self):
        # Main scrollable canvas container to ensure it works on any screen size
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # Header Bar
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 14))

        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT)

        app_title = ttk.Label(title_box, text="Discord Video Compressor", style="Header.TLabel")
        app_title.pack(anchor="w")

        subtitle = ttk.Label(
            title_box,
            text="Compress videos with 2-pass FFmpeg to fit Discord upload limits without quality waste",
            foreground=COLORS["text_muted"],
            font=(FONT_FAMILY, 9)
        )
        subtitle.pack(anchor="w")

        # FFmpeg Status Indicator
        self.ffmpeg_badge_frame = ttk.Frame(header_frame)
        self.ffmpeg_badge_frame.pack(side=tk.RIGHT, anchor="center")

        self.ffmpeg_status_lbl = tk.Label(
            self.ffmpeg_badge_frame,
            text="Checking FFmpeg...",
            font=(FONT_FAMILY, 9),
            bg=COLORS["input_bg"],
            fg=COLORS["text_muted"],
            padx=10,
            pady=4,
            relief="flat"
        )
        self.ffmpeg_status_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_locate_ffmpeg = ttk.Button(
            self.ffmpeg_badge_frame,
            text="Locate FFmpeg",
            style="Secondary.TButton",
            command=self.browse_ffmpeg_binary
        )

        # -------------------------------------------------------------
        # Section 1: Input Video Selection Card
        # -------------------------------------------------------------
        input_card = ttk.Frame(container, style="Card.TFrame", padding=14)
        input_card.pack(fill=tk.X, pady=(0, 12))

        lbl_s1 = ttk.Label(input_card, text="1. Select Video File", style="Section.TLabel")
        lbl_s1.pack(anchor="w", pady=(0, 8))

        file_row = ttk.Frame(input_card, style="Card.TFrame")
        file_row.pack(fill=tk.X, pady=(0, 6))

        self.entry_input = tk.Entry(
            file_row,
            textvariable=self.input_file_var,
            bg=COLORS["input_bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=(FONT_FAMILY, 10),
            relief="flat"
        )
        self.entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))

        btn_browse = ttk.Button(
            file_row,
            text="Browse...",
            style="Secondary.TButton",
            command=self.browse_input_file
        )
        btn_browse.pack(side=tk.RIGHT)

        # DnD support if installed
        if HAS_DND:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self.on_drop_file)
            dnd_hint = " (Drag & Drop supported)"
        else:
            dnd_hint = ""

        # Video Metadata Card (hidden until file selected)
        self.info_card = ttk.Frame(input_card, style="Card.TFrame")
        self.lbl_info_details = ttk.Label(
            self.info_card,
            text=f"No video selected.{dnd_hint}",
            style="Muted.TLabel"
        )
        self.lbl_info_details.pack(anchor="w", pady=(4, 0))
        self.info_card.pack(fill=tk.X)

        # -------------------------------------------------------------
        # Section 2: Preset Target Size Selection Card
        # -------------------------------------------------------------
        preset_card = ttk.Frame(container, style="Card.TFrame", padding=14)
        preset_card.pack(fill=tk.X, pady=(0, 12))

        lbl_s2 = ttk.Label(preset_card, text="2. Choose Target File Size Preset", style="Section.TLabel")
        lbl_s2.pack(anchor="w", pady=(0, 8))

        preset_row = ttk.Frame(preset_card, style="Card.TFrame")
        preset_row.pack(fill=tk.X, pady=(0, 8))

        r_8 = ttk.Radiobutton(
            preset_row,
            text="8 MB (Free Discord limit)",
            value="8",
            variable=self.preset_var,
            command=self.on_preset_changed
        )
        r_8.pack(side=tk.LEFT, padx=(0, 14))

        r_20 = ttk.Radiobutton(
            preset_row,
            text="20 MB",
            value="20",
            variable=self.preset_var,
            command=self.on_preset_changed
        )
        r_20.pack(side=tk.LEFT, padx=(0, 14))

        r_50 = ttk.Radiobutton(
            preset_row,
            text="50 MB (Nitro Basic)",
            value="50",
            variable=self.preset_var,
            command=self.on_preset_changed
        )
        r_50.pack(side=tk.LEFT, padx=(0, 14))

        r_custom = ttk.Radiobutton(
            preset_row,
            text="Custom Target:",
            value="custom",
            variable=self.preset_var,
            command=self.on_preset_changed
        )
        r_custom.pack(side=tk.LEFT, padx=(0, 6))

        self.entry_custom_size = tk.Entry(
            preset_row,
            textvariable=self.custom_size_var,
            width=6,
            bg=COLORS["input_bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=(FONT_FAMILY, 10, "bold"),
            relief="flat",
            state="disabled"
        )
        self.entry_custom_size.pack(side=tk.LEFT, ipady=3, padx=(0, 4))
        self.custom_size_var.trace_add("write", lambda *args: self.update_bitrate_preview())

        lbl_mb = ttk.Label(preset_row, text="MB", style="Card.TLabel")
        lbl_mb.pack(side=tk.LEFT)

        # Dynamic Bitrate Preview Box
        self.preview_box = ttk.Frame(preset_card, style="Card.TFrame")
        self.preview_box.pack(fill=tk.X, pady=(6, 0))

        self.lbl_preview = ttk.Label(
            self.preview_box,
            text="Target Bitrate Preview: Select a video to calculate optimal bitrates.",
            foreground=COLORS["accent"],
            font=(FONT_FAMILY, 9, "bold"),
            background=COLORS["card"]
        )
        self.lbl_preview.pack(anchor="w")

        # -------------------------------------------------------------
        # Section 3: Compression Settings (Options)
        # -------------------------------------------------------------
        opts_card = ttk.Frame(container, style="Card.TFrame", padding=14)
        opts_card.pack(fill=tk.X, pady=(0, 12))

        lbl_s3 = ttk.Label(opts_card, text="3. Encoding Options", style="Section.TLabel")
        lbl_s3.pack(anchor="w", pady=(0, 8))

        opts_row = ttk.Frame(opts_card, style="Card.TFrame")
        opts_row.pack(fill=tk.X)

        # Resolution Option
        lbl_res = ttk.Label(opts_row, text="Resolution:", style="Muted.TLabel")
        lbl_res.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        self.cb_res = ttk.Combobox(
            opts_row,
            textvariable=self.resolution_var,
            values=["Auto", "Keep Original", "1080p", "720p", "480p", "360p"],
            state="readonly",
            width=14
        )
        self.cb_res.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=4)
        self.cb_res.bind("<<ComboboxSelected>>", lambda e: self.update_bitrate_preview())

        # Audio Option
        lbl_aud = ttk.Label(opts_row, text="Audio Track:", style="Muted.TLabel")
        lbl_aud.grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        self.cb_aud = ttk.Combobox(
            opts_row,
            textvariable=self.audio_var,
            values=["keep", "mute"],
            state="readonly",
            width=12
        )
        self.cb_aud.grid(row=0, column=3, sticky="w", padx=(0, 16), pady=4)
        self.cb_aud.bind("<<ComboboxSelected>>", lambda e: self.update_bitrate_preview())

        # Preset / Speed
        lbl_spd = ttk.Label(opts_row, text="Encoder Speed:", style="Muted.TLabel")
        lbl_spd.grid(row=0, column=4, sticky="w", padx=(0, 6), pady=4)
        self.cb_spd = ttk.Combobox(
            opts_row,
            textvariable=self.speed_var,
            values=["medium", "fast", "faster", "slow", "veryslow"],
            state="readonly",
            width=10
        )
        self.cb_spd.grid(row=0, column=5, sticky="w", pady=4)

        # -------------------------------------------------------------
        # Section 4: Output File Destination
        # -------------------------------------------------------------
        out_card = ttk.Frame(container, style="Card.TFrame", padding=14)
        out_card.pack(fill=tk.X, pady=(0, 12))

        lbl_s4 = ttk.Label(out_card, text="4. Output Destination", style="Section.TLabel")
        lbl_s4.pack(anchor="w", pady=(0, 8))

        out_row = ttk.Frame(out_card, style="Card.TFrame")
        out_row.pack(fill=tk.X)

        self.entry_output = tk.Entry(
            out_row,
            textvariable=self.output_file_var,
            bg=COLORS["input_bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=(FONT_FAMILY, 10),
            relief="flat"
        )
        self.entry_output.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))

        btn_browse_out = ttk.Button(
            out_row,
            text="Change...",
            style="Secondary.TButton",
            command=self.browse_output_file
        )
        btn_browse_out.pack(side=tk.RIGHT)

        # -------------------------------------------------------------
        # Section 5: Progress & Actions
        # -------------------------------------------------------------
        action_card = ttk.Frame(container, style="Card.TFrame", padding=14)
        action_card.pack(fill=tk.X, pady=(0, 12))

        btn_row = ttk.Frame(action_card, style="Card.TFrame")
        btn_row.pack(fill=tk.X, pady=(0, 10))

        self.btn_compress = ttk.Button(
            btn_row,
            text="⚡ Compress Video",
            style="Primary.TButton",
            command=self.start_compression
        )
        self.btn_compress.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_cancel = ttk.Button(
            btn_row,
            text="Cancel",
            style="Danger.TButton",
            state="disabled",
            command=self.cancel_compression
        )
        self.btn_cancel.pack(side=tk.LEFT)

        # Open output & play buttons (shown upon success)
        self.btn_open_folder = ttk.Button(
            btn_row,
            text="Open Folder",
            style="Secondary.TButton",
            command=self.open_output_folder
        )
        self.btn_play_video = ttk.Button(
            btn_row,
            text="Play Video",
            style="Secondary.TButton",
            command=self.play_output_video
        )

        # Progress bar
        self.progress_bar = ttk.Progressbar(
            action_card,
            orient="horizontal",
            mode="determinate",
            style="Horizontal.TProgressbar"
        )
        self.progress_bar.pack(fill=tk.X, pady=(4, 6))

        # Status text & ETA
        status_row = ttk.Frame(action_card, style="Card.TFrame")
        status_row.pack(fill=tk.X)

        self.lbl_status = ttk.Label(
            status_row,
            text="Ready to compress",
            style="Card.TLabel",
            font=(FONT_FAMILY, 9, "bold")
        )
        self.lbl_status.pack(side=tk.LEFT)

        self.lbl_eta = ttk.Label(
            status_row,
            text="",
            style="Muted.TLabel"
        )
        self.lbl_eta.pack(side=tk.RIGHT)

        # Result Banner
        self.lbl_result = tk.Label(
            action_card,
            text="",
            font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["card"],
            fg=COLORS["success"],
            wraplength=700,
            justify="left"
        )
        self.lbl_result.pack(anchor="w", pady=(6, 0))

        # -------------------------------------------------------------
        # Section 6: Collapsible FFmpeg Log Drawer
        # -------------------------------------------------------------
        log_header = ttk.Frame(container)
        log_header.pack(fill=tk.X, pady=(4, 4))

        self.btn_toggle_logs = ttk.Button(
            log_header,
            text="▶ Show FFmpeg Logs",
            style="Secondary.TButton",
            command=self.toggle_logs
        )
        self.btn_toggle_logs.pack(side=tk.LEFT)

        self.log_container = ttk.Frame(container)

        self.log_text = tk.Text(
            self.log_container,
            height=8,
            bg="#111214",
            fg="#dbdee1",
            font=("Consolas", 8),
            wrap="word",
            relief="flat",
            padx=8,
            pady=8
        )
        log_scroll = ttk.Scrollbar(self.log_container, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def check_ffmpeg_status(self):
        """Check if FFmpeg and FFprobe are accessible and update badge."""
        ffmpeg_bin = ffmpeg_finder.get_ffmpeg_path()
        ffprobe_bin = ffmpeg_finder.get_ffprobe_path()

        if ffmpeg_bin:
            version_str = ffmpeg_finder.get_ffmpeg_version(ffmpeg_bin) or "Detected"
            short_ver = version_str.split("Copyright")[0].strip() if "Copyright" in version_str else version_str[:25]
            self.ffmpeg_status_lbl.config(
                text=f"✓ FFmpeg Ready ({short_ver})",
                fg=COLORS["success"],
                bg=COLORS["input_bg"]
            )
            self.btn_locate_ffmpeg.pack_forget()
        else:
            self.ffmpeg_status_lbl.config(
                text="⚠ FFmpeg not found on PATH",
                fg=COLORS["warning"],
                bg=COLORS["input_bg"]
            )
            self.btn_locate_ffmpeg.pack(side=tk.LEFT)

    def browse_ffmpeg_binary(self):
        """Allow user to select ffmpeg.exe manually."""
        file_path = filedialog.askopenfilename(
            title="Locate ffmpeg executable",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")] if os.name == "nt" else [("All Files", "*.*")]
        )
        if file_path:
            success, msg = ffmpeg_finder.set_custom_ffmpeg_path(file_path)
            if success:
                messagebox.showinfo("FFmpeg Found", "FFmpeg path configured successfully!")
                self.check_ffmpeg_status()
            else:
                messagebox.showerror("Invalid Binary", msg)

    def on_drop_file(self, event):
        """Handles Drag and Drop files."""
        path = event.data.strip()
        # On Windows, path may be enclosed in curly braces if it has spaces
        if path.startswith("{") and path.endswith("}"):
            path = path[1:-1]
        if os.path.exists(path):
            self.set_input_file(path)

    def browse_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Video to Compress",
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v *.ts"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            self.set_input_file(file_path)

    def set_input_file(self, path: str):
        self.input_file_var.set(path)
        self.lbl_status.config(text="Analyzing video...", foreground=COLORS["accent"])
        self.root.update_idletasks()

        threading.Thread(target=self._analyze_video_worker, args=(path,), daemon=True).start()

    def _analyze_video_worker(self, path: str):
        try:
            info = get_video_info(path)
            self.video_info = info
            self.root.after(0, self._on_video_analyzed, info)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Analysis Error", f"Failed to analyze video:\n{e}"))
            self.root.after(0, lambda: self.lbl_status.config(text="Ready to compress", foreground=COLORS["text"]))

    def _on_video_analyzed(self, info: Dict[str, Any]):
        audio_str = f"{info['audio_codec'].upper()}" if info['has_audio'] else "None (Muted)"
        fps_str = f" @ {info['fps']} fps" if info['fps'] > 0 else ""
        details = (
            f"File: {info['filename']}\n"
            f"Size: {info['filesize_str']}  |  Duration: {info['duration_str']}  |  "
            f"Resolution: {info['resolution_str']}{fps_str}  |  "
            f"Video: {info['video_codec']}  |  Audio: {audio_str}"
        )
        self.lbl_info_details.config(text=details, style="Card.TLabel")
        self.lbl_status.config(text="Video loaded successfully.", foreground=COLORS["text"])

        # Update auto output file path
        self.update_default_output_path()
        self.update_bitrate_preview()

    def get_selected_target_mb(self) -> float:
        choice = self.preset_var.get()
        if choice in ("8", "20", "50"):
            return float(choice)
        try:
            val = float(self.custom_size_var.get().strip())
            return max(0.1, val)
        except ValueError:
            return 8.0

    def on_preset_changed(self):
        choice = self.preset_var.get()
        if choice == "custom":
            self.entry_custom_size.config(state="normal")
            self.entry_custom_size.focus_set()
        else:
            self.entry_custom_size.config(state="disabled")

        self.update_default_output_path()
        self.update_bitrate_preview()

    def update_default_output_path(self):
        in_path = self.input_file_var.get().strip()
        if not in_path:
            return

        target_mb = self.get_selected_target_mb()
        dir_name = os.path.dirname(in_path)
        base_name = os.path.splitext(os.path.basename(in_path))[0]
        # Remove previous _discord suffix if already present
        if "_discord" in base_name:
            base_name = base_name.split("_discord")[0]

        target_label = f"{int(target_mb)}MB" if target_mb.is_integer() else f"{target_mb}MB"
        out_name = f"{base_name}_discord_{target_label}.mp4"
        self.output_file_var.set(os.path.join(dir_name, out_name))

    def update_bitrate_preview(self):
        if not self.video_info or self.video_info.get("duration", 0) <= 0:
            self.lbl_preview.config(text="Target Bitrate Preview: Select a video to view bitrate calculation.")
            return

        target_mb = self.get_selected_target_mb()
        dur = self.video_info["duration"]
        keep_aud = (self.audio_var.get() == "keep") and self.video_info["has_audio"]

        bitrates = calculate_bitrates(target_mb, dur, has_audio=keep_aud, safety_margin=0.96)
        v_kbps = bitrates["video_bitrate_kbps"]
        a_kbps = bitrates["audio_bitrate_kbps"]
        est_mb = bitrates["estimated_size_mb"]

        res_mode = self.resolution_var.get()
        if res_mode == "Auto":
            rec_h = get_recommended_scale(v_kbps, self.video_info["height"])
            res_str = f"Auto ({rec_h}p)" if rec_h else "Auto"
        else:
            res_str = res_mode

        aud_str = f"{a_kbps} kbps" if keep_aud else "Muted"

        # Warning if bitrate is very low
        warn_str = ""
        if v_kbps < 150:
            warn_str = " ⚠ Very long video for this size target! Video may have artifacts."

        preview_text = (
            f"Bitrate Plan for {target_mb} MB: Video: ~{v_kbps} kbps | Audio: {aud_str} | "
            f"Resolution: {res_str} | Estimated Output: ~{est_mb} MB{warn_str}"
        )
        self.lbl_preview.config(
            text=preview_text,
            foreground=COLORS["warning"] if warn_str else COLORS["accent"]
        )

    def browse_output_file(self):
        current = self.output_file_var.get().strip()
        initial_dir = os.path.dirname(current) if current else None
        initial_file = os.path.basename(current) if current else "output.mp4"

        file_path = filedialog.asksaveasfilename(
            title="Select Output Location",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")]
        )
        if file_path:
            self.output_file_var.set(file_path)

    def toggle_logs(self):
        if self.show_logs_var.get():
            self.log_container.pack_forget()
            self.btn_toggle_logs.config(text="▶ Show FFmpeg Logs")
            self.show_logs_var.set(False)
        else:
            self.log_container.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
            self.btn_toggle_logs.config(text="▼ Hide FFmpeg Logs")
            self.show_logs_var.set(True)

    def append_log(self, text: str):
        def _append():
            self.log_text.insert(tk.END, text + "\n")
            self.log_text.see(tk.END)
        self.root.after(0, _append)

    # -------------------------------------------------------------
    # Compression Execution & Threading
    # -------------------------------------------------------------
    def start_compression(self):
        input_path = self.input_file_var.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Missing File", "Please select an existing input video file.")
            return

        if not ffmpeg_finder.get_ffmpeg_path():
            messagebox.showerror(
                "FFmpeg Missing",
                "FFmpeg is required to compress videos. Please install FFmpeg or click 'Locate FFmpeg'."
            )
            return

        output_path = self.output_file_var.get().strip()
        if not output_path:
            self.update_default_output_path()
            output_path = self.output_file_var.get().strip()

        if os.path.abspath(input_path) == os.path.abspath(output_path):
            messagebox.showerror("Invalid Output", "Output file cannot be the same as input file.")
            return

        target_mb = self.get_selected_target_mb()
        if target_mb <= 0:
            messagebox.showerror("Invalid Size", "Target file size must be greater than 0 MB.")
            return

        # UI state during compression
        self.is_compressing = True
        self.btn_compress.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.btn_open_folder.pack_forget()
        self.btn_play_video.pack_forget()
        self.lbl_result.config(text="")
        self.progress_bar["value"] = 0
        self.lbl_status.config(text="Initializing FFmpeg 2-Pass encoder...", foreground=COLORS["accent"])
        self.lbl_eta.config(text="")
        self.log_text.delete("1.0", tk.END)

        preset = self.speed_var.get()
        res_mode = self.resolution_var.get()
        keep_aud = (self.audio_var.get() == "keep")

        # Start thread
        thread = threading.Thread(
            target=self._compress_worker,
            args=(input_path, output_path, target_mb, preset, res_mode, keep_aud),
            daemon=True
        )
        thread.start()

    def cancel_compression(self):
        if self.is_compressing:
            self.lbl_status.config(text="Cancelling encoding...", foreground=COLORS["danger"])
            self.compressor.cancel()

    def _compress_worker(
        self,
        input_path: str,
        output_path: str,
        target_mb: float,
        preset: str,
        res_mode: str,
        keep_aud: bool
    ):
        def on_progress(p: Dict[str, Any]):
            def _update():
                overall = p["overall_percent"]
                self.progress_bar["value"] = overall
                pass_num = p["pass"]
                pass_pct = p["pass_percent"]
                speed = p["speed"]
                eta_s = p["eta_seconds"]

                eta_str = f"ETA: {format_seconds(eta_s)}" if eta_s > 0 else ""
                speed_str = f"Speed: {speed}" if speed else ""

                status_msg = f"Pass {pass_num}/2: {'Analyzing' if pass_num == 1 else 'Encoding'} ({pass_pct:.0f}%)"
                if speed_str:
                    status_msg += f"  [{speed_str}]"

                self.lbl_status.config(text=status_msg, foreground=COLORS["text"])
                self.lbl_eta.config(text=eta_str)
            self.root.after(0, _update)

        try:
            res = self.compressor.compress(
                input_path=input_path,
                output_path=output_path,
                target_size_mb=target_mb,
                preset=preset,
                resolution_mode=res_mode,
                keep_audio=keep_aud,
                safety_margin=0.96,
                progress_callback=on_progress,
                log_callback=self.append_log
            )
            self.root.after(0, self._on_compression_success, res)
        except Exception as e:
            self.root.after(0, self._on_compression_error, str(e))

    def _on_compression_success(self, res: Dict[str, Any]):
        self.is_compressing = False
        self.btn_compress.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.progress_bar["value"] = 100
        self.lbl_eta.config(text="")

        out_size_str = res["compressed_size_str"]
        orig_size_str = res["original_size_str"]
        reduction = res["reduction_percent"]
        elapsed = res["elapsed_str"]
        under_target = res["under_target"]

        if under_target:
            status_text = f"✓ Compression Complete in {elapsed}!"
            color = COLORS["success"]
            summary = (
                f"🎉 Ready for Discord!\n"
                f"Original: {orig_size_str}  →  Compressed: {out_size_str} ({reduction}% reduction)\n"
                f"Saved to: {res['output_file']}"
            )
        else:
            status_text = f"Compression finished in {elapsed} (slightly over target)"
            color = COLORS["warning"]
            summary = (
                f"Original: {orig_size_str}  →  Compressed: {out_size_str} ({reduction}% reduction)\n"
                f"Saved to: {res['output_file']}"
            )

        self.lbl_status.config(text=status_text, foreground=color)
        self.lbl_result.config(text=summary, fg=color)

        # Show action buttons
        self.btn_open_folder.pack(side=tk.LEFT, padx=(10, 0))
        self.btn_play_video.pack(side=tk.LEFT, padx=(10, 0))

    def _on_compression_error(self, err_msg: str):
        self.is_compressing = False
        self.btn_compress.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.lbl_eta.config(text="")

        if "cancelled" in err_msg.lower():
            self.lbl_status.config(text="Compression was cancelled.", foreground=COLORS["warning"])
            self.progress_bar["value"] = 0
        else:
            self.lbl_status.config(text="Compression failed.", foreground=COLORS["danger"])
            self.lbl_result.config(text=f"Error: {err_msg}", fg=COLORS["danger"])
            messagebox.showerror("Compression Error", f"Video compression failed:\n\n{err_msg}")

    def open_output_folder(self):
        out_path = self.output_file_var.get().strip()
        if out_path and os.path.exists(out_path):
            folder = os.path.dirname(os.path.abspath(out_path))
            if os.name == "nt":
                subprocess.Popen(f'explorer /select,"{os.path.abspath(out_path)}"')
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", out_path])
            else:
                subprocess.Popen(["xdg-open", folder])

    def play_output_video(self):
        out_path = self.output_file_var.get().strip()
        if out_path and os.path.exists(out_path):
            if os.name == "nt":
                os.startfile(out_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", out_path])
            else:
                subprocess.Popen(["xdg-open", out_path])

    def on_close(self):
        if self.is_compressing:
            if messagebox.askyesno("Exit Confirmation", "Compression is currently running. Do you want to cancel and exit?"):
                self.compressor.cancel()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = BaseTk()
    app = DiscordVideoCompressorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

