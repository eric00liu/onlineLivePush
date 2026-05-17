# syntax=docker/dockerfile:1.7

FROM python:3.11-slim-bookworm

ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN set -eux; \
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy; \
    if [ -n "${TARGETARCH:-}" ]; then \
        ffmpeg_arch="$TARGETARCH"; \
    else \
        case "$(uname -m)" in \
            x86_64) ffmpeg_arch="amd64" ;; \
            aarch64|arm64) ffmpeg_arch="arm64" ;; \
            *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
        esac; \
    fi; \
    case "$ffmpeg_arch" in \
        amd64|arm64) ;; \
        *) echo "unsupported TARGETARCH=$ffmpeg_arch" >&2; exit 1 ;; \
    esac; \
    export FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${ffmpeg_arch}-static.tar.xz"; \
    python3 - <<'PY'
import io
import os
from pathlib import Path
import stat
import tarfile
import urllib.request

archive = urllib.request.urlopen(os.environ["FFMPEG_URL"], timeout=300).read()
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:xz") as tar:
    for binary in ("ffmpeg", "ffprobe"):
        member = next(
            candidate
            for candidate in tar.getmembers()
            if candidate.name.endswith(f"/{binary}")
        )
        source = tar.extractfile(member)
        if source is None:
            raise RuntimeError(f"missing {binary} in archive")
        target = Path("/usr/local/bin") / binary
        target.write_bytes(source.read())
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
PY
RUN ffmpeg -version >/dev/null && ffprobe -version >/dev/null

COPY pyproject.toml README.md ./
COPY online_obs ./online_obs
COPY examples ./examples
COPY docs ./docs

RUN mkdir -p /app/uploads

EXPOSE 8080

CMD ["python3", "-m", "online_obs", "--host", "0.0.0.0", "--port", "8080"]
