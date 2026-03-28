# tests/test_capture_frames.py
import json
import subprocess
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from capture_frames import extract_video_id, format_timestamp, build_ffmpeg_cmd


class TestExtractVideoId(unittest.TestCase):
    def test_full_url(self):
        self.assertEqual(extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_short_url(self):
        self.assertEqual(extract_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_bare_id(self):
        self.assertEqual(extract_video_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")


class TestFormatTimestamp(unittest.TestCase):
    def test_seconds_only(self):
        self.assertEqual(format_timestamp(45), "00:00:45")

    def test_minutes_and_seconds(self):
        self.assertEqual(format_timestamp(261), "00:04:21")

    def test_hours(self):
        self.assertEqual(format_timestamp(3661), "01:01:01")


class TestBuildFfmpegCmd(unittest.TestCase):
    def test_command_structure(self):
        cmd = build_ffmpeg_cmd("https://example.com/stream", 261, "/tmp/out.png")
        self.assertIn("ffmpeg", cmd[0])
        self.assertIn("-ss", cmd)
        self.assertIn("00:04:21", cmd)
        self.assertEqual(cmd[-1], "/tmp/out.png")


if __name__ == "__main__":
    unittest.main()
