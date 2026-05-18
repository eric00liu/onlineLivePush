from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from .errors import ConflictError, NotFoundError, ServiceUnavailableError, ValidationError
from .ffmpeg_pipeline import build_ffmpeg_pipeline
from .models import (
    Session,
    normalize_animation,
    normalize_canvas,
    normalize_output,
    normalize_scene,
    normalize_source,
)
from .pipeline import build_pipeline
from .storage import SessionStore


_DEFAULT_GST_PLUGIN_DIR = object()


class SessionEngine:
    def __init__(
        self,
        *,
        gst_binary: str = "gst-launch-1.0",
        store: SessionStore | None = None,
        gst_plugin_dir: str | Path | None | object = _DEFAULT_GST_PLUGIN_DIR,
    ):
        self.gst_binary = gst_binary
        self.store = store
        if gst_plugin_dir is _DEFAULT_GST_PLUGIN_DIR:
            self.gst_plugin_dir = Path(__file__).resolve().parent.parent / "gst-min-plugins"
        else:
            self.gst_plugin_dir = Path(gst_plugin_dir) if gst_plugin_dir else None
        self.sessions: dict[str, Session] = store.load_sessions() if store else {}

    def create_session(self, payload: dict) -> dict:
        session_id = payload.get("id") or f"sess_{uuid4().hex[:12]}"
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValidationError("session.id must be a non-empty string")
        if session_id in self.sessions:
            raise ConflictError(f"session {session_id} already exists")
        canvas = normalize_canvas(payload.get("canvas"))
        output = normalize_output(payload.get("output"))
        session = Session(
            id=session_id.strip(),
            canvas=canvas,
            output=output,
            scene={"canvas": canvas, "layers": []},
        )
        self.sessions[session.id] = session
        self._persist_session(session)
        return session.to_dict()

    def list_sessions(self) -> dict:
        for session in self.sessions.values():
            self._refresh_process_status(session)
        return {"sessions": [session.to_dict() for session in self.sessions.values()]}

    def get_session(self, session_id: str) -> dict:
        return self._get(session_id).to_dict()

    def update_session(self, session_id: str, payload: dict) -> dict:
        session = self._get(session_id)
        if "canvas" in payload:
            session.canvas = normalize_canvas(payload.get("canvas"))
            scene = session.scene or {"layers": []}
            session.scene = {"canvas": session.canvas, "layers": scene.get("layers", [])}
        if "output" in payload:
            session.output = normalize_output(payload.get("output"))
        session.pipeline = None
        self._persist_session(session)
        return session.to_dict()

    def delete_session(self, session_id: str) -> dict:
        session = self._get(session_id)
        if session.status == "running":
            self.stop(session_id)
        del self.sessions[session_id]
        if self.store is not None:
            self.store.delete_session(session_id)
        return {"id": session_id, "deleted": True}

    def add_source(self, session_id: str, payload: dict) -> dict:
        session = self._get(session_id)
        source = normalize_source(payload)
        if source["id"] in session.sources:
            raise ConflictError(f"source {source['id']} already exists")
        session.sources[source["id"]] = source
        self._persist_session(session)
        return session.to_dict()

    def update_source(self, session_id: str, source_id: str, payload: dict) -> dict:
        session = self._get(session_id)
        if source_id not in session.sources:
            raise NotFoundError(f"source {source_id} was not found")
        update_payload = dict(payload)
        update_payload.setdefault("id", source_id)
        source = normalize_source(update_payload)
        if source["id"] != source_id:
            raise ValidationError("source.id cannot be changed")
        session.sources[source_id] = source
        session.pipeline = None
        self._persist_session(session)
        return session.to_dict()

    def delete_source(self, session_id: str, source_id: str) -> dict:
        session = self._get(session_id)
        if source_id not in session.sources:
            raise NotFoundError(f"source {source_id} was not found")
        referenced_by = [
            layer["id"]
            for layer in session.scene.get("layers", [])
            if layer["sourceId"] == source_id
        ]
        if referenced_by:
            raise ValidationError(
                f"source {source_id} is still used by scene layers",
                details={"layers": referenced_by},
            )
        del session.sources[source_id]
        session.pipeline = None
        self._persist_session(session)
        return session.to_dict()

    def set_scene(self, session_id: str, payload: dict) -> dict:
        session = self._get(session_id)
        scene = normalize_scene(payload, session.canvas)
        for layer in scene["layers"]:
            source = session.sources.get(layer["sourceId"])
            if source is None:
                raise ValidationError(f"layer {layer['id']} references unknown source {layer['sourceId']}")
            if source["type"] == "audio":
                raise ValidationError(f"layer {layer['id']} cannot reference audio source {layer['sourceId']}")
        session.canvas = scene["canvas"]
        session.scene = scene
        session.pipeline = None
        self._persist_session(session)
        return session.to_dict()

    def add_animation(self, session_id: str, payload: dict) -> dict:
        session = self._get(session_id)
        animation = normalize_animation(payload)
        layer_ids = {layer["id"] for layer in session.scene.get("layers", [])}
        if animation["layerId"] not in layer_ids:
            raise ValidationError(f"animation references unknown layer {animation['layerId']}")
        session.animations.append(animation)
        self._persist_session(session)
        return session.to_dict()

    def render_pipeline(self, session_id: str) -> dict:
        session = self._get(session_id)
        plan = build_pipeline(session)
        session.pipeline = {"backend": "gstreamer", **plan.to_dict()}
        return session.pipeline

    def start(self, session_id: str, payload: dict) -> dict:
        session = self._get(session_id)
        self._refresh_process_status(session)
        dry_run = bool(payload.get("dryRun", False))
        backend = payload.get("backend", payload.get("engine", "gstreamer"))
        if session.status == "running":
            raise ConflictError(f"session {session.id} is already running")
        if backend == "gstreamer":
            plan = build_pipeline(session)
            binary = self.gst_binary
        elif backend == "ffmpeg":
            plan = build_ffmpeg_pipeline(session)
            binary = "ffmpeg"
        else:
            raise ValidationError("backend must be one of ['gstreamer', 'ffmpeg']")
        plan_dict = plan.to_dict()
        session.pipeline = plan_dict if "backend" in plan_dict else {"backend": backend, **plan_dict}
        if dry_run:
            return {"dryRun": True, "session": session.to_dict()}

        self._launch_process(session, backend, plan.args)
        time.sleep(0.3)
        self._refresh_process_status(session)
        if session.status != "running":
            raise ServiceUnavailableError(
                f"{binary} exited immediately",
                details={"pipeline": session.pipeline, "stderr": self._read_process_log(session)},
            )
        return {"dryRun": False, "session": session.to_dict()}

    def stop(self, session_id: str) -> dict:
        session = self._get(session_id)
        self._refresh_process_status(session)
        if session.status != "running" or session.process is None:
            session.status = "stopped"
            return session.to_dict()
        session.process.terminate()
        try:
            session.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            session.process.kill()
            session.process.wait(timeout=5)
        session.process = None
        session.status = "stopped"
        return session.to_dict()

    def restart(self, session_id: str, payload: dict) -> dict:
        session = self._get(session_id)
        backend = payload.get("backend", payload.get("engine"))
        if backend is None and session.pipeline is not None:
            backend = session.pipeline.get("backend")
        if backend is None:
            backend = "gstreamer"
        if session.status == "running":
            self.stop(session_id)
        next_payload = dict(payload)
        next_payload["backend"] = backend
        return self.start(session_id, next_payload)

    def get_logs(self, session_id: str) -> dict:
        session = self._get(session_id)
        return {"sessionId": session.id, "stderr": self._read_process_log(session)}

    def _get(self, session_id: str) -> Session:
        session = self.sessions.get(session_id)
        if session is None:
            raise NotFoundError(f"session {session_id} was not found")
        self._refresh_process_status(session)
        return session

    def _refresh_process_status(self, session: Session) -> None:
        process = session.process
        if process is None or session.status != "running":
            return
        return_code = process.poll()
        if return_code is not None:
            session.process = None
            if return_code == 0 and self._should_restart_looping_source(session):
                self._append_process_log(session, "\n[online-obs] looping source ended; restarting pipeline\n")
                try:
                    backend = session.pipeline.get("backend", "gstreamer") if session.pipeline else "gstreamer"
                    args = session.pipeline.get("args", []) if session.pipeline else []
                    self._launch_process(session, backend, args, append_log=True)
                    return
                except ServiceUnavailableError:
                    pass
            session.status = "exited"

    def _gstreamer_env(self) -> dict[str, str]:
        env = os.environ.copy()
        plugin_dir = self.gst_plugin_dir
        if plugin_dir is None or not plugin_dir.exists():
            return env
        for key in (
            "GST_PLUGIN_PATH",
            "GST_PLUGIN_SYSTEM_PATH",
            "GST_PLUGIN_PATH_1_0",
            "GST_PLUGIN_SYSTEM_PATH_1_0",
        ):
            env[key] = str(plugin_dir)
        env["GST_REGISTRY"] = "/private/tmp/online-obs-gst-registry.bin"
        return env

    def _persist_session(self, session: Session) -> None:
        if self.store is not None:
            self.store.save_session(session)

    def _launch_process(
        self,
        session: Session,
        backend: str,
        plan_args: list[str],
        *,
        append_log: bool = False,
    ) -> None:
        if not plan_args:
            raise ServiceUnavailableError("pipeline args are missing", details={"pipeline": session.pipeline})
        binary = self.gst_binary if backend == "gstreamer" else "ffmpeg"
        binary_path = shutil.which(binary)
        if binary_path is None:
            raise ServiceUnavailableError(
                f"{binary} was not found; install it or call start with dryRun=true",
                details={"pipeline": session.pipeline},
            )
        args = [binary_path, *plan_args[1:]]
        process_env = self._gstreamer_env() if backend == "gstreamer" else None
        if session.log_path is None or not append_log:
            log_file = tempfile.NamedTemporaryFile(prefix=f"online-obs-{session.id}-", suffix=".log", delete=False)
            session.log_path = log_file.name
        else:
            log_file = open(session.log_path, "ab")
        session.process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=log_file,
            env=process_env,
        )
        log_file.close()
        session.status = "running"

    def _should_restart_looping_source(self, session: Session) -> bool:
        if not session.pipeline or session.pipeline.get("backend") != "gstreamer":
            return False
        looping_sources = set(session.pipeline.get("loopingSources", []))
        if not looping_sources:
            return False
        visible_source_ids = {
            layer["sourceId"]
            for layer in (session.scene or {}).get("layers", [])
            if layer.get("visible", True)
        }
        audio_source_ids = {
            source_id
            for source_id, source in session.sources.items()
            if source.get("type") == "audio"
        }
        return bool(looping_sources & (visible_source_ids | audio_source_ids))

    def _append_process_log(self, session: Session, message: str) -> None:
        if not session.log_path:
            return
        with open(session.log_path, "ab") as file:
            file.write(message.encode("utf-8"))

    def _read_process_log(self, session: Session, *, max_bytes: int = 20000) -> str:
        if not session.log_path:
            return ""
        path = Path(session.log_path)
        if not path.exists():
            return ""
        size = path.stat().st_size
        with path.open("rb") as file:
            if size > max_bytes:
                file.seek(-max_bytes, os.SEEK_END)
            return file.read().decode("utf-8", errors="replace")
