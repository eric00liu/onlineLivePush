import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from online_obs.engine import SessionEngine
from online_obs.storage import SQLiteSessionStore


class SQLiteSessionStoreTests(unittest.TestCase):
    def test_session_definition_reloads_from_sqlite(self):
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "online_obs.sqlite3"
            engine = SessionEngine(store=SQLiteSessionStore(db_path))
            engine.create_session({
                "id": "demo",
                "canvas": {"width": 1280, "height": 720, "fps": 30},
                "output": {"type": "rtmp", "url": "rtmp://127.0.0.1:1935/live/demo"},
            })
            engine.add_source("demo", {"id": "camera", "type": "testsrc", "pattern": "ball"})
            engine.add_source("demo", {"id": "clip", "type": "file", "uri": "/tmp/clip.mp4", "loop": True})
            engine.set_scene("demo", {
                "layers": [
                    {
                        "id": "camera-full",
                        "sourceId": "camera",
                        "width": 1280,
                        "height": 720,
                        "zIndex": 0,
                    }
                ]
            })
            engine.add_animation("demo", {
                "id": "fade-in",
                "layerId": "camera-full",
                "type": "fade",
                "durationMs": 500,
            })
            engine.start("demo", {"backend": "ffmpeg", "dryRun": True})

            reloaded = SessionEngine(store=SQLiteSessionStore(db_path))
            session = reloaded.get_session("demo")

            self.assertEqual(session["id"], "demo")
            self.assertEqual(session["status"], "idle")
            self.assertEqual(session["pipeline"], None)
            self.assertEqual(session["canvas"], {"width": 1280, "height": 720, "fps": 30})
            self.assertEqual(session["sources"][0]["pattern"], "ball")
            clip = next(source for source in session["sources"] if source["id"] == "clip")
            self.assertTrue(clip["loop"])
            self.assertEqual(session["scene"]["layers"][0]["id"], "camera-full")
            self.assertEqual(session["animations"][0]["id"], "fade-in")

    def test_delete_session_removes_persisted_row(self):
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "online_obs.sqlite3"
            engine = SessionEngine(store=SQLiteSessionStore(db_path))
            engine.create_session({"id": "demo"})

            engine.delete_session("demo")

            reloaded = SessionEngine(store=SQLiteSessionStore(db_path))
            self.assertEqual(reloaded.list_sessions(), {"sessions": []})


if __name__ == "__main__":
    unittest.main()
