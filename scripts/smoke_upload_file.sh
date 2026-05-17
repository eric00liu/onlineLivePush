#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://127.0.0.1:8080}"
API_TOKEN="${API_TOKEN:-${ONLINE_OBS_AUTH_TOKEN:-}}"
STREAM_NAME="${STREAM_NAME:-harness-smoke-upload-$$}"
RTMP_URL="${RTMP_URL:-rtmp://127.0.0.1:1935/live/$STREAM_NAME}"
PUBLISH_RTMP_URL="${PUBLISH_RTMP_URL:-$RTMP_URL}"
PROBE_RTMP_URL="${PROBE_RTMP_URL:-$RTMP_URL}"
HLS_URL="${HLS_URL:-http://127.0.0.1:8888/live/$STREAM_NAME/index.m3u8}"
LIVE_FILE_SMOKE="${LIVE_FILE_SMOKE:-0}"
CREATED_SAMPLE_BASE=""
if [[ -z "${SAMPLE_FILE:-}" ]]; then
  CREATED_SAMPLE_BASE="$(mktemp "${TMPDIR:-/tmp}/online_obs_harness_upload.XXXXXX")"
  SAMPLE_FILE="$CREATED_SAMPLE_BASE.mp4"
fi
SOURCE_JSON="$(mktemp "${TMPDIR:-/tmp}/online_obs_upload_source.XXXXXX")"
HLS_FILE="$(mktemp "${TMPDIR:-/tmp}/online_obs_smoke_upload_hls.XXXXXX")"
UPLOAD_PATH=""
UPLOAD_STORED_NAME=""
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
require_cmd ffmpeg
require_cmd python3

cleanup() {
  curl --noproxy '*' --silent "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions/$STREAM_NAME/stop" >/dev/null || true
  curl --noproxy '*' --silent "${CURL_AUTH_ARGS[@]}" -X DELETE "$API_URL/sessions/$STREAM_NAME" >/dev/null || true
  if [[ -n "$UPLOAD_STORED_NAME" ]]; then
    curl --noproxy '*' --silent "${CURL_AUTH_ARGS[@]}" -X DELETE "$API_URL/uploads/$UPLOAD_STORED_NAME" >/dev/null || true
  elif [[ -n "$UPLOAD_PATH" ]]; then
    rm -f "$UPLOAD_PATH"
  fi
  if [[ -n "$CREATED_SAMPLE_BASE" ]]; then
    rm -f "$CREATED_SAMPLE_BASE" "$SAMPLE_FILE"
  fi
  rm -f "$SOURCE_JSON" "$HLS_FILE"
}
trap cleanup EXIT

echo "== creating sample upload file =="
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i testsrc2=size=640x360:rate=30 \
  -t 10 \
  -pix_fmt yuv420p \
  "$SAMPLE_FILE"

echo "== checking API =="
if ! curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" "$API_URL/health" >/dev/null; then
  echo "API is not reachable at $API_URL; start it with: python3 -m online_obs --host 127.0.0.1 --port 8080" >&2
  exit 1
fi

echo "== uploading sample file =="
UPLOAD_JSON="$(curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/uploads" \
  -F "file=@$SAMPLE_FILE;type=video/mp4")"
UPLOAD_PATH="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["path"])' <<<"$UPLOAD_JSON")"
UPLOAD_STORED_NAME="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["storedName"])' <<<"$UPLOAD_JSON")"
test -f "$UPLOAD_PATH"

echo "== checking uploaded asset list =="
ASSETS_JSON="$(curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" "$API_URL/uploads")"
python3 -c 'import json,sys; data=json.load(sys.stdin); name=sys.argv[1]; assert any(item["storedName"] == name for item in data["uploads"])' "$UPLOAD_STORED_NAME" <<<"$ASSETS_JSON"

echo "== creating file-source session =="
curl --noproxy '*' --silent "${CURL_AUTH_ARGS[@]}" -X DELETE "$API_URL/sessions/$STREAM_NAME" >/dev/null || true
curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"id\":\"$STREAM_NAME\",
    \"canvas\":{\"width\":1280,\"height\":720,\"fps\":30},
    \"output\":{\"type\":\"rtmp\",\"url\":\"$PUBLISH_RTMP_URL\",\"bitrateKbps\":2200}
  }" >/dev/null

python3 - "$UPLOAD_PATH" >"$SOURCE_JSON" <<'PY'
import json
import sys

print(json.dumps({"id": "uploaded_clip", "type": "file", "uri": sys.argv[1], "loop": True}))
PY

curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions/$STREAM_NAME/sources" \
  -H 'Content-Type: application/json' \
  -d @"$SOURCE_JSON" >/dev/null

curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X PUT "$API_URL/sessions/$STREAM_NAME/scene" \
  -H 'Content-Type: application/json' \
  -d '{"layers":[{"id":"uploaded-clip-layer","sourceId":"uploaded_clip","x":0,"y":0,"width":1280,"height":720,"zIndex":0}]}' >/dev/null

echo "== verifying generated file-source pipeline =="
PIPELINE_JSON="$(curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions/$STREAM_NAME/start" \
  -H 'Content-Type: application/json' \
  -d '{"backend":"gstreamer","dryRun":true}')"
grep -F -q "$UPLOAD_PATH" <<<"$PIPELINE_JSON"
grep -q '"backend": "gstreamer"' <<<"$PIPELINE_JSON"
grep -F -q '"loopingSources": ["uploaded_clip"]' <<<"$PIPELINE_JSON"

if [[ "$LIVE_FILE_SMOKE" != "1" ]]; then
  echo "LIVE_FILE_SMOKE=0; skipping live file-source push"
  echo "== deleting uploaded asset =="
  curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X DELETE "$API_URL/uploads/$UPLOAD_STORED_NAME" >/dev/null
  UPLOAD_STORED_NAME=""
  test ! -f "$UPLOAD_PATH"
  echo "smoke_upload_file complete"
  exit 0
fi

echo "== starting stream =="
curl --noproxy '*' --silent --fail "${CURL_AUTH_ARGS[@]}" -X POST "$API_URL/sessions/$STREAM_NAME/start" \
  -H 'Content-Type: application/json' \
  -d '{"backend":"gstreamer"}' >/dev/null

echo "== checking HLS endpoint =="
for attempt in 1 2 3 4 5; do
  sleep 2
  if curl --noproxy '*' --silent --fail --location --max-time 8 "$HLS_URL" >"$HLS_FILE"; then
    break
  fi
  if [[ "$attempt" = "5" ]]; then
    echo "HLS fetch failed for $HLS_URL; check MediaMTX and file-source negotiation." >&2
    exit 1
  fi
done
if [[ ! -s "$HLS_FILE" ]]; then
  echo "HLS fetch failed for $HLS_URL; check MediaMTX and file-source negotiation." >&2
  exit 1
fi
grep -q '#EXTM3U' "$HLS_FILE"

echo "smoke_upload_file complete"
