from __future__ import annotations

import shlex
from dataclasses import dataclass

from .errors import ValidationError


@dataclass(frozen=True)
class FfmpegPlan:
    args: list[str]

    @property
    def command(self) -> str:
        return shlex.join(self.args)

    def to_dict(self) -> dict:
        return {"backend": "ffmpeg", "args": self.args, "command": self.command}


def build_ffmpeg_pipeline(session) -> FfmpegPlan:
    if session.output["type"] != "rtmp":
        raise ValidationError("ffmpeg backend currently requires output.type=rtmp")

    scene = session.scene or {"canvas": session.canvas, "layers": []}
    canvas = scene["canvas"]
    visible_layers = [layer for layer in scene["layers"] if layer["visible"]]
    if not visible_layers:
        return _testsrc_plan(canvas, session.output["url"], session.output["bitrateKbps"])

    base_layer = visible_layers[0]
    source = session.sources.get(base_layer["sourceId"])
    if source is None:
        raise ValidationError(f"layer {base_layer['id']} references unknown source {base_layer['sourceId']}")
    if source["type"] != "testsrc":
        raise ValidationError("ffmpeg backend MVP currently supports testsrc as the base video source")

    return _testsrc_plan(canvas, session.output["url"], session.output["bitrateKbps"])


def _testsrc_plan(canvas: dict, output_url: str, bitrate_kbps: int) -> FfmpegPlan:
    size = f"{canvas['width']}x{canvas['height']}"
    rate = str(canvas["fps"])
    bitrate = f"{bitrate_kbps}k"
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-re",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:rate={rate}",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        bitrate,
        "-g",
        str(max(canvas["fps"] * 2, 1)),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-f",
        "flv",
        output_url,
    ]
    return FfmpegPlan(args)
