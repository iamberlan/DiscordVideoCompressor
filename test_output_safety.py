"""Safety checks for published compression results."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from compressor import VideoCompressor


class TestOutputSafety(unittest.TestCase):
    def run_encode(self, sizes, existing=False, cancel=False):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'original.mp4'
            source.write_bytes(b'original')
            destination = Path(directory) / 'shared.mp4'
            if existing:
                destination.write_bytes(b'existing')
            engine = VideoCompressor()
            attempts = []

            def encode(*args):
                staging = Path(args[1])
                size = sizes[len(attempts)]
                attempts.append(args[6])
                staging.write_bytes(b'x' * size)
                if cancel:
                    engine.cancel()
                return {'compressed_size': size, 'output_file': str(staging)}

            with patch.object(engine, '_compress_once', side_effect=encode):
                if cancel or min(sizes) > 1_000_000:
                    with self.assertRaises((RuntimeError, ValueError)):
                        engine.compress(str(source), str(destination), 1)
                    self.assertFalse(destination.exists())
                else:
                    result = engine.compress(str(source), str(destination), 1)
                    self.assertLessEqual(os.path.getsize(result['output_file']), 1_000_000)
                    if existing:
                        self.assertNotEqual(str(destination), result['output_file'])
                        self.assertEqual(destination.read_bytes(), b'existing')
            self.assertEqual(source.read_bytes(), b'original')
            self.assertFalse(any(p.name.startswith('.dvc_') for p in Path(directory).iterdir()))
            return attempts

    def test_retry_and_preserve_existing(self):
        attempts = self.run_encode([1_100_000, 900_000], existing=True)
        self.assertEqual(len(attempts), 2)
        self.assertLess(attempts[1], attempts[0])

    def test_impossible_size_not_published(self):
        self.assertEqual(len(self.run_encode([1_100_000] * 3)), 3)

    def test_cancel_not_published(self):
        self.run_encode([900_000], cancel=True)
