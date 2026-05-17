#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

require_cmd() {
  command -v "$1" >/dev/null || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

require_cmd python3
require_cmd node
require_cmd curl

echo "== unit tests =="
python3 -m unittest

echo "== frontend syntax =="
node --check online_obs/static/app.js

echo "== script syntax =="
bash -n scripts/smoke_rtmp.sh scripts/smoke_upload_file.sh scripts/smoke_audio_mix.sh scripts/smoke_compose.sh

echo "== release assets =="
test -f .github/workflows/ci.yml
test -f .github/workflows/release.yml
test -f CHANGELOG.md
test -f docs/release.md

echo "== static assets =="
test -f online_obs/static/index.html
test -f online_obs/static/styles.css
test -f online_obs/static/app.js
test -f online_obs/static/vendor/hls.min.js

echo "== optional API health =="
if curl --noproxy '*' --silent --fail --max-time 2 http://127.0.0.1:8080/health >/dev/null; then
  echo "API is healthy at http://127.0.0.1:8080"
else
  echo "API is not running; skipping live health check"
fi

echo "dev_check complete"
