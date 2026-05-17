import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from online_obs.engine import SessionEngine
from online_obs.errors import ServiceUnavailableError, ValidationError


class SessionEngineTests(unittest.TestCase):
    def test_dry_run_builds_pipeline_for_basic_scene(self):
        engine = SessionEngine()
        session = engine.create_session({
            "id": "demo",
            "canvas": {"width": 1280, "height": 720, "fps": 30},
            "output": {"type": "rtmp", "url": "rtmp://example/live/stream", "bitrateKbps": 2500},
        })
        self.assertEqual(session["status"], "idle")

        engine.add_source("demo", {"id": "camera", "type": "testsrc", "pattern": "smpte"})
        engine.add_source("demo", {"id": "title", "type": "text", "text": "Online OBS"})
        engine.set_scene("demo", {
            "layers": [
                {"id": "camera-full", "sourceId": "camera", "width": 1280, "height": 720, "zIndex": 0},
                {"id": "title-bar", "sourceId": "title", "x": 40, "y": 40, "width": 500, "height": 96, "zIndex": 1},
            ]
        })

        result = engine.start("demo", {"dryRun": True})

        command = result["session"]["pipeline"]["command"]
        self.assertIn("gst-launch-1.0", command)
        self.assertIn("compositor", command)
        self.assertIn("rtmpsink", command)
        self.assertIn("fdkaacenc", command)
        self.assertIn("mux.audio", command)
        self.assertIn("text=Online OBS", command)
        self.assertEqual(result["session"]["pipeline"]["backend"], "gstreamer")
        self.assertEqual(result["session"]["status"], "idle")

    def test_missing_source_in_scene_is_rejected(self):
        engine = SessionEngine()
        engine.create_session({"id": "demo"})

        with self.assertRaises(ValidationError):
            engine.set_scene("demo", {"layers": [{"sourceId": "missing"}]})

    def test_audio_source_is_validated_but_not_a_scene_layer(self):
        engine = SessionEngine()
        engine.create_session({"id": "demo"})

        session = engine.add_source("demo", {
            "id": "music",
            "type": "audio",
            "uri": "/tmp/music.wav",
            "volume": 0.75,
        })

        self.assertEqual(session["sources"][0]["volume"], 0.75)
        with self.assertRaises(ValidationError):
            engine.add_source("demo", {
                "id": "too_loud",
                "type": "audio",
                "uri": "/tmp/loud.wav",
                "volume": 2.5,
            })
        with self.assertRaises(ValidationError):
            engine.set_scene("demo", {"layers": [{"id": "music-layer", "sourceId": "music"}]})

    def test_start_without_gstreamer_returns_pipeline_detail(self):
        engine = SessionEngine(gst_binary="definitely-not-gst")
        engine.create_session({"id": "demo"})

        with self.assertRaises(ServiceUnavailableError) as context:
            engine.start("demo", {})

        self.assertIn("pipeline", context.exception.details)

    def test_ffmpeg_dry_run_builds_rtmp_command(self):
        engine = SessionEngine()
        engine.create_session({
            "id": "demo",
            "output": {"type": "rtmp", "url": "rtmp://127.0.0.1:1935/live/demo"},
        })

        result = engine.start("demo", {"backend": "ffmpeg", "dryRun": True})

        command = result["session"]["pipeline"]["command"]
        self.assertIn("ffmpeg", command)
        self.assertIn("testsrc2", command)
        self.assertIn("rtmp://127.0.0.1:1935/live/demo", command)

    def test_restart_dry_run_reuses_previous_backend(self):
        engine = SessionEngine()
        engine.create_session({
            "id": "demo",
            "output": {"type": "rtmp", "url": "rtmp://127.0.0.1:1935/live/demo"},
        })
        engine.start("demo", {"backend": "ffmpeg", "dryRun": True})

        result = engine.restart("demo", {"dryRun": True})

        self.assertTrue(result["dryRun"])
        self.assertEqual(result["session"]["pipeline"]["backend"], "ffmpeg")

    def test_update_and_delete_source(self):
        engine = SessionEngine()
        engine.create_session({"id": "demo"})
        engine.add_source("demo", {"id": "title", "type": "text", "text": "First"})

        updated = engine.update_source("demo", "title", {"type": "text", "text": "Second"})

        self.assertEqual(updated["sources"][0]["text"], "Second")
        deleted = engine.delete_source("demo", "title")
        self.assertEqual(deleted["sources"], [])

    def test_delete_referenced_source_is_rejected(self):
        engine = SessionEngine()
        engine.create_session({"id": "demo"})
        engine.add_source("demo", {"id": "camera", "type": "testsrc"})
        engine.set_scene("demo", {"layers": [{"id": "camera", "sourceId": "camera"}]})

        with self.assertRaises(ValidationError):
            engine.delete_source("demo", "camera")

    def test_update_session_output_and_canvas(self):
        engine = SessionEngine()
        engine.create_session({"id": "demo"})

        updated = engine.update_session("demo", {
            "canvas": {"width": 1280, "height": 720, "fps": 25},
            "output": {
                "type": "rtmp",
                "url": "rtmp://127.0.0.1:1935/live/updated",
                "bitrateKbps": 1800,
            },
        })

        self.assertEqual(updated["canvas"], {"width": 1280, "height": 720, "fps": 25})
        self.assertEqual(updated["scene"]["canvas"], updated["canvas"])
        self.assertEqual(updated["output"]["url"], "rtmp://127.0.0.1:1935/live/updated")

    def test_aac_encoder_can_be_overridden_for_container_images(self):
        engine = SessionEngine()
        engine.create_session({
            "id": "demo",
            "output": {"type": "rtmp", "url": "rtmp://127.0.0.1:1935/live/demo"},
        })

        with patch.dict("os.environ", {"ONLINE_OBS_AAC_ENCODER": "avenc_aac"}):
            result = engine.start("demo", {"dryRun": True})

        command = result["session"]["pipeline"]["command"]
        self.assertIn("avenc_aac", command)
        self.assertIn("audio/x-raw,format=F32LE,rate=44100,channels=2", command)
        self.assertNotIn("fdkaacenc", command)

    def test_file_source_loop_is_reflected_in_pipeline(self):
        engine = SessionEngine()
        engine.create_session({
            "id": "demo",
            "output": {"type": "rtmp", "url": "rtmp://127.0.0.1:1935/live/demo"},
        })
        engine.add_source("demo", {
            "id": "clip",
            "type": "file",
            "uri": "/tmp/clip.mp4",
            "loop": True,
        })
        engine.set_scene("demo", {
            "layers": [{"id": "clip-layer", "sourceId": "clip"}],
        })

        result = engine.start("demo", {"dryRun": True})

        pipeline = result["session"]["pipeline"]
        self.assertEqual(pipeline["loopingSources"], ["clip"])
        self.assertIn("identity sync=true", pipeline["command"])
        self.assertNotIn("mux.audio", pipeline["command"])

    def test_audio_sources_are_mixed_into_rtmp_output(self):
        engine = SessionEngine()
        engine.create_session({
            "id": "demo",
            "output": {"type": "rtmp", "url": "rtmp://127.0.0.1:1935/live/demo"},
        })
        engine.add_source("demo", {"id": "camera", "type": "testsrc"})
        engine.add_source("demo", {"id": "music", "type": "audio", "uri": "/tmp/music.wav", "volume": 0.7})
        engine.add_source("demo", {"id": "mic", "type": "audio", "uri": "/tmp/mic.wav", "volume": 1.2})
        engine.set_scene("demo", {"layers": [{"id": "camera-layer", "sourceId": "camera"}]})

        result = engine.start("demo", {"dryRun": True})

        pipeline = result["session"]["pipeline"]
        command = pipeline["command"]
        self.assertEqual(pipeline["audioSources"], ["music", "mic"])
        self.assertIn("audiomixer name=amix", command)
        self.assertIn(f"uridecodebin uri={Path('/tmp/music.wav').resolve().as_uri()}", command)
        self.assertIn("volume volume=0.7", command)
        self.assertIn("amix.sink_0", command)
        self.assertIn("amix.sink_1", command)
        self.assertNotIn("audiotestsrc is-live=true wave=silence", command)

    def test_audio_only_rtmp_output_uses_default_video(self):
        engine = SessionEngine()
        engine.create_session({
            "id": "demo",
            "output": {"type": "rtmp", "url": "rtmp://127.0.0.1:1935/live/demo"},
        })
        engine.add_source("demo", {"id": "music", "type": "audio", "uri": "/tmp/music.wav"})

        result = engine.start("demo", {"dryRun": True})

        command = result["session"]["pipeline"]["command"]
        self.assertIn("videotestsrc is-live=true pattern=smpte", command)
        self.assertIn("audiomixer name=amix", command)
        self.assertNotIn("audiotestsrc is-live=true wave=silence", command)

    def test_get_session_refreshes_exited_process_and_keeps_logs(self):
        class FinishedProcess:
            def poll(self):
                return 1

        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "stream.log"
            log_path.write_text("encoder failed\n", encoding="utf-8")
            engine = SessionEngine()
            engine.create_session({"id": "demo"})
            session = engine.sessions["demo"]
            session.status = "running"
            session.process = FinishedProcess()
            session.log_path = str(log_path)

            payload = engine.get_session("demo")
            logs = engine.get_logs("demo")

            self.assertEqual(payload["status"], "exited")
            self.assertEqual(logs["stderr"], "encoder failed\n")


if __name__ == "__main__":
    unittest.main()
