import unittest
from pathlib import Path
from unittest.mock import patch

from online_obs.config import AppConfig


class AppConfigTests(unittest.TestCase):
    def test_defaults_preserve_local_behavior(self):
        with patch.dict("os.environ", {}, clear=True):
            config = AppConfig.from_env()

        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8080)
        self.assertEqual(config.upload_dir.name, "uploads")
        self.assertEqual(config.hls_host, "127.0.0.1")
        self.assertEqual(config.hls_port, 8888)
        self.assertEqual(config.gst_plugin_dir.name, "gst-min-plugins")
        self.assertEqual(config.auth_token, "")
        self.assertEqual(config.max_upload_bytes, 1024 * 1024 * 1024)
        self.assertEqual(config.allowed_upload_types, ("video/*", "audio/*", "image/*"))

    def test_environment_overrides(self):
        with patch.dict(
            "os.environ",
            {
                "ONLINE_OBS_HOST": "0.0.0.0",
                "ONLINE_OBS_PORT": "18080",
                "ONLINE_OBS_UPLOAD_DIR": "/tmp/online-obs-uploads",
                "ONLINE_OBS_DB": "/tmp/online-obs.sqlite3",
                "ONLINE_OBS_GST_PLUGIN_DIR": "",
                "ONLINE_OBS_HLS_HOST": "localhost",
                "ONLINE_OBS_HLS_PORT": "18888",
                "ONLINE_OBS_AUTH_TOKEN": "secret-token",
                "ONLINE_OBS_MAX_UPLOAD_BYTES": "4096",
                "ONLINE_OBS_ALLOWED_UPLOAD_TYPES": "video/mp4,audio/*",
            },
            clear=True,
        ):
            config = AppConfig.from_env()

        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 18080)
        self.assertEqual(config.upload_dir, Path("/tmp/online-obs-uploads"))
        self.assertEqual(config.db_path, Path("/tmp/online-obs.sqlite3"))
        self.assertEqual(config.gst_plugin_dir, None)
        self.assertEqual(config.hls_host, "localhost")
        self.assertEqual(config.hls_port, 18888)
        self.assertEqual(config.auth_token, "secret-token")
        self.assertEqual(config.max_upload_bytes, 4096)
        self.assertEqual(config.allowed_upload_types, ("video/mp4", "audio/*"))


if __name__ == "__main__":
    unittest.main()
