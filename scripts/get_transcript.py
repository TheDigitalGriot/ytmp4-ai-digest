#!/usr/bin/env python3
"""Fetch video transcripts using yt-dlp, with proxy and cookie support."""
import json
import os
import argparse
import subprocess
from pathlib import Path

DATA_DIR = Path(os.environ.get("CLAUDE_PLUGIN_DATA", Path(__file__).parent.parent / "data"))


def _find_ytdlp():
    """Find yt-dlp executable, checking common install locations on Windows."""
    import shutil
    found = shutil.which("yt-dlp")
    if found:
        return found
    # Check user Scripts dir (pip install --user)
    user_scripts = Path.home() / "AppData" / "Roaming" / "Python" / f"Python{__import__('sys').version_info.major}{__import__('sys').version_info.minor}" / "Scripts" / "yt-dlp.exe"
    if user_scripts.exists():
        return str(user_scripts)
    return "yt-dlp"  # fallback, let it fail with a clear error


def get_env():
    """Inherit current environment (including HTTPS_PROXY and other proxy variables)."""
    return {**os.environ}


def get_transcript_ytdlp(video_id):
    """
    Fetch subtitles using yt-dlp with a 3-tier fallback strategy:
      1. Try without cookies (works for most public videos)
      2. Retry with Chrome cookies
      3. Retry with Firefox cookies
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = str(DATA_DIR / f"sub_{video_id}")

    ytdlp = _find_ytdlp()
    base_cmd = [
        ytdlp, "--skip-download",
        "--write-auto-sub", "--write-sub",
        "--sub-lang", "en,zh",
        "--sub-format", "vtt",
        "-o", output_template,
    ]

    print("  Attempting to fetch subtitles without cookies...", flush=True)
    subprocess.run(base_cmd + [url], capture_output=True, env=get_env(), timeout=60)

    result = _find_vtt(video_id)
    if result[0]:
        return result

    print("  Retrying with Chrome cookies...", flush=True)
    subprocess.run(
        base_cmd + ["--cookies-from-browser", "chrome", url],
        capture_output=True,
        env=get_env(),
        timeout=60
    )

    result = _find_vtt(video_id)
    if result[0]:
        return result

    print("  Retrying with Firefox cookies...", flush=True)
    subprocess.run(
        base_cmd + ["--cookies-from-browser", "firefox", url],
        capture_output=True,
        env=get_env(),
        timeout=60
    )

    return _find_vtt(video_id)


def _find_vtt(video_id):
    """Find generated subtitle files in the data directory."""
    for suffix in [".en.vtt", ".zh.vtt", ".en-orig.vtt", ".zh-Hans.vtt"]:
        sub_file = DATA_DIR / f"sub_{video_id}{suffix}"
        if sub_file.exists():
            lang = suffix.split(".")[1]
            return parse_vtt(sub_file), lang
    return None, None


def parse_vtt(vtt_file):
    """Parse a VTT subtitle file, deduplicate and merge entries."""
    content = vtt_file.read_text(encoding="utf-8")
    lines = content.split("\n")
    transcript = []
    seen_texts = set()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            parts = line.split("-->")
            start_time = parts[0].strip()
            time_parts = start_time.replace(",", ".").split(":")
            if len(time_parts) == 3:
                h, m, s = time_parts
                start_seconds = int(h) * 3600 + int(m) * 60 + float(s.split(".")[0])
            else:
                start_seconds = 0
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                text = lines[i].strip()
                if not text.isdigit() and "<" not in text and text not in seen_texts:
                    text_lines.append(text)
                    seen_texts.add(text)
                i += 1
            if text_lines:
                transcript.append({"start": start_seconds, "text": " ".join(text_lines)})
        else:
            i += 1
    return transcript


def format_transcript(transcript):
    """Format transcript as timestamped plain text."""
    lines = []
    for entry in transcript:
        start = int(entry["start"])
        mins, secs = divmod(start, 60)
        lines.append(f"[{mins:02d}:{secs:02d}] {entry['text']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube video transcripts")
    parser.add_argument("--video-id", required=True, help="YouTube video ID")
    parser.add_argument("--output", help="Custom output file path")
    args = parser.parse_args()

    print(f"Fetching transcript: {args.video_id}", flush=True)
    transcript, lang = get_transcript_ytdlp(args.video_id)

    if not transcript:
        print("Failed to fetch transcript (video may require login or have no subtitles)")
        return

    formatted = format_transcript(transcript)
    print(f"Transcript language: {lang}, {len(transcript)} entries")

    output_file = Path(args.output) if args.output else DATA_DIR / f"transcript_{args.video_id}.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(formatted, encoding="utf-8")
    print(f"Saved to: {output_file}")

    json_file = DATA_DIR / f"transcript_{args.video_id}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
