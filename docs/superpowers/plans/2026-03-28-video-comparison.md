# Video Comparison Feature — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-video comparison with an interactive HTML dashboard, frame screenshots via ffmpeg, session history, and an agentic chat widget.

**Architecture:** Two-layer design — Python scripts handle data fetching, transcript extraction, and frame capture, outputting `comparison_data.json`. A self-contained HTML viewer renders the interactive dashboard. In Claude Code mode, a Flask server adds on-demand screenshot and chat API endpoints.

**Tech Stack:** Python 3.9+, yt-dlp (existing), ffmpeg (new system dep), Flask (new pip dep), vanilla HTML/CSS/JS (no build step)

---

### Task 1: capture_frames.py — ffmpeg frame extraction

**Files:**
- Create: `scripts/capture_frames.py`
- Create: `tests/test_capture_frames.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python -m pytest tests/test_capture_frames.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'capture_frames'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/capture_frames.py
#!/usr/bin/env python3
"""Extract video frames at specific timestamps using yt-dlp + ffmpeg."""
import argparse
import base64
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

DATA_DIR = Path(os.environ.get("CLAUDE_PLUGIN_DATA", Path(__file__).parent.parent / "data"))


def get_env():
    """Inherit current environment (including HTTPS_PROXY and other proxy variables)."""
    return {**os.environ}


def extract_video_id(url_or_id):
    """Extract YouTube video ID from a URL or return the ID if already bare."""
    patterns = [
        r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS format for ffmpeg."""
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_stream_url(video_id):
    """Get the direct stream URL for a YouTube video using yt-dlp."""
    cmd = [
        "yt-dlp",
        "--get-url",
        "--format", "best[height<=720]",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=get_env())
    urls = result.stdout.strip().split("\n")
    return urls[0] if urls else None


def build_ffmpeg_cmd(stream_url, timestamp_seconds, output_path):
    """Build the ffmpeg command to extract a single frame."""
    ts = format_timestamp(timestamp_seconds)
    return [
        "ffmpeg",
        "-ss", ts,
        "-i", stream_url,
        "-frames:v", "1",
        "-q:v", "2",
        "-y",
        str(output_path),
    ]


def capture_frame(video_id, timestamp_seconds, output_dir=None):
    """
    Capture a single frame from a YouTube video at the given timestamp.
    Returns the frame as a base64-encoded PNG string, or None on failure.
    """
    output_dir = Path(output_dir) if output_dir else DATA_DIR / "frames"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_id}_{int(timestamp_seconds)}.png"

    # If already captured, return cached
    if output_path.exists():
        return base64.b64encode(output_path.read_bytes()).decode("utf-8")

    print(f"  Getting stream URL for {video_id}...", flush=True)
    stream_url = get_stream_url(video_id)
    if not stream_url:
        print(f"  Failed to get stream URL for {video_id}")
        return None

    print(f"  Capturing frame at {format_timestamp(timestamp_seconds)}...", flush=True)
    cmd = build_ffmpeg_cmd(stream_url, timestamp_seconds, output_path)

    try:
        subprocess.run(cmd, capture_output=True, timeout=30, env=get_env())
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  ffmpeg error: {e}")
        return None

    if output_path.exists() and output_path.stat().st_size > 0:
        return base64.b64encode(output_path.read_bytes()).decode("utf-8")
    return None


def capture_frames_batch(video_id, timestamps, output_dir=None):
    """Capture multiple frames for a single video. Returns list of {timestamp, base64}."""
    results = []
    for ts in timestamps:
        b64 = capture_frame(video_id, ts, output_dir)
        results.append({"timestamp": ts, "base64": b64})
    return results


def main():
    parser = argparse.ArgumentParser(description="Capture video frames at specific timestamps")
    parser.add_argument("--video-id", required=True, help="YouTube video ID or URL")
    parser.add_argument("--timestamps", required=True, help="Comma-separated timestamps in seconds (e.g., 60,120,300)")
    parser.add_argument("--output-dir", help="Directory to save frames")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    video_id = extract_video_id(args.video_id)
    timestamps = [int(t.strip()) for t in args.timestamps.split(",")]

    results = capture_frames_batch(video_id, timestamps, args.output_dir)

    if args.json:
        output = []
        for r in results:
            output.append({
                "video_id": video_id,
                "timestamp": r["timestamp"],
                "has_frame": r["base64"] is not None,
            })
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            status = "OK" if r["base64"] else "FAILED"
            print(f"  [{format_timestamp(r['timestamp'])}] {status}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python -m pytest tests/test_capture_frames.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/capture_frames.py tests/test_capture_frames.py
git commit -m "feat: add capture_frames.py for ffmpeg frame extraction"
```

---

### Task 2: compare_videos.py — orchestrator script

**Files:**
- Create: `scripts/compare_videos.py`
- Create: `tests/test_compare_videos.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compare_videos.py
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from compare_videos import parse_urls, generate_session_id, build_session_dir_name


class TestParseUrls(unittest.TestCase):
    def test_full_urls(self):
        urls = ["https://www.youtube.com/watch?v=abc123def45", "https://youtu.be/xyz789ghi01"]
        result = parse_urls(urls)
        self.assertEqual(result, ["abc123def45", "xyz789ghi01"])

    def test_bare_ids(self):
        result = parse_urls(["abc123def45", "xyz789ghi01"])
        self.assertEqual(result, ["abc123def45", "xyz789ghi01"])

    def test_mixed(self):
        result = parse_urls(["https://www.youtube.com/watch?v=abc123def45", "xyz789ghi01"])
        self.assertEqual(result, ["abc123def45", "xyz789ghi01"])


class TestGenerateSessionId(unittest.TestCase):
    def test_returns_string(self):
        sid = generate_session_id()
        self.assertIsInstance(sid, str)
        self.assertGreater(len(sid), 8)


class TestBuildSessionDirName(unittest.TestCase):
    def test_format(self):
        name = build_session_dir_name("GPT-5 Announcements!")
        self.assertTrue(name.startswith("20"))
        self.assertIn("gpt-5-announcements", name)

    def test_sanitizes_special_chars(self):
        name = build_session_dir_name("What's New? (2026)")
        self.assertNotIn("?", name)
        self.assertNotIn("'", name)
        self.assertNotIn("(", name)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python -m pytest tests/test_compare_videos.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# scripts/compare_videos.py
#!/usr/bin/env python3
"""Orchestrator: fetch metadata + transcripts for multiple videos, output comparison_data.json."""
import argparse
import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from capture_frames import extract_video_id, capture_frame
from get_transcript import get_transcript_ytdlp, format_transcript

DATA_DIR = Path(os.environ.get("CLAUDE_PLUGIN_DATA", Path(__file__).parent.parent / "data"))
SESSIONS_DIR = DATA_DIR / "sessions"


def get_env():
    """Inherit current environment."""
    return {**os.environ}


def parse_urls(urls):
    """Extract video IDs from a list of URLs or bare IDs."""
    return [extract_video_id(u) for u in urls]


def generate_session_id():
    """Generate a unique session ID."""
    return uuid.uuid4().hex[:12]


def build_session_dir_name(title):
    """Build a filesystem-safe session directory name from a title."""
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    return f"{date_prefix}_{slug}"


def fetch_video_metadata(video_id):
    """Fetch full metadata for a single video using yt-dlp."""
    cmd = ["yt-dlp", "--dump-json", "--no-download", f"https://www.youtube.com/watch?v={video_id}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=get_env())
        info = json.loads(result.stdout)
        return {
            "id": video_id,
            "title": info.get("title", "Unknown"),
            "channel": info.get("channel", "Unknown"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration": info.get("duration_string", ""),
            "upload_date": info.get("upload_date", ""),
            "view_count": info.get("view_count", 0),
        }
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  Error fetching metadata for {video_id}: {e}")
        return {
            "id": video_id,
            "title": "Unknown",
            "channel": "Unknown",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration": "",
            "upload_date": "",
            "view_count": 0,
        }


def fetch_thumbnail_base64(video_id):
    """Download thumbnail and return as base64 string."""
    import base64
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp", "--write-thumbnail", "--skip-download",
            "--convert-thumbnails", "png",
            "-o", os.path.join(tmpdir, "thumb"),
            f"https://www.youtube.com/watch?v={video_id}",
        ]
        subprocess.run(cmd, capture_output=True, timeout=30, env=get_env())
        for f in Path(tmpdir).glob("thumb*.png"):
            return base64.b64encode(f.read_bytes()).decode("utf-8")
    return None


def process_video(video_id):
    """Fetch metadata, transcript, and thumbnail for a single video."""
    print(f"\nProcessing: {video_id}", flush=True)

    print("  Fetching metadata...", flush=True)
    metadata = fetch_video_metadata(video_id)

    print(f"  Title: {metadata['title']}", flush=True)
    print(f"  Channel: {metadata['channel']}", flush=True)

    print("  Fetching thumbnail...", flush=True)
    metadata["thumbnail_base64"] = fetch_thumbnail_base64(video_id)

    print("  Fetching transcript...", flush=True)
    transcript, lang = get_transcript_ytdlp(video_id)
    metadata["transcript"] = transcript or []
    metadata["transcript_lang"] = lang

    if transcript:
        formatted = format_transcript(transcript)
        transcript_file = DATA_DIR / f"transcript_{video_id}.txt"
        transcript_file.parent.mkdir(parents=True, exist_ok=True)
        transcript_file.write_text(formatted, encoding="utf-8")
        print(f"  Transcript: {len(transcript)} entries ({lang})", flush=True)
    else:
        print("  Transcript: not available", flush=True)

    return metadata


def build_comparison_data(videos, title="Video Comparison"):
    """
    Build the comparison_data.json structure.
    Note: analysis.topics, analysis.disagreements, analysis.key_moments, and
    analysis.unified_summary are PLACEHOLDER fields — Claude fills them in after
    reading the transcripts. This script only populates the video data.
    """
    session_id = generate_session_id()
    return {
        "session": {
            "id": session_id,
            "title": title,
            "created_at": datetime.now().isoformat(),
            "video_count": len(videos),
        },
        "videos": videos,
        "analysis": {
            "unified_summary": "",
            "topics": [],
            "disagreements": [],
            "key_moments": [],
        },
        "stats": {
            "total_videos": len(videos),
            "common_topics": 0,
            "disagreements": 0,
            "key_moments": 0,
        },
    }


def save_session(comparison_data):
    """Save session to the sessions directory and update the index."""
    session = comparison_data["session"]
    dir_name = build_session_dir_name(session["title"])
    session_dir = SESSIONS_DIR / dir_name
    session_dir.mkdir(parents=True, exist_ok=True)

    data_file = session_dir / "comparison_data.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(comparison_data, f, indent=2, ensure_ascii=False)

    # Update index
    index_file = SESSIONS_DIR / "index.json"
    index = []
    if index_file.exists():
        with open(index_file) as f:
            index = json.load(f)

    index.insert(0, {
        "id": session["id"],
        "title": session["title"],
        "created_at": session["created_at"],
        "video_count": session["video_count"],
        "dir_name": dir_name,
    })

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\nSession saved to: {data_file}")
    return data_file


def main():
    parser = argparse.ArgumentParser(description="Compare multiple YouTube videos")
    parser.add_argument("--urls", nargs="+", required=True, help="YouTube video URLs or IDs")
    parser.add_argument("--title", default=None, help="Session title (auto-generated if omitted)")
    args = parser.parse_args()

    video_ids = parse_urls(args.urls)
    print(f"Comparing {len(video_ids)} videos...\n", flush=True)

    videos = []
    for vid in video_ids:
        video_data = process_video(vid)
        videos.append(video_data)

    title = args.title or f"Comparison: {', '.join(v['channel'] for v in videos[:3])}"
    if len(videos) > 3:
        title += f" +{len(videos) - 3}"

    comparison_data = build_comparison_data(videos, title)
    output_path = save_session(comparison_data)

    print(f"\nDone! {len(videos)} videos processed.")
    print(f"Output: {output_path}")
    print("\nClaude: read the comparison_data.json file and fill in the analysis section")
    print("(unified_summary, topics, disagreements, key_moments)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python -m pytest tests/test_compare_videos.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/compare_videos.py tests/test_compare_videos.py
git commit -m "feat: add compare_videos.py orchestrator for multi-video comparison"
```

---

### Task 3: Session persistence and index management

**Files:**
- Create: `tests/test_session_persistence.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_session_persistence.py
import json
import tempfile
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

# Patch DATA_DIR before importing
import compare_videos


class TestSessionPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        compare_videos.SESSIONS_DIR = os.path.join(self.tmpdir, "sessions")

    def test_save_session_creates_files(self):
        data = {
            "session": {
                "id": "test123",
                "title": "Test Session",
                "created_at": "2026-03-28T14:00:00",
                "video_count": 2,
            },
            "videos": [],
            "analysis": {"unified_summary": "", "topics": [], "disagreements": [], "key_moments": []},
            "stats": {"total_videos": 2, "common_topics": 0, "disagreements": 0, "key_moments": 0},
        }
        from pathlib import Path
        compare_videos.SESSIONS_DIR = Path(self.tmpdir) / "sessions"
        output_path = compare_videos.save_session(data)

        self.assertTrue(output_path.exists())
        index_path = Path(self.tmpdir) / "sessions" / "index.json"
        self.assertTrue(index_path.exists())

        with open(index_path) as f:
            index = json.load(f)
        self.assertEqual(len(index), 1)
        self.assertEqual(index[0]["id"], "test123")

    def test_index_prepends_new_sessions(self):
        from pathlib import Path
        compare_videos.SESSIONS_DIR = Path(self.tmpdir) / "sessions"

        for i, title in enumerate(["First", "Second"]):
            data = {
                "session": {"id": f"sess{i}", "title": title, "created_at": "2026-03-28T14:00:00", "video_count": 1},
                "videos": [],
                "analysis": {"unified_summary": "", "topics": [], "disagreements": [], "key_moments": []},
                "stats": {"total_videos": 1, "common_topics": 0, "disagreements": 0, "key_moments": 0},
            }
            compare_videos.save_session(data)

        index_path = Path(self.tmpdir) / "sessions" / "index.json"
        with open(index_path) as f:
            index = json.load(f)
        self.assertEqual(len(index), 2)
        self.assertEqual(index[0]["title"], "Second")  # newest first


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python -m pytest tests/test_session_persistence.py -v`
Expected: All 2 tests PASS (implementation already in compare_videos.py)

- [ ] **Step 3: Commit**

```bash
git add tests/test_session_persistence.py
git commit -m "test: add session persistence tests"
```

---

### Task 4: compare_server.py — Flask API server

**Files:**
- Create: `scripts/compare_server.py`
- Create: `tests/test_compare_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compare_server.py
import json
import tempfile
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestServerRoutes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ["CLAUDE_PLUGIN_DATA"] = self.tmpdir

        # Create a test session
        sessions_dir = os.path.join(self.tmpdir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        session_dir = os.path.join(sessions_dir, "2026-03-28_test-session")
        os.makedirs(session_dir, exist_ok=True)

        self.test_data = {
            "session": {"id": "test123", "title": "Test Session", "created_at": "2026-03-28T14:00:00", "video_count": 2},
            "videos": [{"id": "vid1", "title": "Video 1", "transcript": []}],
            "analysis": {"unified_summary": "Test summary", "topics": [], "disagreements": [], "key_moments": []},
            "stats": {"total_videos": 2, "common_topics": 0, "disagreements": 0, "key_moments": 0},
        }
        with open(os.path.join(session_dir, "comparison_data.json"), "w") as f:
            json.dump(self.test_data, f)

        index = [{"id": "test123", "title": "Test Session", "created_at": "2026-03-28T14:00:00", "video_count": 2, "dir_name": "2026-03-28_test-session"}]
        with open(os.path.join(sessions_dir, "index.json"), "w") as f:
            json.dump(index, f)

        from compare_server import create_app
        self.app = create_app(self.tmpdir)
        self.client = self.app.test_client()

    def test_get_sessions(self):
        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "test123")

    def test_get_session_by_id(self):
        response = self.client.get("/api/session/test123")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["session"]["title"], "Test Session")

    def test_get_session_not_found(self):
        response = self.client.get("/api/session/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_index_serves_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        if "CLAUDE_PLUGIN_DATA" in os.environ:
            del os.environ["CLAUDE_PLUGIN_DATA"]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python -m pytest tests/test_compare_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'compare_server'`

- [ ] **Step 3: Install Flask**

Run: `pip install flask`

- [ ] **Step 4: Write the implementation**

```python
# scripts/compare_server.py
#!/usr/bin/env python3
"""Flask server for the video comparison viewer with on-demand screenshot API."""
import argparse
import json
import os
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_file, abort

from capture_frames import capture_frame, extract_video_id


def create_app(data_dir=None):
    """Create and configure the Flask app."""
    data_dir = Path(data_dir or os.environ.get("CLAUDE_PLUGIN_DATA", Path(__file__).parent.parent / "data"))
    sessions_dir = data_dir / "sessions"
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))
    viewer_path = plugin_root / "viewer" / "viewer.html"

    app = Flask(__name__)

    @app.route("/")
    def index():
        if viewer_path.exists():
            return send_file(viewer_path)
        return "<h1>ytmp4 Video Comparison</h1><p>viewer.html not found</p>", 200

    @app.route("/api/sessions")
    def get_sessions():
        index_file = sessions_dir / "index.json"
        if not index_file.exists():
            return jsonify([])
        with open(index_file) as f:
            return jsonify(json.load(f))

    @app.route("/api/session/<session_id>")
    def get_session(session_id):
        index_file = sessions_dir / "index.json"
        if not index_file.exists():
            abort(404)

        with open(index_file) as f:
            index = json.load(f)

        dir_name = None
        for entry in index:
            if entry["id"] == session_id:
                dir_name = entry["dir_name"]
                break

        if not dir_name:
            abort(404)

        data_file = sessions_dir / dir_name / "comparison_data.json"
        if not data_file.exists():
            abort(404)

        with open(data_file) as f:
            return jsonify(json.load(f))

    @app.route("/api/screenshot", methods=["POST"])
    def take_screenshot():
        body = request.get_json()
        if not body or "video_id" not in body or "timestamp" not in body:
            return jsonify({"error": "video_id and timestamp required"}), 400

        video_id = extract_video_id(body["video_id"])
        timestamp = int(body["timestamp"])

        frames_dir = data_dir / "frames"
        b64 = capture_frame(video_id, timestamp, frames_dir)

        if b64:
            return jsonify({"video_id": video_id, "timestamp": timestamp, "screenshot_base64": b64})
        return jsonify({"error": "Failed to capture frame"}), 500

    @app.route("/api/chat", methods=["POST"])
    def chat():
        # Chat endpoint placeholder — in production, this routes to Claude API
        body = request.get_json()
        return jsonify({
            "response": "Chat endpoint ready. Connect to Claude API for full functionality.",
            "session_id": body.get("session_id"),
        })

    return app


def main():
    parser = argparse.ArgumentParser(description="Start the video comparison viewer server")
    parser.add_argument("--port", type=int, default=5123, help="Port to serve on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser automatically")
    parser.add_argument("--session", help="Session ID to open directly")
    args = parser.parse_args()

    app = create_app()

    url = f"http://{args.host}:{args.port}"
    if args.session:
        url += f"?session={args.session}"

    if not args.no_open:
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"Serving viewer at {url}", flush=True)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python -m pytest tests/test_compare_server.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/compare_server.py tests/test_compare_server.py
git commit -m "feat: add Flask server with session, screenshot, and chat API endpoints"
```

---

### Task 5: viewer.html — Dashboard tab

**Files:**
- Create: `viewer/viewer.html`

This is a large self-contained HTML file. It will be built incrementally across Tasks 5-8. This task implements the shell layout (nav, history panel, stats row, unified summary, topic map, video cards, key moments grid) and the Dashboard tab.

- [ ] **Step 1: Create the viewer directory**

Run: `mkdir -p c:/Users/digit/Developer/ytmp4-ai-digest/viewer`

- [ ] **Step 2: Write the viewer HTML with Dashboard tab**

Create `viewer/viewer.html` with the full shell: dark theme (#0f1117 background), nav bar with ytmp4 branding and tab switcher, collapsible history panel (expanded: 260px with date-grouped sessions, search; collapsed: 48px icon strip with tooltips), stats cards, unified summary, topic map bars, video cards, and key moments screenshot grid. The file loads data from `/api/sessions` and `/api/session/:id` when served by Flask, or from an inline `window.__COMPARISON_DATA__` variable when used as a static artifact.

The complete HTML file is too large to inline here. Write it with these sections:
- CSS: dark theme variables, panel animations, responsive grid, tooltip styles
- HTML structure: `#app` wrapper > `#history-panel` + `#main-content` > `#nav-bar` + `#tab-content`
- JS: `loadSession(id)`, `renderDashboard(data)`, `togglePanel()`, tab switching, API fetch helpers, tooltip hover handlers

- [ ] **Step 3: Test manually**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python scripts/compare_server.py --port 5123 --no-open`
Then open `http://localhost:5123` in a browser. Verify the shell renders with placeholder content.

- [ ] **Step 4: Commit**

```bash
git add viewer/viewer.html
git commit -m "feat: add viewer.html shell with Dashboard tab"
```

---

### Task 6: viewer.html — By Topic tab

**Files:**
- Modify: `viewer/viewer.html`

- [ ] **Step 1: Add the By Topic rendering function**

Add `renderByTopic(data)` to the JS section of `viewer/viewer.html`. This function:
- Reads `data.analysis.topics` array
- Sorts topics by `video_coverage.length` descending
- Renders each topic as a collapsible accordion section with:
  - Colored indicator bar (cycle through: `#60a5fa`, `#34d399`, `#fbbf24`, `#f472b6`, `#a78bfa`)
  - Topic name, video coverage count ("3 of 4 videos"), consensus badge
  - Expanded: per-video entries with screenshot thumbnail (from `entry.screenshot_base64`), timestamp link, creator name, quote text
- Clicking a topic header toggles its expanded/collapsed state
- First topic starts expanded, rest collapsed

- [ ] **Step 2: Wire up the tab switcher**

In the tab click handler, when "By Topic" is clicked, call `renderByTopic(currentSessionData)` and inject into `#tab-content`.

- [ ] **Step 3: Test manually**

Create a test `comparison_data.json` with sample topics and verify the accordion renders correctly.

- [ ] **Step 4: Commit**

```bash
git add viewer/viewer.html
git commit -m "feat: add By Topic accordion view to viewer"
```

---

### Task 7: viewer.html — By Video tab

**Files:**
- Modify: `viewer/viewer.html`

- [ ] **Step 1: Add the By Video rendering function**

Add `renderByVideo(data)` to the JS section. This function:
- Renders a split layout: 200px video selector sidebar + detail panel
- Sidebar shows each video as a card with thumbnail, title, channel, duration
- Active video highlighted with blue left border
- Detail panel shows:
  - Video header: large thumbnail, title, channel, date, views, per-video summary
  - Topic tags: colored pills for each topic this video appears in
  - Timeline bar: horizontal bar with colored dots at key moment timestamps, "Click anywhere to capture frame" hint
  - Moment entries: screenshot thumbnail, timestamp, label, description
- Clicking a sidebar card calls `renderVideoDetail(videoId)` to update the right panel
- Clicking the timeline bar triggers a POST to `/api/screenshot` with `{video_id, timestamp}` and appends the new screenshot to the moments list

- [ ] **Step 2: Wire up the tab switcher**

When "By Video" is clicked, call `renderByVideo(currentSessionData)` and inject into `#tab-content`. First video in the list is selected by default.

- [ ] **Step 3: Test the on-demand screenshot capture**

Start the server, navigate to By Video tab, click on the timeline bar. Verify the `/api/screenshot` POST fires and a new frame appears in the moments list (requires ffmpeg installed and a real video ID in the test data).

- [ ] **Step 4: Commit**

```bash
git add viewer/viewer.html
git commit -m "feat: add By Video split view with timeline and on-demand screenshots"
```

---

### Task 8: viewer.html — Chat widget

**Files:**
- Modify: `viewer/viewer.html`

- [ ] **Step 1: Add the chat widget HTML and CSS**

Add to `viewer/viewer.html`:
- Chat bubble: fixed position bottom-right, 52x52px purple gradient circle, green "AI" dot
- Chat panel: 380px wide, 400px tall, absolute positioned bottom-right, with header (Claude avatar, status, expand/close buttons), message container (scrollable), and input bar
- CSS transitions for open/close animation (transform + opacity, 200ms ease)

- [ ] **Step 2: Add the chat widget JS**

Add chat functionality:
- `toggleChat()` — show/hide the chat panel
- `sendMessage(text)` — POST to `/api/chat` with `{session_id, message}`, append user message bubble, append Claude response bubble
- `appendMessage(role, text)` — render a message bubble (left-aligned dark bg for Claude, right-aligned purple bg for user)
- Timestamp links in Claude responses (`[04:21]` pattern) are clickable — they navigate to the By Video tab and highlight that moment
- Enter key in input sends message

- [ ] **Step 3: Test manually**

Start the server, click the chat bubble, type a message, verify it appears in the thread with a response from the placeholder endpoint.

- [ ] **Step 4: Commit**

```bash
git add viewer/viewer.html
git commit -m "feat: add agentic chat widget to viewer"
```

---

### Task 9: Update SKILL.md with comparison workflow

**Files:**
- Modify: `skills/ytmp4-ai-digest/SKILL.md`

- [ ] **Step 1: Update the SKILL.md frontmatter description**

Add comparison trigger phrases to the description field:

```yaml
description: Browse subscribed YouTube channels for AI-related videos, fetch transcripts, and generate summary digests in Markdown. Also supports multi-video comparison — cross-video analysis with interactive dashboard, frame screenshots, and agentic chat. Use this skill whenever the user mentions "AI videos", "latest AI news", "YouTube AI content", "summarize YouTube", "AI video digest", "what's new in AI", "AI podcast", "youtube ai digest", "compare these videos", "compare video X and Y", "what's the difference between these videos", "cross-video analysis", or wants to catch up on recent AI developments even without specifying a source.
```

- [ ] **Step 2: Add the Video Comparison section to SKILL.md**

Append after the "Common Usage Scenarios" table:

```markdown
## Video Comparison

Compare multiple YouTube videos on the same topic with an interactive dashboard.

### Comparison Workflow

```bash
# Step 1: Fetch transcripts and metadata for all videos
cd ${CLAUDE_PLUGIN_ROOT}
python scripts/compare_videos.py --urls URL1 URL2 URL3

# Step 2: Claude reads comparison_data.json and fills in the analysis
# (unified_summary, topics, disagreements, key_moments)

# Step 3: Launch the interactive viewer
python scripts/compare_server.py --port 5123 --session SESSION_ID
```

### What Claude Does After compare_videos.py

After the script outputs comparison_data.json, Claude reads the transcripts and fills in:
- **Unified Summary** — cross-video synthesis paragraph
- **Topics** — shared themes with per-video timestamps, quotes, and consensus status
- **Disagreements** — where creators differ, with both sides stated
- **Key Moments** — notable timestamps worth capturing as screenshots

Then Claude updates the JSON file and launches the viewer.

### Frame Screenshots

Claude auto-identifies key moments from transcripts and captures frames using ffmpeg.
Users can also click any point on the timeline in the viewer to capture additional frames on demand.

### Comparison Scenarios

| User Says | Claude Should Do |
|-----------|-----------------|
| "Compare these videos: URL1, URL2" | Run compare_videos.py, analyze, launch viewer |
| "What do they disagree on?" | Reference the disagreements section |
| "Capture the chart at 4:21 in video 2" | Run capture_frames.py for that timestamp |
| "Show me all sessions" | Launch viewer showing session history |
```

- [ ] **Step 3: Commit**

```bash
git add skills/ytmp4-ai-digest/SKILL.md
git commit -m "docs: add video comparison workflow to SKILL.md"
```

---

### Task 10: Update .gitignore and add requirements

**Files:**
- Modify: `.gitignore`
- Create: `requirements.txt`

- [ ] **Step 1: Update .gitignore**

Add these lines to `.gitignore`:

```
# Superpowers brainstorm artifacts
.superpowers/

# Design docs are tracked
!docs/
```

- [ ] **Step 2: Create requirements.txt**

```
# requirements.txt
yt-dlp
flask
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore requirements.txt
git commit -m "chore: update .gitignore and add requirements.txt"
```

---

### Task 11: Create tests directory init and run full test suite

**Files:**
- Create: `tests/__init__.py`

- [ ] **Step 1: Create test init file**

```python
# tests/__init__.py
```

- [ ] **Step 2: Run full test suite**

Run: `cd c:/Users/digit/Developer/ytmp4-ai-digest && python -m pytest tests/ -v`
Expected: All tests pass (test_capture_frames: 6, test_compare_videos: 6, test_session_persistence: 2, test_compare_server: 4 = 18 total)

- [ ] **Step 3: Commit**

```bash
git add tests/__init__.py
git commit -m "test: add tests init and verify full suite passes"
```
