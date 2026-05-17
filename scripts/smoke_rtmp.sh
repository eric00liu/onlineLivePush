#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://127.0.0.1:8080}"
API_TOKEN="${API_TOKEN:-${ONLINE_OBS_AUTH_TOKEN:-}}"
STREAM_NAME="${STREAM_NAME:-harness-smoke-rtmp-$$}"
BACKEND="${BACKEND:-gstreamer}"
RTMP_URL="${RTMP_URL:-rtmp://127.0.0.1:1935/live/$STREAM_NAME}"
PUBLISH_RTMP_URL="${PUBLISH_RTMP_URL:-$RTMP_URL}"
PROBE_RTMP_URL="${PROBE_RTMP_URL:-$RTMP_URL}"
HLS_URL="${HLS_URL:-http://127.0.0.1:8888/live/$STREAM_NAME/index.m3u8}"
PROBE_FILE="$(mktemp "${TMPDIR:-/tmp}/online_obs_smoke_rtmp_probe.XXXXXX")"
HLS_FILE="$(mktemp "${TMPDIR:-/tmp}/online_obs_smoke_rtmp_hls.XXXXXX")"
CURL_AUTH_ARGS=()
if [[ -n "$API_TOKEN" ]]; then
  CURL_AUTH_ARGS=(-H "Authorization: Bearer $API_TOKEN")
fi

require_cmd() {
  command -v "$1" >/dev/null || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd ffprobe

cleanup() {
  curl --noproxy '*' --silent "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions/$STREAM_NAME/stop" >/dev/null || true
  curl --noproxy '*' --silent "${CURL_AUTH_ARGS[@]}" -X DELETE "$API_URL/sessions/$STREAM_NAME" >/dev/null || true
  rm -f "$PROBE_FILE" "$HLS_FILE"
}
trap cleanup EXIT

echo "== checking API =="
if ! curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" "$API_URL/health" >/dev/null; then
  echo "API is not reachable at $API_URL; start it with: python3 -m online_obs --host 127.0.0.1 --port 8080" >&2
  exit 1
fi

echo "== creating smoke session =="
curl --noproxy '*' --silent "${CURL_AUTH_ARGS[@]}" -X DELETE "$API_URL/sessions/$STREAM_NAME" >/dev/null || true
curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"id\":\"$STREAM_NAME\",
    \"canvas\":{\"width\":1280,\"height\":720,\"fps\":30},
    \"output\":{\"type\":\"rtmp\",\"url\":\"$PUBLISH_RTMP_URL\",\"bitrateKbps\":2200}
  }" >/dev/null

curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions/$STREAM_NAME/sources" \
  -H 'Content-Type: application/json' \
  -d '{"id":"camera","type":"testsrc","pattern":"smpte"}' >/dev/null

curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X PUT "$API_URL/sessions/$STREAM_NAME/scene" \
  -H 'Content-Type: application/json' \
  -d '{"layers":[{"id":"camera-layer","sourceId":"camera","x":0,"y":0,"width":1280,"height":720,"zIndex":0}]}' >/dev/null

echo "== starting stream =="
curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions/$STREAM_NAME/start" \
  -H 'Content-Type: application/json' \
  -d "{\"backend\":\"$BACKEND\"}" >/dev/null

echo "== probing RTMP =="
sleep 2
if ! ffprobe -v error \
  -show_entries stream=codec_type,codec_name,width,height,sample_rate,channels \
  -of json \
  "$PROBE_RTMP_URL" >"$PROBE_FILE"; then
  echo "RTMP probe failed for $PROBE_RTMP_URL; check that MediaMTX is listening on the expected host port." >&2
  exit 1
fi

grep -q '"codec_name": "h264"' "$PROBE_FILE"
grep -q '"codec_name": "aac"' "$PROBE_FILE"

echo "== checking HLS endpoint =="
if ! curl --noproxy '*' --silent --fail --location --max-time 10 "$HLS_URL" >"$HLS_FILE"; then
  echo "HLS fetch failed for $HLS_URL; check that MediaMTX HLS is listening on port 8888." >&2
  exit 1
fi
grep -q '#EXTM3U' "$HLS_FILE"

echo "smoke_rtmp complete"
