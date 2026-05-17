#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STREAM_NAME="${STREAM_NAME:-compose-smoke-$$}"
API_URL="${API_URL:-http://127.0.0.1:${ONLINE_OBS_API_PORT:-8080}}"
COMPOSE_MEDIAMTX_IP="${COMPOSE_MEDIAMTX_IP:-10.89.0.10}"
PUBLISH_RTMP_URL="${PUBLISH_RTMP_URL:-rtmp://$COMPOSE_MEDIAMTX_IP:1935/live/$STREAM_NAME}"
PROBE_RTMP_URL="${PROBE_RTMP_URL:-rtmp://127.0.0.1:${ONLINE_OBS_RTMP_PORT:-1935}/live/$STREAM_NAME}"
HLS_URL="${HLS_URL:-http://127.0.0.1:${ONLINE_OBS_HLS_PORT:-8888}/live/$STREAM_NAME/index.m3u8}"
BACKEND="${BACKEND:-ffmpeg}"

export API_URL
export STREAM_NAME
export PUBLISH_RTMP_URL
export PROBE_RTMP_URL
export HLS_URL
export BACKEND

exec scripts/smoke_rtmp.sh
