from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Protocol

from .errors import ConflictError, ValidationError
from .models import (
    Session,
    normalize_animation,
    normalize_canvas,
    normalize_output,
    normalize_scene,
    normalize_source,
)


class SessionStore(Protocol):
    def load_sessions(self) -> dict[str, Session]:
        ...

    def save_session(self, session: Session) -> None:
        ...

    def delete_session(self, session_id: str) -> None:
        ...


class UploadStore(Protocol):
    def save_upload_metadata(self, upload: dict) -> None:
        ...

    def load_upload_metadata(self) -> dict[str, dict]:
        ...

    def delete_upload_metadata(self, stored_name: str) -> None:
        ...


class SQLiteSessionStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def load_sessions(self) -> dict[str, Session]:
        sessions: dict[str, Session] = {}
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT document FROM sessions ORDER BY id"
            ).fetchall()
        for row in rows:
            session = session_from_document(json.loads(row["document"]))
            sessions[session.id] = session
        return sessions

    def save_session(self, session: Session) -> None:
        document = json.dumps(session_to_document(session), sort_keys=True)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, document, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    document = excluded.document,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (session.id, document),
            )

    def delete_session(self, session_id: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def save_upload_metadata(self, upload: dict) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO uploads (stored_name, name, path, size, content_type, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(stored_name) DO UPDATE SET
                    name = excluded.name,
                    path = excluded.path,
                    size = excluded.size,
                    content_type = excluded.content_type
                """,
                (
                    upload["storedName"],
                    upload["name"],
                    upload["path"],
                    upload["size"],
                    upload.get("contentType"),
                ),
            )

    def load_upload_metadata(self) -> dict[str, dict]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT stored_name, name, path, size, content_type
                FROM uploads
                ORDER BY created_at DESC, stored_name
                """
            ).fetchall()
        return {
            row["stored_name"]: {
                "storedName": row["stored_name"],
                "name": row["name"],
                "path": row["path"],
                "size": row["size"],
                "contentType": row["content_type"],
            }
            for row in rows
        }

    def delete_upload_metadata(self, stored_name: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM uploads WHERE stored_name = ?", (stored_name,))

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    document TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    stored_name TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    content_type TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


def session_to_document(session: Session) -> dict:
    return {
        "id": session.id,
        "canvas": session.canvas,
        "output": session.output,
        "sources": list(session.sources.values()),
        "scene": session.scene or {"canvas": session.canvas, "layers": []},
        "animations": session.animations,
    }


def session_from_document(document: dict) -> Session:
    if not isinstance(document, dict):
        raise ValidationError("session document must be an object")
    session_id = document.get("id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValidationError("session document id must be a non-empty string")

    canvas = normalize_canvas(document.get("canvas"))
    output = normalize_output(document.get("output"))
    session = Session(
        id=session_id.strip(),
        canvas=canvas,
        output=output,
        scene={"canvas": canvas, "layers": []},
    )

    raw_sources = document.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValidationError("session document sources must be an array")
    for raw_source in raw_sources:
        source = normalize_source(raw_source)
        if source["id"] in session.sources:
            raise ConflictError(f"source {source['id']} already exists")
        session.sources[source["id"]] = source

    scene = normalize_scene(document.get("scene", session.scene), session.canvas)
    for layer in scene["layers"]:
        if layer["sourceId"] not in session.sources:
            raise ValidationError(f"layer {layer['id']} references unknown source {layer['sourceId']}")
    session.canvas = scene["canvas"]
    session.scene = scene

    raw_animations = document.get("animations", [])
    if not isinstance(raw_animations, list):
        raise ValidationError("session document animations must be an array")
    layer_ids = {layer["id"] for layer in session.scene.get("layers", [])}
    for raw_animation in raw_animations:
        animation = normalize_animation(raw_animation)
        if animation["layerId"] not in layer_ids:
            raise ValidationError(f"animation references unknown layer {animation['layerId']}")
        session.animations.append(animation)

    return session
