from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        result = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return Path(value).expanduser()


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


@dataclass(frozen=True)
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    upload_dir: Path = ROOT_DIR / "uploads"
    db_path: Path | None = None
    gst_plugin_dir: Path | None = ROOT_DIR / "gst-min-plugins"
    hls_host: str = "127.0.0.1"
    hls_port: int = 8888
    auth_token: str = ""
    max_upload_bytes: int = 1024 * 1024 * 1024
    allowed_upload_types: tuple[str, ...] = ("video/*", "audio/*", "image/*")

    @classmethod
    def from_env(cls) -> "AppConfig":
        db_value = os.environ.get("ONLINE_OBS_DB", "").strip()
        gst_plugin_value = os.environ.get("ONLINE_OBS_GST_PLUGIN_DIR")
        if gst_plugin_value is None:
            gst_plugin_dir = ROOT_DIR / "gst-min-plugins"
        elif gst_plugin_value.strip():
            gst_plugin_dir = Path(gst_plugin_value).expanduser()
        else:
            gst_plugin_dir = None
        return cls(
            host=_env_str("ONLINE_OBS_HOST", "127.0.0.1"),
            port=_env_int("ONLINE_OBS_PORT", 8080),
            upload_dir=_env_path("ONLINE_OBS_UPLOAD_DIR", ROOT_DIR / "uploads"),
            db_path=Path(db_value).expanduser() if db_value else None,
            gst_plugin_dir=gst_plugin_dir,
            hls_host=_env_str("ONLINE_OBS_HLS_HOST", "127.0.0.1"),
            hls_port=_env_int("ONLINE_OBS_HLS_PORT", 8888),
            auth_token=os.environ.get("ONLINE_OBS_AUTH_TOKEN", "").strip(),
            max_upload_bytes=_env_int("ONLINE_OBS_MAX_UPLOAD_BYTES", 1024 * 1024 * 1024, minimum=1),
            allowed_upload_types=_env_csv("ONLINE_OBS_ALLOWED_UPLOAD_TYPES", ("video/*", "audio/*", "image/*")),
        )

    def public_dict(self) -> dict:
        return {
            "hlsHost": self.hls_host,
            "hlsPort": self.hls_port,
            "uploadDir": str(self.upload_dir),
            "dbEnabled": self.db_path is not None,
            "gstPluginDir": str(self.gst_plugin_dir) if self.gst_plugin_dir else "",
            "authRequired": bool(self.auth_token),
            "maxUploadBytes": self.max_upload_bytes,
            "allowedUploadTypes": list(self.allowed_upload_types),
        }
