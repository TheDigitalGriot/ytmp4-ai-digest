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
