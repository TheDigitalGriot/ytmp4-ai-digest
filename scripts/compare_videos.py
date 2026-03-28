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

from _utils import find_ytdlp, get_env, DATA_DIR
from capture_frames import extract_video_id, capture_frame
from get_transcript import get_transcript_ytdlp, format_transcript
SESSIONS_DIR = DATA_DIR / "sessions"


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
    cmd = [find_ytdlp(), "--dump-json", "--no-download", f"https://www.youtube.com/watch?v={video_id}"]
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
            find_ytdlp(), "--write-thumbnail", "--skip-download",
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
