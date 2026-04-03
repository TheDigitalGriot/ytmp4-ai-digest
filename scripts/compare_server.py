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

    @app.route("/api/videos")
    def get_all_videos():
        """Return deduplicated list of all videos across all sessions."""
        index_file = sessions_dir / "index.json"
        if not index_file.exists():
            return jsonify([])

        with open(index_file) as f:
            index = json.load(f)

        seen = {}
        for entry in index:
            data_file = sessions_dir / entry["dir_name"] / "comparison_data.json"
            if not data_file.exists():
                continue
            with open(data_file) as f:
                data = json.load(f)
            for video in data.get("videos", []):
                vid = video.get("id")
                if vid and vid not in seen:
                    seen[vid] = {
                        "id": vid,
                        "title": video.get("title", "Unknown"),
                        "channel": video.get("channel", "Unknown"),
                        "duration": video.get("duration", ""),
                        "upload_date": video.get("upload_date", ""),
                        "thumbnail_base64": video.get("thumbnail_base64"),
                        "session_id": entry["id"],
                        "session_title": entry["title"],
                    }
        return jsonify(list(seen.values()))

    @app.route("/api/sessions/compose", methods=["POST"])
    def compose_session():
        """Create a new session from library videos + new URLs."""
        body = request.get_json()
        if not body:
            return jsonify({"error": "Request body required"}), 400

        title = body.get("title", "")
        video_ids = body.get("video_ids", [])
        new_urls = body.get("new_urls", [])

        if not video_ids and not new_urls:
            return jsonify({"error": "Provide video_ids and/or new_urls"}), 400

        videos = []

        # Load cached videos from existing sessions
        if video_ids:
            index_file = sessions_dir / "index.json"
            if index_file.exists():
                with open(index_file) as f:
                    index = json.load(f)
                # Build a lookup of all videos across sessions
                all_videos = {}
                for entry in index:
                    data_file = sessions_dir / entry["dir_name"] / "comparison_data.json"
                    if not data_file.exists():
                        continue
                    with open(data_file) as f:
                        data = json.load(f)
                    for v in data.get("videos", []):
                        if v.get("id") and v["id"] not in all_videos:
                            all_videos[v["id"]] = v
                for vid in video_ids:
                    if vid in all_videos:
                        videos.append(all_videos[vid])

        # Fetch new videos from URLs
        if new_urls:
            from compare_videos import parse_urls, process_video
            for url in new_urls:
                try:
                    vid_id = parse_urls([url])[0]
                    video_data = process_video(vid_id)
                    videos.append(video_data)
                except Exception as e:
                    return jsonify({"error": f"Failed to process {url}: {str(e)}"}), 500

        if not videos:
            return jsonify({"error": "No valid videos found"}), 400

        # Build and save session
        from compare_videos import build_comparison_data, save_session
        if not title:
            title = f"Comparison: {', '.join(v.get('channel', '?') for v in videos[:3])}"
            if len(videos) > 3:
                title += f" +{len(videos) - 3}"

        comparison_data = build_comparison_data(videos, title)
        save_session(comparison_data)

        return jsonify(comparison_data), 201

    @app.route("/api/session/<session_id>/add-videos", methods=["POST"])
    def add_videos(session_id):
        """Add videos to an existing session."""
        body = request.get_json()
        if not body:
            return jsonify({"error": "Request body required"}), 400

        video_ids = body.get("video_ids", [])
        new_urls = body.get("new_urls", [])

        if not video_ids and not new_urls:
            return jsonify({"error": "Provide video_ids and/or new_urls"}), 400

        new_videos = []

        # Load cached videos from library
        if video_ids:
            index_file = sessions_dir / "index.json"
            if index_file.exists():
                with open(index_file) as f:
                    index = json.load(f)
                all_videos = {}
                for entry in index:
                    data_file = sessions_dir / entry["dir_name"] / "comparison_data.json"
                    if not data_file.exists():
                        continue
                    with open(data_file) as f:
                        data = json.load(f)
                    for v in data.get("videos", []):
                        if v.get("id") and v["id"] not in all_videos:
                            all_videos[v["id"]] = v
                for vid in video_ids:
                    if vid in all_videos:
                        new_videos.append(all_videos[vid])

        # Fetch new videos from URLs
        if new_urls:
            from compare_videos import parse_urls, process_video
            for url in new_urls:
                try:
                    vid_id = parse_urls([url])[0]
                    video_data = process_video(vid_id)
                    new_videos.append(video_data)
                except Exception as e:
                    return jsonify({"error": f"Failed to process {url}: {str(e)}"}), 500

        if not new_videos:
            return jsonify({"error": "No valid videos found"}), 400

        # Add to existing session
        from compare_videos import add_videos_to_session
        try:
            add_videos_to_session(session_id, new_videos)
        except (FileNotFoundError, ValueError) as e:
            return jsonify({"error": str(e)}), 404

        # Return updated session data
        index_file = sessions_dir / "index.json"
        with open(index_file) as f:
            index = json.load(f)
        entry = next((e for e in index if e["id"] == session_id), None)
        if entry:
            data_file = sessions_dir / entry["dir_name"] / "comparison_data.json"
            with open(data_file) as f:
                return jsonify(json.load(f))

        return jsonify({"error": "Session updated but could not reload"}), 500

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
