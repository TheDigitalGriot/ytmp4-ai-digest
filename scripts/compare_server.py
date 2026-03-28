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
