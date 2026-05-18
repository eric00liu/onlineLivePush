#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://127.0.0.1:8080}"
API_TOKEN="${API_TOKEN:-${ONLINE_OBS_AUTH_TOKEN:-}}"
STREAM_NAME="${STREAM_NAME:-harness-smoke-audio-$$}"
RTMP_URL="${RTMP_URL:-rtmp://127.0.0.1:1935/live/$STREAM_NAME}"
LIVE_AUDIO_SMOKE="${LIVE_AUDIO_SMOKE:-0}"
CREATED_BASE_A="$(mktemp "${TMPDIR:-/tmp}/online_obs_audio_a.XXXXXX")"
CREATED_BASE_B="$(mktemp "${TMPDIR:-/tmp}/online_obs_audio_b.XXXXXX")"
SAMPLE_A="$CREATED_BASE_A.wav"
SAMPLE_B="$CREATED_BASE_B.wav"
SOURCE_A_JSON="$(mktemp "${TMPDIR:-/tmp}/online_obs_audio_source_a.XXXXXX")"
SOURCE_B_JSON="$(mktemp "${TMPDIR:-/tmp}/online_obs_audio_source_b.XXXXXX")"
PIPELINE_JSON_FILE="$(mktemp "${TMPDIR:-/tmp}/online_obs_audio_pipeline.XXXXXX")"
UPLOAD_A_PATH=""
UPLOAD_B_PATH=""
UPLOAD_A_STORED_NAME=""
UPLOAD_B_STORED_NAME=""
CURL_API_SILENT=(curl --noproxy '*' --silent)
curl_api() {
  if [[ -n "$API_TOKEN" ]]; then
    "${CURL_API_SILENT[@]}" -H "Authorization: Bearer $API_TOKEN" "$@"
  else
    "${CURL_API_SILENT[@]}" "$@"
  fi
}

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
  curl_api -X POST "$API_URL/sessions/$STREAM_NAME/stop" >/dev/null || true
  curl_api -X DELETE "$API_URL/sessions/$STREAM_NAME" >/dev/null || true
  if [[ -n "$UPLOAD_A_STORED_NAME" ]]; then
    curl_api -X DELETE "$API_URL/uploads/$UPLOAD_A_STORED_NAME" >/dev/null || true
  fi
  if [[ -n "$UPLOAD_B_STORED_NAME" ]]; then
    curl_api -X DELETE "$API_URL/uploads/$UPLOAD_B_STORED_NAME" >/dev/null || true
  fi
  rm -f "$CREATED_BASE_A" "$CREATED_BASE_B" "$SAMPLE_A" "$SAMPLE_B" "$SOURCE_A_JSON" "$SOURCE_B_JSON" "$PIPELINE_JSON_FILE"
}
trap cleanup EXIT

echo "== creating sample audio files =="
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i sine=frequency=440:duration=15 \
  -ac 2 -ar 44100 "$SAMPLE_A"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i sine=frequency=660:duration=15 \
  -ac 2 -ar 44100 "$SAMPLE_B"

echo "== checking API =="
if ! curl_api --fail "$API_URL/health" >/dev/null; then
  echo "API is not reachable at $API_URL; start it with: python3 -m online_obs --host 127.0.0.1 --port 8080" >&2
  exit 1
fi

echo "== uploading sample audio files =="
UPLOAD_A_JSON="$(curl_api --fail -X POST "$API_URL/uploads" \
  -F "file=@$SAMPLE_A;type=audio/wav")"
UPLOAD_B_JSON="$(curl_api --fail -X POST "$API_URL/uploads" \
  -F "file=@$SAMPLE_B;type=audio/wav")"
UPLOAD_A_PATH="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["path"])' <<<"$UPLOAD_A_JSON")"
UPLOAD_B_PATH="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["path"])' <<<"$UPLOAD_B_JSON")"
UPLOAD_A_STORED_NAME="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["storedName"])' <<<"$UPLOAD_A_JSON")"
UPLOAD_B_STORED_NAME="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["storedName"])' <<<"$UPLOAD_B_JSON")"
test -f "$UPLOAD_A_PATH"
test -f "$UPLOAD_B_PATH"

echo "== creating audio-mix session =="
curl_api -X DELETE "$API_URL/sessions/$STREAM_NAME" >/dev/null || true
curl_api --fail -X POST "$API_URL/sessions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"id\":\"$STREAM_NAME\",
    \"canvas\":{\"width\":1280,\"height\":720,\"fps\":30},
    \"output\":{\"type\":\"rtmp\",\"url\":\"$RTMP_URL\",\"bitrateKbps\":2200}
  }" >/dev/null

curl_api --fail -X POST "$API_URL/sessions/$STREAM_NAME/sources" \
  -H 'Content-Type: application/json' \
  -d '{"id":"camera","type":"testsrc","pattern":"smpte"}' >/dev/null

python3 - "$UPLOAD_A_PATH" >"$SOURCE_A_JSON" <<'PY'
import json
import sys

print(json.dumps({"id": "music_a", "type": "audio", "uri": sys.argv[1], "volume": 0.6, "loop": True}))
PY
python3 - "$UPLOAD_B_PATH" >"$SOURCE_B_JSON" <<'PY'
import json
import sys

print(json.dumps({"id": "music_b", "type": "audio", "uri": sys.argv[1], "volume": 1.1}))
PY

curl_api --fail -X POST "$API_URL/sessions/$STREAM_NAME/sources" \
  -H 'Content-Type: application/json' \
  -d @"$SOURCE_A_JSON" >/dev/null
curl_api --fail -X POST "$API_URL/sessions/$STREAM_NAME/sources" \
  -H 'Content-Type: application/json' \
  -d @"$SOURCE_B_JSON" >/dev/null

curl_api --fail -X PUT "$API_URL/sessions/$STREAM_NAME/scene" \
  -H 'Content-Type: application/json' \
  -d '{"layers":[{"id":"camera-layer","sourceId":"camera","x":0,"y":0,"width":1280,"height":720,"zIndex":0}]}' >/dev/null

echo "== verifying generated audio-mix pipeline =="
curl_api --fail -X POST "$API_URL/sessions/$STREAM_NAME/start" \
  -H 'Content-Type: application/json' \
  -d '{"backend":"gstreamer","dryRun":true}' >"$PIPELINE_JSON_FILE"

python3 - "$PIPELINE_JSON_FILE" "$UPLOAD_A_PATH" "$UPLOAD_B_PATH" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
pipeline = payload["session"]["pipeline"]
command = pipeline["command"]
expected_a = Path(sys.argv[2]).resolve().as_uri()
expected_b = Path(sys.argv[3]).resolve().as_uri()

assert pipeline["backend"] == "gstreamer"
assert pipeline["audioSources"] == ["music_a", "music_b"], pipeline
assert pipeline["loopingSources"] == ["music_a"], pipeline
assert "audiomixer name=amix" in command
assert f"uridecodebin uri={expected_a}" in command
assert f"uridecodebin uri={expected_b}" in command
assert "volume volume=0.6" in command
assert "volume volume=1.1" in command
assert "amix.sink_0" in command
assert "amix.sink_1" in command
assert "audiotestsrc is-live=true wave=silence" not in command
PY

if [[ "$LIVE_AUDIO_SMOKE" != "1" ]]; then
  echo "LIVE_AUDIO_SMOKE=0; skipping live audio push"
  echo "smoke_audio_mix complete"
  exit 0
fi

echo "== starting stream =="
curl_api --fail -X POST "$API_URL/sessions/$STREAM_NAME/start" \
  -H 'Content-Type: application/json' \
  -d '{"backend":"gstreamer"}' >/dev/null

echo "smoke_audio_mix complete"
