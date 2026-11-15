"""
app.py - Modern Tkinter GUI for Discord Video Compressor.
"""

import os
import math
import sys
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, Any

try:
    from tkinterdnd2 import COPY, DND_FILES, TkinterDnD
    HAS_DND = True
    BaseTk = TkinterDnD.Tk
except ImportError:
    HAS_DND = False
    BaseTk = tk.Tk

from compressor import (
    unique_output_path,
    VideoCompressor,
    get_video_info,
    calculate_bitrates,
    format_bytes,
    format_seconds,
    get_recommended_scale
)
from file_clipboard import copy_file
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
        self.root.geometry("780x650")
        self.root.minsize(700, 600)
        self.root.configure(bg=COLORS["bg"])

        self.compressor = VideoCompressor()
        self.is_compressing = False
        self.result_path = None
        self.custom_output = False
        self.video_info: Optional[Dict[str, Any]] = None

        # State Variables
        self.input_file_var = tk.StringVar()
        self.output_file_var = tk.StringVar()
        self.preset_var = tk.StringVar(value="20")
        self.custom_size_var = tk.StringVar(value="20")
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
            font=(FONT_FAMILY, 10, "bold"),
            padding=(12, 8),
            width=11,
            borderwidth=0
        )
        self.style.map("Primary.TButton",
            background=[("active", COLORS["accent_hover"]), ("disabled", "#4e5058")],
            foreground=[("disabled", "#80848e")]
        )

        # Danger Button (Cancel)
        self.style.configure(
            "Danger.TButton",
            width=11,
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

        self.style.configure("Action.TButton", font=(FONT_FAMILY, 10, "bold"),
                             padding=(12, 8), width=11, borderwidth=0,
                             background=COLORS["input_bg"], foreground=COLORS["text"])
        self.style.map("Action.TButton", background=[("active", COLORS["card_border"])])

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
        viewport = tk.Canvas(self.root, bg=COLORS["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(self.root, orient="vertical", command=viewport.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        viewport.pack(fill=tk.BOTH, expand=True)
        viewport.configure(yscrollcommand=scroll.set)
        container = ttk.Frame(viewport, padding=(20, 16))
        content = viewport.create_window((0, 0), window=container, anchor="nw")
        container.bind("<Configure>", lambda event: viewport.configure(scrollregion=viewport.bbox("all")))
        viewport.bind("<Configure>", lambda event: viewport.itemconfigure(content, width=event.width))
        self.root.bind("<MouseWheel>", lambda event: viewport.yview_scroll(-int(event.delta / 120), "units"))

        # Header Bar
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 14))

        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT)

        app_title = ttk.Label(title_box, text="Discord Video Compressor", style="Header.TLabel")
        app_title.pack(anchor="w")

        subtitle = ttk.Label(
            title_box,
            text="",
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

        lbl_s1 = ttk.Label(input_card, text="1. Video", style="Section.TLabel")
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

        lbl_s2 = ttk.Label(preset_card, text="2. Size", style="Section.TLabel")
        lbl_s2.pack(anchor="w", pady=(0, 8))

        preset_row = ttk.Frame(preset_card, style="Card.TFrame")
        preset_row.pack(fill=tk.X, pady=(0, 8))

        r_8 = ttk.Radiobutton(
            preset_row,
            text="20 MB · Free",
            value="20",
            variable=self.preset_var,
            command=self.on_preset_changed
        )
        r_8.pack(side=tk.LEFT, padx=(0, 14))

        r_20 = ttk.Radiobutton(
            preset_row,
            text="50 MB · Basic",
            value="50",
            variable=self.preset_var,
            command=self.on_preset_changed
        )
        r_20.pack(side=tk.LEFT, padx=(0, 14))

        r_50 = ttk.Radiobutton(
            preset_row,
            text="1 GB · Nitro",
            value="1000",
            variable=self.preset_var,
            command=self.on_preset_changed
        )
        r_50.pack(side=tk.LEFT, padx=(0, 14))

        r_custom = ttk.Radiobutton(
            preset_row,
            text="Custom",
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
        self.custom_size_var.trace_add("write", lambda *args: self.on_custom_size_changed())

        lbl_mb = ttk.Label(preset_row, text="MB", style="Card.TLabel")
        lbl_mb.pack(side=tk.LEFT)

        # -------------------------------------------------------------
        # Section 3: Compression Settings (Options)
        # -------------------------------------------------------------
        opts_card = ttk.Frame(container, style="Card.TFrame", padding=14)
        self.opts_card = opts_card
        self.btn_advanced = ttk.Button(container, text="Advanced", command=self.toggle_advanced)
        self.btn_advanced.pack(anchor="w", pady=(0, 8))

        lbl_s3 = ttk.Label(opts_card, text="Options", style="Section.TLabel")
        lbl_s3.pack(anchor="w", pady=(0, 8))

        opts_row = ttk.Frame(opts_card, style="Card.TFrame")
        opts_row.pack(fill=tk.X)

        # Dynamic Bitrate Preview Box
        self.preview_box = ttk.Frame(opts_card, style="Card.TFrame")


        self.lbl_preview = ttk.Label(
            self.preview_box,
            text="Target Bitrate Preview: Select a video to calculate optimal bitrates.",
            foreground=COLORS["accent"],
            font=(FONT_FAMILY, 9, "bold"),
            background=COLORS["card"]
        )
        self.lbl_preview.pack(anchor="w")

        self.preview_box.pack(fill=tk.X, pady=(6, 0))

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

        lbl_s4 = ttk.Label(out_card, text="Save beside original", style="Section.TLabel")
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
        self.entry_output.config(state="readonly")
        self.entry_output.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))

        btn_browse_out = ttk.Button(
            out_row,
            text="Change location",
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
            text="Compress",
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
            style="Action.TButton",
            command=self.open_output_folder
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

        # Completed video: click to open, drag to share.
        self.lbl_result = ttk.Button(btn_row, text="▶ Video", style="Action.TButton", cursor="hand2")
        self.btn_copy = ttk.Button(btn_row, text="Copy", style="Action.TButton", command=self.copy_result)
        self.result_press = None
        self.result_dragging = False
        self.lbl_result.bind("<ButtonPress-1>", self.press_result, add="+")
        self.lbl_result.bind("<ButtonRelease-1>", self.release_result, add="+")
        self.lbl_result.bind("<Return>", lambda event: self.play_output_video())
        self.lbl_result.bind("<space>", lambda event: self.play_output_video())
        if HAS_DND:
            self.lbl_result.drag_source_register(1, DND_FILES)
            self.lbl_result.dnd_bind("<<DragInitCmd>>", self.drag_result)

        # -------------------------------------------------------------
        # Section 6: Collapsible FFmpeg Log Drawer
        # -------------------------------------------------------------
        log_header = ttk.Frame(container)
        log_header.pack(in_=opts_card, fill=tk.X, pady=(4, 4))

        self.btn_toggle_logs = ttk.Button(
            log_header,
            text="Show details",
            style="Secondary.TButton",
            command=self.toggle_logs
        )
        self.btn_toggle_logs.pack(side=tk.LEFT)

        self.log_container = ttk.Frame(opts_card)

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
                text="Ready",
                fg=COLORS["success"],
                bg=COLORS["input_bg"]
            )
            self.btn_locate_ffmpeg.pack_forget()
        else:
            self.ffmpeg_status_lbl.config(
                text="Setup needed",
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
        if self.is_compressing:
            return
        paths = self.root.tk.splitlist(event.data)
        if len(paths) == 1 and os.path.isfile(paths[0]):
            self.set_input_file(paths[0])

    def toggle_advanced(self):
        if self.opts_card.winfo_manager():
            self.opts_card.pack_forget()
        else:
            self.opts_card.pack(fill=tk.X, before=self.btn_advanced, pady=(0, 8))

    def press_result(self, event):
        self.result_press = (event.x_root, event.y_root)
        self.result_dragging = False
        self.lbl_result.focus_set()

    def release_result(self, event):
        if self.result_press and not self.result_dragging:
            x, y = self.result_press
            if abs(event.x_root - x) < 5 and abs(event.y_root - y) < 5:
                self.play_output_video()
        self.result_press = None

    def drag_result(self, event):
        if self.result_path and os.path.isfile(self.result_path) and not self.is_compressing:
            self.result_dragging = True
            return (COPY, DND_FILES, (os.path.abspath(self.result_path),))
        return "break"

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
        if self.is_compressing:
            return
        self.custom_output = False
        self.video_info = None
        self.result_path = None
        self.lbl_result.config(text="")
        self.btn_open_folder.pack_forget()
        self.lbl_result.pack_forget()
        self.btn_copy.pack_forget()
        self.input_file_var.set(path)
        self.lbl_status.config(text="Analyzing video...", foreground=COLORS["accent"])
        self.root.update_idletasks()

        threading.Thread(target=self._analyze_video_worker, args=(path,), daemon=True).start()

    def _analyze_video_worker(self, path: str):
        try:
            info = get_video_info(path)
            self.root.after(0, self._on_video_analyzed, info, path)
        except Exception as e:
            self.root.after(0, lambda err=str(e): messagebox.showerror("Cannot open video", err))
            self.root.after(0, lambda: self.lbl_status.config(text="Ready to compress", foreground=COLORS["text"]))

    def _on_video_analyzed(self, info: Dict[str, Any], path=None):
        if path and path != self.input_file_var.get():
            return
        self.video_info = info
        details = f"{info['filename']} · {info['filesize_str']} · {info['duration_str']}"
        self.lbl_info_details.config(text=details, style="Card.TLabel")
        self.lbl_status.config(text="Video loaded successfully.", foreground=COLORS["text"])

        # Update auto output file path
        self.update_default_output_path()
        self.update_bitrate_preview()

    def get_selected_target_mb(self) -> float:
        choice = self.preset_var.get()
        if choice in ("20", "50", "1000"):
            return float(choice)
        try:
            val = float(self.custom_size_var.get().strip())
            return val if math.isfinite(val) and val > 0 else 0
        except ValueError:
            return 0.0

    def on_custom_size_changed(self):
        if hasattr(self, "lbl_preview"):
            self.update_default_output_path()
            self.update_bitrate_preview()

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
        if not in_path or self.custom_output:
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

        if self.video_info["filesize"] <= target_mb * 1_000_000:
            self.lbl_status.config(text="Already fits", foreground=COLORS["success"])
        elif v_kbps < 500:
            self.lbl_status.config(text="Low quality: try a larger size or shorter clip", foreground=COLORS["warning"])
        else:
            self.lbl_status.config(text="Ready", foreground=COLORS["text"])

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
            self.custom_output = True
            self.output_file_var.set(file_path)

    def toggle_logs(self):
        if self.show_logs_var.get():
            self.log_container.pack_forget()
            self.btn_toggle_logs.config(text="Show details")
            self.show_logs_var.set(False)
        else:
            self.log_container.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
            self.btn_toggle_logs.config(text="Hide details")
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
        if self.is_compressing:
            return
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

        output_path = unique_output_path(output_path)
        self.output_file_var.set(output_path)

        # UI state during compression
        self.is_compressing = True
        self.result_path = None
        self.btn_compress.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.btn_open_folder.pack_forget()
        self.lbl_result.pack_forget()
        self.btn_copy.pack_forget()
        self.lbl_result.config(text="")
        self.progress_bar["value"] = 0
        self.lbl_status.config(text="Preparing video...", foreground=COLORS["accent"])
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
            self.lbl_status.config(text="Cancelling...", foreground=COLORS["danger"])
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

                status_msg = "Analyzing video..." if pass_num == 1 else "Compressing video..."
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

        self.result_path = res["output_file"]
        out_size_str = res["compressed_size_str"]
        orig_size_str = res["original_size_str"]
        reduction = res["reduction_percent"]
        elapsed = res["elapsed_str"]
        under_target = res["under_target"]

        status_text = "Ready to share" if under_target else "Over size limit"
        color = COLORS["success"] if under_target else COLORS["warning"]
        self.lbl_status.config(text=status_text, foreground=color)
        self.lbl_result.config(text="▶ Video", cursor="hand2")
        self.lbl_result.pack(side=tk.RIGHT, padx=(10, 0))
        if os.name == "nt":
            self.btn_copy.config(text="Copy")
            self.btn_copy.pack(side=tk.RIGHT, padx=(10, 0))

        # Show action buttons
        self.btn_open_folder.pack(side=tk.LEFT, padx=(10, 0))


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
            self.lbl_result.config(text="▶ Video")
            messagebox.showerror("Compression Error", f"Video compression failed:\n\n{err_msg}")

    def copy_result(self):
        if not self.result_path or self.is_compressing:
            return
        try:
            copy_file(self.result_path, self.root.winfo_id())
            self.btn_copy.config(text="Copied")
        except OSError as error:
            messagebox.showerror("Cannot copy video", str(error))

    def open_output_folder(self):
        out_path = self.result_path
        if out_path and os.path.exists(out_path):
            folder = os.path.dirname(os.path.abspath(out_path))
            if os.name == "nt":
                subprocess.Popen(f'explorer /select,"{os.path.abspath(out_path)}"')
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", out_path])
            else:
                subprocess.Popen(["xdg-open", folder])

    def play_output_video(self):
        out_path = self.result_path
        if not self.is_compressing and out_path and os.path.isfile(out_path):
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

