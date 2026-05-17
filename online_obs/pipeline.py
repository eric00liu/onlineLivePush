from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .errors import ValidationError


@dataclass(frozen=True)
class PipelinePlan:
    args: list[str]
    metadata: dict = field(default_factory=dict)

    @property
    def command(self) -> str:
        return shlex.join(self.args)

    def to_dict(self) -> dict:
        return {"args": self.args, "command": self.command, **self.metadata}


def build_pipeline(session) -> PipelinePlan:
    scene = session.scene or {"canvas": session.canvas, "layers": []}
    canvas = scene["canvas"]
    session_sources = session.sources
    audio_sources = _audio_sources(session_sources)
    visible_layers = [
        layer
        for layer in scene["layers"]
        if layer["visible"] and session_sources.get(layer["sourceId"], {}).get("type") != "audio"
    ]
    if not visible_layers:
        visible_layers = [{
            "id": "default_testsrc",
            "sourceId": "__default_testsrc__",
            "x": 0,
            "y": 0,
            "width": canvas["width"],
            "height": canvas["height"],
            "alpha": 1.0,
            "zIndex": 0,
            "visible": True,
        }]
        sources = {
            **session_sources,
            "__default_testsrc__": {"id": "__default_testsrc__", "type": "testsrc", "pattern": "smpte"},
        }
    else:
        sources = session_sources

    args = ["gst-launch-1.0", "-e"]
    if session.output["type"] == "rtmp":
        args.extend(_rtmp_mux_chain(session.output))
        args.extend(_compositor_chain(canvas, visible_layers))
        args.extend(_rtmp_video_chain(session.output, canvas))
        if audio_sources:
            args.extend(_audio_mix_output_chain())
        elif not _has_file_source(visible_layers, sources):
            args.extend(_silent_audio_chain())
    else:
        args.extend(_compositor_chain(canvas, visible_layers))
        args.extend(_output_chain(session.output, canvas))
    looping_sources = []
    for index, layer in enumerate(visible_layers):
        source = sources.get(layer["sourceId"])
        if source is None:
            raise ValidationError(f"layer {layer['id']} references unknown source {layer['sourceId']}")
        if source["type"] == "file" and source.get("loop"):
            looping_sources.append(source["id"])
        args.extend(_source_chain(source, layer, canvas, index))
    for index, source in enumerate(audio_sources):
        args.extend(_audio_source_chain(source, index))
    metadata = {}
    if looping_sources:
        metadata["loopingSources"] = looping_sources
    if audio_sources:
        metadata["audioSources"] = [source["id"] for source in audio_sources]
    return PipelinePlan(args, metadata)


def _audio_sources(sources: dict[str, dict]) -> list[dict]:
    return [source for source in sources.values() if source["type"] == "audio"]


def _has_file_source(layers: list[dict], sources: dict[str, dict]) -> bool:
    return any(sources.get(layer["sourceId"], {}).get("type") == "file" for layer in layers)


def _compositor_chain(canvas: dict, layers: list[dict]) -> list[str]:
    chain = ["compositor", "name=comp", "background=black"]
    for index, layer in enumerate(layers):
        chain.extend([
            f"sink_{index}::xpos={layer['x']}",
            f"sink_{index}::ypos={layer['y']}",
            f"sink_{index}::alpha={layer['alpha']}",
        ])
    chain.extend([
        "!",
        f"video/x-raw,width={canvas['width']},height={canvas['height']},framerate={canvas['fps']}/1",
        "!",
        "videoconvert",
    ])
    return chain


def _output_chain(output: dict, canvas: dict) -> list[str]:
    if output["type"] == "fakesink":
        return ["!", "queue", "!", "fakesink", "sync=false"]
    raise ValidationError(f"unsupported output type {output['type']}")


def _rtmp_mux_chain(output: dict) -> list[str]:
    return [
        "flvmux",
        "name=mux",
        "streamable=true",
        "!",
        "rtmpsink",
        f"location={output['url']}",
    ]


def _rtmp_video_chain(output: dict, canvas: dict) -> list[str]:
    key_int_max = max(canvas["fps"] * 2, 1)
    return [
        "!",
        "x264enc",
        "tune=zerolatency",
        "speed-preset=veryfast",
        f"bitrate={output['bitrateKbps']}",
        f"key-int-max={key_int_max}",
        "!",
        "h264parse",
        "!",
        "queue",
        "!",
        "mux.video",
    ]


def _silent_audio_chain() -> list[str]:
    aac_encoder = os.environ.get("ONLINE_OBS_AAC_ENCODER", "fdkaacenc").strip() or "fdkaacenc"
    return [
        "audiotestsrc",
        "is-live=true",
        "wave=silence",
        "!",
        "audioconvert",
        "!",
        "audioresample",
        "!",
        _aac_raw_caps(aac_encoder),
        "!",
        aac_encoder,
        "bitrate=128000",
        "!",
        "aacparse",
        "!",
        "queue",
        "!",
        "mux.audio",
    ]


def _audio_mix_output_chain() -> list[str]:
    aac_encoder = os.environ.get("ONLINE_OBS_AAC_ENCODER", "fdkaacenc").strip() or "fdkaacenc"
    return [
        "audiomixer",
        "name=amix",
        "!",
        "audioconvert",
        "!",
        "audioresample",
        "!",
        _aac_raw_caps(aac_encoder),
        "!",
        aac_encoder,
        "bitrate=128000",
        "!",
        "aacparse",
        "!",
        "queue",
        "!",
        "mux.audio",
    ]


def _aac_raw_caps(aac_encoder: str) -> str:
    if aac_encoder == "avenc_aac":
        return "audio/x-raw,format=F32LE,rate=44100,channels=2"
    return "audio/x-raw,format=S16LE,rate=44100,channels=2"


def _source_chain(source: dict, layer: dict, canvas: dict, index: int) -> list[str]:
    chain = _source_head(source)
    chain.extend([
        "!",
        "queue",
        "!",
        "videoconvert",
        "!",
        "videoscale",
        "!",
    ])
    source_caps = f"video/x-raw,width={layer['width']},height={layer['height']}"
    if source["type"] != "file":
        source_caps = f"{source_caps},framerate={canvas['fps']}/1"
    chain.extend([source_caps, "!"])
    if source["type"] == "file":
        chain.extend([
            "identity",
            "sync=true",
            "!",
        ])
    chain.extend(["queue", "!", f"comp.sink_{index}"])
    return chain


def _audio_source_chain(source: dict, index: int) -> list[str]:
    return [
        "uridecodebin",
        f"uri={_as_uri(source['uri'])}",
        "!",
        "queue",
        "!",
        "audioconvert",
        "!",
        "audioresample",
        "!",
        "audio/x-raw,rate=44100,channels=2",
        "!",
        "volume",
        f"volume={float(source.get('volume', 1.0))}",
        "!",
        "queue",
        "!",
        f"amix.sink_{index}",
    ]


def _source_head(source: dict) -> list[str]:
    source_type = source["type"]
    if source_type == "testsrc":
        return ["videotestsrc", "is-live=true", f"pattern={source.get('pattern', 'smpte')}"]
    if source_type == "file":
        return ["uridecodebin", f"uri={_as_uri(source['uri'])}"]
    if source_type == "image":
        return ["filesrc", f"location={source['uri']}", "!", "decodebin", "!", "imagefreeze"]
    if source_type == "rtmp":
        return ["rtmpsrc", f"location={source['uri']}", "!", "flvdemux", "!", "decodebin"]
    if source_type == "rtsp":
        return ["rtspsrc", f"location={source['uri']}", "latency=200", "!", "decodebin"]
    if source_type == "text":
        return [
            "videotestsrc",
            "is-live=true",
            "pattern=black",
            "!",
            "textoverlay",
            f"text={source['text']}",
            f"font-desc={source['font']}",
            "valignment=center",
            "halignment=center",
        ]
    raise ValidationError(f"unsupported source type {source_type}")


def _as_uri(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme:
        return value
    return Path(value).expanduser().resolve().as_uri()
