"""
test_compressor.py - Unit tests for bitrate calculation and video compression helper functions.
"""

import unittest
import os
from compressor import (
    format_bytes,
    format_seconds,
    calculate_bitrates,
    get_recommended_scale
)
from ffmpeg_finder import load_config, save_config, CONFIG_FILE


class TestCompressorCalculations(unittest.TestCase):

    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")
        self.assertEqual(format_bytes(8 * 1024 * 1024), "8.00 MB")

    def test_format_seconds(self):
        self.assertEqual(format_seconds(0), "00:00")
        self.assertEqual(format_seconds(45), "00:45")
        self.assertEqual(format_seconds(75), "01:15")
        self.assertEqual(format_seconds(3665), "01:01:05")

    def test_calculate_bitrates_8mb_preset(self):
        # 60s video targeting 8MB
        res = calculate_bitrates(target_size_mb=8.0, duration_sec=60.0, has_audio=True, safety_margin=0.96)
        
        self.assertGreater(res["video_bitrate_kbps"], 0)
        self.assertGreater(res["audio_bitrate_kbps"], 0)
        
        total_kbps = res["video_bitrate_kbps"] + res["audio_bitrate_kbps"]
        # Total bits for 60s:
        total_bytes = (total_kbps * 1000 * 60) / 8
        target_limit_bytes = 8.0 * 1024 * 1024
        
        # Must strictly be below 8MB limit
        self.assertLess(total_bytes, target_limit_bytes)
        self.assertLessEqual(res["estimated_size_mb"], 8.0)

    def test_calculate_bitrates_20mb_preset(self):
        res = calculate_bitrates(target_size_mb=20.0, duration_sec=120.0, has_audio=True)
        self.assertLess(res["estimated_size_mb"], 20.0)

    def test_calculate_bitrates_50mb_preset(self):
        res = calculate_bitrates(target_size_mb=50.0, duration_sec=180.0, has_audio=True)
        self.assertLess(res["estimated_size_mb"], 50.0)

    def test_calculate_bitrates_no_audio(self):
        res = calculate_bitrates(target_size_mb=8.0, duration_sec=30.0, has_audio=False)
        self.assertEqual(res["audio_bitrate_kbps"], 0)
        self.assertGreater(res["video_bitrate_kbps"], 0)

    def test_calculate_bitrates_short_video(self):
        # 5 second video
        res = calculate_bitrates(target_size_mb=8.0, duration_sec=5.0, has_audio=True)
        self.assertGreater(res["video_bitrate_kbps"], 500)
        self.assertLess(res["estimated_size_mb"], 8.0)

    def test_recommended_scale(self):
        # Very low bitrate should scale to 360p or 480p
        self.assertEqual(get_recommended_scale(150, 1080), 360)
        self.assertEqual(get_recommended_scale(400, 1080), 480)
        self.assertEqual(get_recommended_scale(900, 1080), 720)
        self.assertEqual(get_recommended_scale(3000, 1080), 1080)
        
        # Don't upscale
        self.assertEqual(get_recommended_scale(3000, 720), 720)


class TestConfig(unittest.TestCase):
    def test_save_and_load_config(self):
        test_data = {"test_key": "test_val"}
        save_config(test_data)
        loaded = load_config()
        self.assertEqual(loaded.get("test_key"), "test_val")
        if CONFIG_FILE.exists():
            os.remove(CONFIG_FILE)


if __name__ == "__main__":
    unittest.main()

