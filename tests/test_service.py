import unittest
import http.client
import json
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from online_obs.engine import SessionEngine
from online_obs.config import AppConfig
from online_obs.errors import NotFoundError, PayloadTooLargeError, ValidationError
from online_obs.service import (
    Handler,
    OnlineObsServer,
    content_type_allowed,
    delete_upload,
    list_uploads,
    route_request,
    sanitize_upload_filename,
    save_upload,
)
from online_obs.storage import SQLiteSessionStore


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = SessionEngine(gst_binary="definitely-not-gst")

    def test_health(self):
        payload = route_request(self.engine, "GET", "/health")
        self.assertEqual(payload, {"ok": True})

    def test_openapi_document_is_valid_and_served(self):
        path = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
        document = json.loads(path.read_text(encoding="utf-8"))

        payload = route_request(self.engine, "GET", "/openapi.json")

        self.assertEqual(payload["openapi"], "3.1.0")
        self.assertEqual(payload["info"]["title"], "Online OBS API")
        self.assertIn("/sessions/{sessionId}/start", payload["paths"])
        self.assertEqual(payload, document)

    def test_config_route_returns_public_runtime_config(self):
        config = AppConfig(
            hls_host="localhost",
            hls_port=18888,
            upload_dir=Path("/tmp/online-obs-uploads"),
            db_path=Path("/tmp/online-obs.sqlite3"),
            gst_plugin_dir=None,
        )

        payload = route_request(self.engine, "GET", "/config", app_config=config)

        self.assertEqual(payload["hlsHost"], "localhost")
        self.assertEqual(payload["hlsPort"], 18888)
        self.assertEqual(payload["uploadDir"], "/tmp/online-obs-uploads")
        self.assertTrue(payload["dbEnabled"])
        self.assertEqual(payload["gstPluginDir"], "")
        self.assertFalse(payload["authRequired"])
        self.assertEqual(payload["maxUploadBytes"], 1024 * 1024 * 1024)
        self.assertEqual(payload["allowedUploadTypes"], ["video/*", "audio/*", "image/*"])

    def test_auth_token_protects_private_http_routes(self):
        config = AppConfig(auth_token="secret-token")
        server = OnlineObsServer(("127.0.0.1", 0), Handler, self.engine, config)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            connection.request("GET", "/health")
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 200)
            connection.close()

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            connection.request("GET", "/sessions")
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 401)
            connection.close()

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            connection.request("GET", "/sessions", headers={"Authorization": "Bearer secret-token"})
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertEqual(payload, {"sessions": []})
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_create_session_and_dry_run_start(self):
        session = route_request(self.engine, "POST", "/sessions", {"id": "demo"})
        self.assertEqual(session["id"], "demo")

        payload = route_request(self.engine, "POST", "/sessions/demo/start", {"dryRun": True})
        self.assertTrue(payload["dryRun"])
        self.assertIn("fakesink", payload["session"]["pipeline"]["command"])

        logs = route_request(self.engine, "GET", "/sessions/demo/logs")
        self.assertEqual(logs, {"sessionId": "demo", "stderr": ""})

    def test_restart_route(self):
        route_request(self.engine, "POST", "/sessions", {"id": "demo"})

        payload = route_request(self.engine, "POST", "/sessions/demo/restart", {"dryRun": True})

        self.assertTrue(payload["dryRun"])
        self.assertEqual(payload["session"]["pipeline"]["backend"], "gstreamer")

    def test_list_update_delete_routes(self):
        route_request(self.engine, "POST", "/sessions", {"id": "demo"})
        route_request(self.engine, "POST", "/sessions/demo/sources", {
            "id": "title",
            "type": "text",
            "text": "Before",
        })

        listed = route_request(self.engine, "GET", "/sessions")
        self.assertEqual([session["id"] for session in listed["sessions"]], ["demo"])

        session = route_request(self.engine, "PUT", "/sessions/demo", {
            "output": {"type": "rtmp", "url": "rtmp://127.0.0.1:1935/live/demo"},
        })
        self.assertEqual(session["output"]["type"], "rtmp")

        updated = route_request(self.engine, "PUT", "/sessions/demo/sources/title", {
            "type": "text",
            "text": "After",
        })
        self.assertEqual(updated["sources"][0]["text"], "After")

        without_source = route_request(self.engine, "DELETE", "/sessions/demo/sources/title")
        self.assertEqual(without_source["sources"], [])

        deleted = route_request(self.engine, "DELETE", "/sessions/demo")
        self.assertEqual(deleted, {"id": "demo", "deleted": True})

    def test_save_upload_stores_file_safely(self):
        boundary = "----onlineobs"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="../My Clip.mp4"\r\n'
            "Content-Type: video/mp4\r\n"
            "\r\n"
        ).encode("utf-8") + b"video-bytes" + f"\r\n--{boundary}--\r\n".encode("utf-8")

        with TemporaryDirectory() as directory:
            result = save_upload(
                f"multipart/form-data; boundary={boundary}",
                body,
                upload_dir=Path(directory),
            )

            self.assertEqual(result["filename"], "../My Clip.mp4")
            self.assertEqual(result["name"], "../My Clip.mp4")
            self.assertTrue(result["storedName"].endswith("_My_Clip.mp4"))
            self.assertEqual(Path(result["path"]).read_bytes(), b"video-bytes")
            Path(result["path"]).resolve().relative_to(Path(directory).resolve())
            self.assertEqual(result["size"], len(b"video-bytes"))

    def test_save_upload_enforces_size_and_type_limits(self):
        boundary = "----onlineobs"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="clip.mp4"\r\n'
            "Content-Type: video/mp4\r\n"
            "\r\n"
        ).encode("utf-8") + b"video-bytes" + f"\r\n--{boundary}--\r\n".encode("utf-8")

        with TemporaryDirectory() as directory:
            with self.assertRaises(PayloadTooLargeError):
                save_upload(
                    f"multipart/form-data; boundary={boundary}",
                    body,
                    upload_dir=Path(directory),
                    max_bytes=4,
                )

            with self.assertRaises(ValidationError):
                save_upload(
                    f"multipart/form-data; boundary={boundary}",
                    body,
                    upload_dir=Path(directory),
                    allowed_content_types=("audio/*",),
                )

        self.assertTrue(content_type_allowed("video/mp4", ("video/*",)))
        self.assertTrue(content_type_allowed("audio/wav; charset=binary", ("audio/*",)))
        self.assertFalse(content_type_allowed("text/plain", ("video/*", "audio/*")))

    def test_list_uploads_returns_file_metadata(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "aaaaaaaaaaaa_clip.mp4"
            second = root / "bbbbbbbbbbbb_cover.png"
            first.write_bytes(b"video")
            second.write_bytes(b"image")

            result = list_uploads(upload_dir=root)

            by_name = {item["storedName"]: item for item in result["uploads"]}
            self.assertEqual(by_name[first.name]["name"], "clip.mp4")
            self.assertEqual(by_name[first.name]["path"], str(first.resolve()))
            self.assertEqual(by_name[first.name]["size"], 5)
            self.assertEqual(by_name[first.name]["contentType"], "video/mp4")
            self.assertEqual(by_name[second.name]["contentType"], "image/png")

    def test_upload_metadata_survives_store_reload(self):
        boundary = "----onlineobs"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="../Original Clip.mp4"\r\n'
            "Content-Type: video/mp4\r\n"
            "\r\n"
        ).encode("utf-8") + b"video-bytes" + f"\r\n--{boundary}--\r\n".encode("utf-8")

        with TemporaryDirectory() as directory:
            root = Path(directory) / "uploads"
            db_path = Path(directory) / "online_obs.sqlite3"
            store = SQLiteSessionStore(db_path)
            saved = save_upload(
                f"multipart/form-data; boundary={boundary}",
                body,
                upload_dir=root,
                upload_store=store,
            )

            reloaded_store = SQLiteSessionStore(db_path)
            listed = list_uploads(upload_dir=root, upload_store=reloaded_store)

            self.assertEqual(listed["uploads"][0]["storedName"], saved["storedName"])
            self.assertEqual(listed["uploads"][0]["name"], "../Original Clip.mp4")
            self.assertEqual(listed["uploads"][0]["contentType"], "video/mp4")
            self.assertEqual(listed["uploads"][0]["size"], len(b"video-bytes"))

            deleted = delete_upload(saved["storedName"], upload_dir=root, upload_store=reloaded_store)
            self.assertTrue(deleted["deleted"])
            self.assertEqual(list_uploads(upload_dir=root, upload_store=reloaded_store), {"uploads": []})

    def test_delete_upload_removes_only_upload_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "aaaaaaaaaaaa_clip.mp4"
            target.write_bytes(b"video")

            result = delete_upload(target.name, upload_dir=root)

            self.assertEqual(result, {"storedName": target.name, "deleted": True})
            self.assertFalse(target.exists())

            with self.assertRaises(NotFoundError):
                delete_upload(target.name, upload_dir=root)

            with self.assertRaises(ValidationError):
                delete_upload("../outside.mp4", upload_dir=root)

    def test_upload_routes_accept_custom_upload_dir(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "aaaaaaaaaaaa_clip.mp4"
            target.write_bytes(b"video")

            listed = route_request(self.engine, "GET", "/uploads", upload_dir=root)
            self.assertEqual(listed["uploads"][0]["storedName"], target.name)

            deleted = route_request(self.engine, "DELETE", f"/uploads/{target.name}", upload_dir=root)
            self.assertTrue(deleted["deleted"])

    def test_upload_routes_use_store_metadata_when_available(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "uploads"
            root.mkdir()
            target = root / "aaaaaaaaaaaa_sanitized.mp4"
            target.write_bytes(b"video")
            store = SQLiteSessionStore(Path(directory) / "online_obs.sqlite3")
            store.save_upload_metadata({
                "storedName": target.name,
                "name": "Original Name.mp4",
                "path": str(target.resolve()),
                "size": target.stat().st_size,
                "contentType": "video/custom",
            })

            listed = route_request(
                self.engine,
                "GET",
                "/uploads",
                upload_dir=root,
                upload_store=store,
            )
            self.assertEqual(listed["uploads"][0]["name"], "Original Name.mp4")
            self.assertEqual(listed["uploads"][0]["contentType"], "video/custom")

    def test_sanitize_upload_filename(self):
        self.assertEqual(sanitize_upload_filename("../../a b.mov"), "a_b.mov")
        self.assertEqual(sanitize_upload_filename("..."), "upload.bin")


if __name__ == "__main__":
    unittest.main()
