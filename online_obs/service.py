from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import re
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from uuid import uuid4

from .config import AppConfig
from .engine import SessionEngine
from .errors import ApiError, NotFoundError, PayloadTooLargeError, UnauthorizedError, ValidationError
from .storage import SQLiteSessionStore, UploadStore

STATIC_DIR = Path(__file__).resolve().parent / "static"
OPENAPI_PATH = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024
DEFAULT_ALLOWED_UPLOAD_TYPES = ("video/*", "audio/*", "image/*")


class OnlineObsServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        engine: SessionEngine,
        config: AppConfig,
        upload_store: UploadStore | None = None,
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.engine = engine
        self.config = config
        self.upload_dir = config.upload_dir
        self.upload_store = upload_store


class Handler(BaseHTTPRequestHandler):
    server: OnlineObsServer

    def do_OPTIONS(self) -> None:
        self._send_json({}, HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        if self._send_static_asset():
            return
        self._dispatch("GET")

    def do_POST(self) -> None:
        if self._handle_upload():
            return
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_static_asset(self) -> bool:
        parsed_path = urlparse(self.path).path
        if parsed_path == "/":
            target = STATIC_DIR / "index.html"
        elif parsed_path.startswith("/static/"):
            relative = unquote(parsed_path.removeprefix("/static/"))
            target = STATIC_DIR / relative
        else:
            return False

        try:
            resolved = target.resolve()
            resolved.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._send_json({"error": {"code": "not_found", "message": "static asset was not found"}}, HTTPStatus.NOT_FOUND)
            return True

        if not resolved.is_file():
            self._send_json({"error": {"code": "not_found", "message": "static asset was not found"}}, HTTPStatus.NOT_FOUND)
            return True

        content = resolved.read_bytes()
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        if resolved.suffix == ".js":
            content_type = "text/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        return True

    def _handle_upload(self) -> bool:
        if urlparse(self.path).path != "/uploads":
            return False
        try:
            if not self._authorize_request():
                return True
            length = int(self.headers.get("content-length", "0"))
            if length <= 0:
                raise ValidationError("upload body is empty")
            if length > self.server.config.max_upload_bytes:
                raise PayloadTooLargeError("upload is too large", details={"maxBytes": self.server.config.max_upload_bytes})
            content_type = self.headers.get("content-type", "")
            body = self.rfile.read(length)
            result = save_upload(
                content_type,
                body,
                upload_dir=self.server.upload_dir,
                upload_store=self.server.upload_store,
                max_bytes=self.server.config.max_upload_bytes,
                allowed_content_types=self.server.config.allowed_upload_types,
            )
            self._send_json(result, HTTPStatus.CREATED)
        except ApiError as error:
            self._send_json(error.to_dict(), error.status_code)
        except Exception as error:
            api_error = ApiError("unexpected upload error", details=str(error))
            self._send_json(api_error.to_dict(), api_error.status_code)
        return True

    def _dispatch(self, method: str) -> None:
        try:
            if not self._authorize_request():
                return
            payload = self._read_json() if method in {"POST", "PUT"} else {}
            result = route_request(
                self.server.engine,
                method,
                self.path,
                payload,
                app_config=self.server.config,
                upload_dir=self.server.upload_dir,
                upload_store=self.server.upload_store,
            )
            self._send_json(result)
        except ApiError as error:
            self._send_json(error.to_dict(), error.status_code)
        except json.JSONDecodeError as error:
            api_error = ValidationError("request body must be valid JSON", details=str(error))
            self._send_json(api_error.to_dict(), api_error.status_code)
        except Exception as error:
            api_error = ApiError("unexpected server error", details=str(error))
            self._send_json(api_error.to_dict(), api_error.status_code)

    def _read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValidationError("request body must be a JSON object")
        return payload

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = b"" if status == HTTPStatus.NO_CONTENT else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Online-OBS-Token")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _authorize_request(self) -> bool:
        if request_is_public(self.command, self.path):
            return True
        if request_is_authorized(self.headers, self.server.config.auth_token):
            return True
        error = UnauthorizedError("valid API token is required")
        self._send_json(error.to_dict(), error.status_code)
        return False


def route_request(
    engine: SessionEngine,
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    upload_dir: Path = UPLOAD_DIR,
    upload_store: UploadStore | None = None,
    app_config: AppConfig | None = None,
) -> dict:
    payload = payload or {}
    parts = [part for part in urlparse(path).path.split("/") if part]

    if method == "GET" and parts == ["health"]:
        return {"ok": True}

    if method == "GET" and parts == ["openapi.json"]:
        return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    if method == "GET" and parts == ["config"]:
        return (app_config or AppConfig()).public_dict()

    if method == "GET" and parts == ["uploads"]:
        return list_uploads(upload_dir=upload_dir, upload_store=upload_store)

    if method == "DELETE" and len(parts) == 2 and parts[0] == "uploads":
        return delete_upload(unquote(parts[1]), upload_dir=upload_dir, upload_store=upload_store)

    if method == "POST" and parts == ["sessions"]:
        return engine.create_session(payload)

    if method == "GET" and parts == ["sessions"]:
        return engine.list_sessions()

    if len(parts) >= 2 and parts[0] == "sessions":
        session_id = parts[1]
        if method == "GET" and len(parts) == 2:
            return engine.get_session(session_id)
        if method == "PUT" and len(parts) == 2:
            return engine.update_session(session_id, payload)
        if method == "DELETE" and len(parts) == 2:
            return engine.delete_session(session_id)
        if method == "GET" and parts[2:] == ["pipeline"]:
            return engine.render_pipeline(session_id)
        if method == "GET" and parts[2:] == ["logs"]:
            return engine.get_logs(session_id)
        if method == "POST" and parts[2:] == ["sources"]:
            return engine.add_source(session_id, payload)
        if len(parts) == 4 and parts[2] == "sources":
            if method == "PUT":
                return engine.update_source(session_id, parts[3], payload)
            if method == "DELETE":
                return engine.delete_source(session_id, parts[3])
        if method == "PUT" and parts[2:] == ["scene"]:
            return engine.set_scene(session_id, payload)
        if method == "POST" and parts[2:] == ["animations"]:
            return engine.add_animation(session_id, payload)
        if method == "POST" and parts[2:] == ["start"]:
            return engine.start(session_id, payload)
        if method == "POST" and parts[2:] == ["stop"]:
            return engine.stop(session_id)
        if method == "POST" and parts[2:] == ["restart"]:
            return engine.restart(session_id, payload)

    raise NotFoundError(f"route {method} {path} was not found")


def save_upload(
    content_type: str,
    body: bytes,
    *,
    upload_dir: Path = UPLOAD_DIR,
    upload_store: UploadStore | None = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
    allowed_content_types: tuple[str, ...] = DEFAULT_ALLOWED_UPLOAD_TYPES,
) -> dict:
    if "multipart/form-data" not in content_type:
        raise ValidationError("upload must use multipart/form-data")

    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    if not message.is_multipart():
        raise ValidationError("upload body must be multipart")

    file_part = None
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") == "file":
            file_part = part
            break

    if file_part is None:
        raise ValidationError("upload must include a file field")

    original_name = file_part.get_filename() or "upload.bin"
    file_bytes = file_part.get_payload(decode=True) or b""
    if not file_bytes:
        raise ValidationError("uploaded file is empty")
    if len(file_bytes) > max_bytes:
        raise PayloadTooLargeError("upload is too large", details={"maxBytes": max_bytes})
    part_content_type = file_part.get_content_type()
    if not content_type_allowed(part_content_type, allowed_content_types):
        raise ValidationError(
            "uploaded file type is not allowed",
            details={"contentType": part_content_type, "allowedTypes": list(allowed_content_types)},
        )

    upload_dir.mkdir(parents=True, exist_ok=True)
    root = upload_dir.resolve()
    stored_name = f"{uuid4().hex[:12]}_{sanitize_upload_filename(original_name)}"
    target = (root / stored_name).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValidationError("upload path is outside the upload directory")
    target.write_bytes(file_bytes)

    result = {
        "filename": original_name,
        "storedName": stored_name,
        "name": original_name,
        "path": str(target),
        "size": len(file_bytes),
        "contentType": part_content_type,
    }
    if upload_store is not None:
        upload_store.save_upload_metadata(result)
    return result


def list_uploads(*, upload_dir: Path = UPLOAD_DIR, upload_store: UploadStore | None = None) -> dict:
    upload_dir.mkdir(parents=True, exist_ok=True)
    root = upload_dir.resolve()
    metadata = upload_store.load_upload_metadata() if upload_store is not None else {}
    uploads = []
    for path in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        stored_name = path.name
        upload = metadata.get(stored_name, {})
        content_type = upload.get("contentType") or mimetypes.guess_type(path.name)[0]
        uploads.append(
            {
                "storedName": stored_name,
                "name": upload.get("name") or display_upload_name(path.name),
                "path": str(path.resolve()),
                "size": path.stat().st_size,
                "contentType": content_type,
            }
        )
    return {"uploads": uploads}


def delete_upload(
    stored_name: str,
    *,
    upload_dir: Path = UPLOAD_DIR,
    upload_store: UploadStore | None = None,
) -> dict:
    if not stored_name:
        raise ValidationError("upload name is required")
    root = upload_dir.resolve()
    target = (root / stored_name).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValidationError("upload path is outside the upload directory")
    if not target.is_file():
        raise NotFoundError(f"upload {stored_name} was not found")
    target.unlink()
    if upload_store is not None:
        upload_store.delete_upload_metadata(stored_name)
    return {"storedName": stored_name, "deleted": True}


def display_upload_name(stored_name: str) -> str:
    match = re.match(r"^[0-9a-f]{12}_(.+)$", stored_name)
    return match.group(1) if match else stored_name


def sanitize_upload_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name.strip("._")
    if not name:
        return "upload.bin"
    if len(name) > 120:
        suffix = "".join(Path(name).suffixes)
        stem = name[: max(1, 120 - len(suffix))]
        name = f"{stem}{suffix}" if suffix else stem
    return name


def request_is_public(method: str, path: str) -> bool:
    parts = [part for part in urlparse(path).path.split("/") if part]
    return method == "GET" and parts in (["health"], ["config"], ["openapi.json"])


def request_is_authorized(headers, auth_token: str) -> bool:
    if not auth_token:
        return True
    expected = auth_token.strip()
    if not expected:
        return True
    authorization = headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()
        if hmac.compare_digest(candidate, expected):
            return True
    header_token = headers.get("X-Online-OBS-Token", "").strip()
    return bool(header_token and hmac.compare_digest(header_token, expected))


def content_type_allowed(content_type: str, allowed_types: tuple[str, ...]) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    for allowed in allowed_types:
        pattern = allowed.strip().lower()
        if not pattern:
            continue
        if pattern == "*/*":
            return True
        if pattern.endswith("/*") and media_type.startswith(pattern[:-1]):
            return True
        if media_type == pattern:
            return True
    return False


def serve(
    host: str,
    port: int,
    *,
    db_path: str | Path | None = None,
    upload_dir: str | Path | None = None,
    gst_plugin_dir: str | Path | None = AppConfig().gst_plugin_dir,
    hls_host: str = "127.0.0.1",
    hls_port: int = 8888,
    auth_token: str = "",
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
    allowed_upload_types: tuple[str, ...] = DEFAULT_ALLOWED_UPLOAD_TYPES,
) -> OnlineObsServer:
    config = AppConfig(
        host=host,
        port=port,
        upload_dir=Path(upload_dir).expanduser() if upload_dir else UPLOAD_DIR,
        db_path=Path(db_path).expanduser() if db_path else None,
        gst_plugin_dir=Path(gst_plugin_dir).expanduser() if gst_plugin_dir else None,
        hls_host=hls_host,
        hls_port=hls_port,
        auth_token=auth_token,
        max_upload_bytes=max_upload_bytes,
        allowed_upload_types=allowed_upload_types,
    )
    store = SQLiteSessionStore(config.db_path) if config.db_path else None
    engine = SessionEngine(store=store, gst_plugin_dir=config.gst_plugin_dir)
    server = OnlineObsServer((config.host, config.port), Handler, engine, config, upload_store=store)
    print(f"online-obs API listening on http://{config.host}:{config.port}", flush=True)
    server.serve_forever()
    return server


def main() -> None:
    env_config = AppConfig.from_env()
    parser = argparse.ArgumentParser(description="Run the Online OBS API service.")
    parser.add_argument("--host", default=env_config.host)
    parser.add_argument("--port", default=env_config.port, type=int)
    parser.add_argument(
        "--db",
        default=str(env_config.db_path) if env_config.db_path else "",
        help="SQLite database path for persistent session definitions.",
    )
    parser.add_argument("--upload-dir", default=str(env_config.upload_dir))
    parser.add_argument(
        "--gst-plugin-dir",
        default=str(env_config.gst_plugin_dir) if env_config.gst_plugin_dir else "",
        help="Directory for a constrained GStreamer plugin path. Use an empty value to disable.",
    )
    parser.add_argument("--hls-host", default=env_config.hls_host)
    parser.add_argument("--hls-port", default=env_config.hls_port, type=int)
    parser.add_argument(
        "--auth-token",
        default=env_config.auth_token,
        help="Optional bearer token required for non-public API routes.",
    )
    parser.add_argument("--max-upload-bytes", default=env_config.max_upload_bytes, type=int)
    parser.add_argument(
        "--allowed-upload-types",
        default=",".join(env_config.allowed_upload_types),
        help="Comma-separated media types accepted by uploads, with wildcards like video/*.",
    )
    args = parser.parse_args()
    serve(
        args.host,
        args.port,
        db_path=args.db or None,
        upload_dir=args.upload_dir,
        gst_plugin_dir=args.gst_plugin_dir or None,
        hls_host=args.hls_host,
        hls_port=args.hls_port,
        auth_token=args.auth_token,
        max_upload_bytes=args.max_upload_bytes,
        allowed_upload_types=tuple(item.strip() for item in args.allowed_upload_types.split(",") if item.strip()),
    )
