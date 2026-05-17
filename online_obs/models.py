from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .errors import ValidationError

SOURCE_TYPES = {"testsrc", "file", "rtmp", "rtsp", "image", "text", "audio"}
OUTPUT_TYPES = {"rtmp", "fakesink"}


def _as_dict(value: Any, field_name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(f"{field_name} must be an object")
    return value


def _as_int(value: Any, field_name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field_name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{field_name} must be >= {minimum}")
    return value


def _as_number(value: Any, field_name: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(f"{field_name} must be a number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValidationError(f"{field_name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise ValidationError(f"{field_name} must be <= {maximum}")
    return result


def _as_str(value: Any, field_name: str, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")
    return value.strip()


def normalize_canvas(value: Any | None = None) -> dict:
    payload = _as_dict(value, "canvas")
    width = _as_int(payload.get("width", 1920), "canvas.width", minimum=16)
    height = _as_int(payload.get("height", 1080), "canvas.height", minimum=16)
    fps = _as_int(payload.get("fps", 30), "canvas.fps", minimum=1)
    return {"width": width, "height": height, "fps": fps}


def normalize_output(value: Any | None = None) -> dict:
    payload = _as_dict(value, "output")
    output_type = _as_str(payload.get("type", "fakesink"), "output.type")
    if output_type not in OUTPUT_TYPES:
        raise ValidationError(f"output.type must be one of {sorted(OUTPUT_TYPES)}")
    normalized = {"type": output_type}
    if output_type == "rtmp":
        normalized["url"] = _as_str(payload.get("url"), "output.url")
        normalized["bitrateKbps"] = _as_int(payload.get("bitrateKbps", 4000), "output.bitrateKbps", minimum=100)
    return normalized


def normalize_source(value: Any) -> dict:
    payload = _as_dict(value, "source")
    source_type = _as_str(payload.get("type"), "source.type")
    if source_type not in SOURCE_TYPES:
        raise ValidationError(f"source.type must be one of {sorted(SOURCE_TYPES)}")
    source_id = _as_str(payload.get("id", f"src_{uuid4().hex[:8]}"), "source.id")
    source = {"id": source_id, "type": source_type}
    if source_type in {"file", "rtmp", "rtsp", "image", "audio"}:
        source["uri"] = _as_str(payload.get("uri"), "source.uri")
    if source_type == "audio":
        source["volume"] = _as_number(payload.get("volume", 1.0), "source.volume", minimum=0.0, maximum=2.0)
    if source_type == "file":
        source["loop"] = bool(payload.get("loop", False))
    if source_type == "text":
        source["text"] = _as_str(payload.get("text"), "source.text")
        source["font"] = _as_str(payload.get("font", "Sans 42"), "source.font")
    if source_type == "testsrc":
        source["pattern"] = _as_str(payload.get("pattern", "smpte"), "source.pattern")
    return source


def normalize_layer(value: Any, canvas: dict) -> dict:
    payload = _as_dict(value, "layer")
    source_id = _as_str(payload.get("sourceId"), "layer.sourceId")
    layer_id = _as_str(payload.get("id", source_id), "layer.id")
    width = _as_int(payload.get("width", canvas["width"]), "layer.width", minimum=1)
    height = _as_int(payload.get("height", canvas["height"]), "layer.height", minimum=1)
    return {
        "id": layer_id,
        "sourceId": source_id,
        "x": _as_int(payload.get("x", 0), "layer.x"),
        "y": _as_int(payload.get("y", 0), "layer.y"),
        "width": width,
        "height": height,
        "alpha": _as_number(payload.get("alpha", 1.0), "layer.alpha", minimum=0.0, maximum=1.0),
        "zIndex": _as_int(payload.get("zIndex", 0), "layer.zIndex"),
        "visible": bool(payload.get("visible", True)),
    }


def normalize_scene(value: Any, existing_canvas: dict) -> dict:
    payload = _as_dict(value, "scene")
    canvas = normalize_canvas(payload.get("canvas", existing_canvas))
    raw_layers = payload.get("layers", [])
    if not isinstance(raw_layers, list):
        raise ValidationError("scene.layers must be an array")
    layers = [normalize_layer(layer, canvas) for layer in raw_layers]
    return {"canvas": canvas, "layers": sorted(layers, key=lambda item: item["zIndex"])}


def normalize_animation(value: Any) -> dict:
    payload = _as_dict(value, "animation")
    layer_id = _as_str(payload.get("layerId"), "animation.layerId")
    animation_type = _as_str(payload.get("type"), "animation.type")
    duration_ms = _as_int(payload.get("durationMs", 300), "animation.durationMs", minimum=1)
    return {
        "id": _as_str(payload.get("id", f"anim_{uuid4().hex[:8]}"), "animation.id"),
        "layerId": layer_id,
        "type": animation_type,
        "durationMs": duration_ms,
        "params": _as_dict(payload.get("params", {}), "animation.params"),
    }


@dataclass
class Session:
    id: str
    canvas: dict
    output: dict
    sources: dict[str, dict] = field(default_factory=dict)
    scene: dict = field(default_factory=dict)
    animations: list[dict] = field(default_factory=list)
    status: str = "idle"
    pipeline: dict | None = None
    process: object | None = field(default=None, repr=False)
    log_path: str | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "canvas": self.canvas,
            "output": self.output,
            "sources": list(self.sources.values()),
            "scene": self.scene or {"canvas": self.canvas, "layers": []},
            "animations": self.animations,
            "pipeline": self.pipeline,
        }
