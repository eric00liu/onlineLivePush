# Project State

Last updated: 2026-05-17 Asia/Shanghai

## Current Phase

0.2 Local Stable.

## Current Focus

Current task: none. Last completed tasks: `docker-compose-basic-stack`, `sqlite-session-store`, `sqlite-upload-metadata`, `status-polling`, `file-source-looping`, `openapi-schema`, `config-system`, `docker-gstreamer-runtime`, `visual-canvas-editor`, `real-audio-input`, `auth-and-security`, `ci-and-release`.

Harness hardening, upload material library, basic Docker Compose, SQLite persistence, status polling, file-source looping, OpenAPI documentation, runtime configuration, the GStreamer Compose runtime, visual canvas layer editing, real audio input/mixing, local auth/security hardening, and CI/release scaffolding are complete. There are no open backlog tasks.

## Completed

- Python stdlib API service.
- Web console served from the API process.
- Session CRUD and in-memory state.
- Source CRUD for supported MVP source types.
- Scene and layer configuration.
- GStreamer RTMP push with H264 video and silent AAC fallback audio.
- GStreamer RTMP output can mix durable `audio` sources through `audiomixer` with per-source volume and optional `loop`.
- FFmpeg fallback backend for generated test video/audio to RTMP.
- MediaMTX local RTMP/HLS workflow.
- HLS auto-preview in the console using local HLS.js.
- Console polls the selected session, updates status/preview automatically, and surfaces logs when a stream exits.
- File and audio sources support a `loop` flag, the console exposes a loop toggle, and GStreamer file-source live smoke passes.
- OpenAPI JSON is stored in `docs/openapi.json` and served from `/openapi.json`.
- Runtime configuration is centralized in `AppConfig`, can be set through environment variables or CLI flags, and is exposed to the console through `GET /config`.
- A GStreamer-capable Docker image and Compose override can publish a real GStreamer stream to MediaMTX.
- The console has a visual canvas editor for selecting, dragging, and resizing scene layers while keeping table inputs as the precise fallback.
- Optional bearer-token auth protects non-public API routes when configured, while the default localhost workflow remains unauthenticated.
- Upload size/media-type limits are configurable and enforced before files are stored under the isolated upload directory.
- GitHub Actions CI and release workflows exist for repository checks and GHCR Docker image publishing.
- `CHANGELOG.md` and `docs/release.md` document release contents and operations.
- Process stderr capture and logs endpoint.
- Restart endpoint to apply updated session configuration.
- Upload endpoint and front-end upload wiring have been implemented.
- SQLite persistence can be enabled with `--db` or `ONLINE_OBS_DB` for session definitions, outputs, sources, scenes, and animations.
- SQLite persistence also preserves uploaded asset original names and content types while keeping directory fallback.
- Docker Compose starts API + MediaMTX with a lean API image and persistent data/upload volumes.
- Unit tests currently cover engine and service behavior.
- Repository-local harness files exist under `.harness/`.
- Harness can resume `[~]` in-progress tasks before selecting new work.
- Harness now requires a Decomposition Gate before implementing broad tasks.
- Upload material library API and UI exist for listing, selecting, saving, and deleting uploaded files.

## Last Modified Areas

- `.git/` initialized for local status tracking. No baseline commit has been made.
- `.harness/RUNBOOK.md`, `.harness/BACKLOG.md`, `.harness/STATE.md`, `.harness/DECISIONS.md`.
- `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `CHANGELOG.md`, `docs/release.md`.
- `scripts/harness_next.py`, `scripts/dev_check.sh`, `scripts/smoke_rtmp.sh`, `scripts/smoke_upload_file.sh`, `scripts/smoke_audio_mix.sh`.
- `online_obs/service.py`, `tests/test_service.py`.
- `online_obs/config.py`, `online_obs/errors.py`, `tests/test_config.py`.
- `online_obs/storage.py`, `tests/test_storage.py`.
- `Dockerfile`, `Dockerfile.gstreamer`, `docker-compose.yml`, `docker-compose.gstreamer.yml`, `.dockerignore`, `.gitignore`.
- `online_obs/static/index.html`, `online_obs/static/app.js`, `online_obs/static/styles.css`.
- `online_obs/models.py`, `online_obs/engine.py`, `online_obs/pipeline.py`, `tests/test_engine.py`.
- `README.md` Docker Compose, SQLite persistence, status polling, long-running harness, uploaded media, audio source, security, CI, and release sections.
- `pyproject.toml` version is `0.2.0`.

## Known Running Local Services

These are development conveniences, not required persistent project state. PIDs are local and ephemeral.

- API: `http://127.0.0.1:8080/` PID `50197`
- MediaMTX RTMP: `rtmp://127.0.0.1:1935/...` PID `93271`
- MediaMTX HLS: `http://127.0.0.1:8888/.../index.m3u8` PID `93271`

## Verification Snapshot

Most recent checks during harness hardening:

- `scripts/harness_next.py` selected `[~] harness-hardening` before completion.
- `bash -n scripts/dev_check.sh scripts/smoke_rtmp.sh scripts/smoke_upload_file.sh` passed.
- `python3 -m py_compile scripts/harness_next.py` passed.
- `scripts/dev_check.sh` passed.
- `scripts/smoke_rtmp.sh` passed and cleaned its dynamic smoke session.
- `scripts/smoke_upload_file.sh` passed with dry-run file-source pipeline verification.
- Old smoke sessions and generated upload artifacts were cleaned.
- `python3 -m unittest` passed with 17 tests after adding upload list/delete coverage.
- `node --check online_obs/static/app.js` passed.
- `scripts/dev_check.sh` passed against the restarted API.
- `scripts/smoke_upload_file.sh` passed against the restarted API, including upload list and delete checks.
- `scripts/smoke_rtmp.sh` passed against the restarted API and MediaMTX.
- Browser verification passed for material library rendering, selecting an uploaded asset, saving it as a `file` source, and deleting it.
- Screenshot saved at `artifacts/upload-material-library-page.png`.
- `python3 -m unittest` passed with 20 tests after adding SQLite session persistence coverage.
- `node --check online_obs/static/app.js` passed.
- `bash -n scripts/dev_check.sh scripts/smoke_rtmp.sh scripts/smoke_upload_file.sh scripts/smoke_compose.sh` passed.
- `docker compose config` passed.
- `ONLINE_OBS_API_PORT=18080 ONLINE_OBS_RTMP_PORT=11935 ONLINE_OBS_HLS_PORT=18888 docker compose up -d --build` passed.
- `ONLINE_OBS_API_PORT=18080 ONLINE_OBS_RTMP_PORT=11935 ONLINE_OBS_HLS_PORT=18888 scripts/smoke_compose.sh` passed.
- Manual SQLite restart check passed on port `18081`: session `persist-smoke` reloaded with source pattern `snow`, status `idle`, and no persisted pipeline.
- `scripts/dev_check.sh` passed with 20 tests.
- `python3 -m unittest` passed with 22 tests after adding upload metadata persistence coverage.
- Manual upload metadata restart check passed on port `18082`: uploaded asset `Second Original.mp4` reloaded with `video/mp4` content type after API restart, then deleted through the API.
- `ONLINE_OBS_API_PORT=18080 ONLINE_OBS_RTMP_PORT=11935 ONLINE_OBS_HLS_PORT=18888 docker compose up -d --build` passed after upload metadata changes.
- `ONLINE_OBS_API_PORT=18080 ONLINE_OBS_RTMP_PORT=11935 ONLINE_OBS_HLS_PORT=18888 scripts/smoke_compose.sh` passed after upload metadata changes.
- `scripts/dev_check.sh` passed with 22 tests.
- `python3 -m unittest` passed with 23 tests after adding process-exit status/log coverage.
- `node --check online_obs/static/app.js` passed after adding status polling.
- `bash -n scripts/dev_check.sh scripts/smoke_rtmp.sh scripts/smoke_upload_file.sh scripts/smoke_compose.sh` passed after status polling.
- Browser verification passed on temporary API `http://127.0.0.1:18083/`: session `poll-smoke` started with FFmpeg, the process was killed externally, the console changed to `poll-smoke · 已退出`, preview changed to `推流已退出`, and the log panel showed the process stderr.
- Screenshot saved at `artifacts/status-polling-exited.png`.
- `scripts/dev_check.sh` passed with 23 tests.
- `python3 -m unittest` passed with 24 tests after adding file source loop coverage.
- `node --check online_obs/static/app.js` passed after adding the loop toggle.
- `bash -n scripts/dev_check.sh scripts/smoke_rtmp.sh scripts/smoke_upload_file.sh scripts/smoke_compose.sh` passed after updating file smoke.
- `API_URL=http://127.0.0.1:18084 LIVE_FILE_SMOKE=1 scripts/smoke_upload_file.sh` passed against a temporary current-code API and existing MediaMTX.
- `scripts/dev_check.sh` passed with 24 tests.
- `python3 -m json.tool docs/openapi.json >/dev/null` passed.
- `python3 -m unittest` passed with 25 tests after adding OpenAPI route coverage.
- `scripts/dev_check.sh` passed with 25 tests.
- `python3 -m unittest` passed with 28 tests after adding runtime configuration coverage.
- `node --check online_obs/static/app.js` passed after wiring the console to `GET /config`.
- `docker compose config` passed after adding runtime configuration environment variables.
- Manual config check passed on temporary API `http://127.0.0.1:18085/config` with `ONLINE_OBS_UPLOAD_DIR`, `ONLINE_OBS_HLS_HOST`, `ONLINE_OBS_HLS_PORT`, and empty `--gst-plugin-dir` overrides.
- `scripts/dev_check.sh` passed with 28 tests.
- `python3 -m json.tool docs/openapi.json >/dev/null` passed after documenting `/config`.
- `python3 -m unittest tests.test_config tests.test_service` passed with 15 focused tests.
- `docker compose -f docker-compose.yml -f docker-compose.gstreamer.yml config` passed.
- `docker compose -f docker-compose.yml -f docker-compose.gstreamer.yml build api` passed after adding BuildKit apt cache and GStreamer plugin self-checks.
- `ONLINE_OBS_API_PORT=18086 ONLINE_OBS_RTMP_PORT=11936 ONLINE_OBS_HLS_PORT=18889 docker compose -f docker-compose.yml -f docker-compose.gstreamer.yml up -d --build` passed.
- `ONLINE_OBS_API_PORT=18086 ONLINE_OBS_RTMP_PORT=11936 ONLINE_OBS_HLS_PORT=18889 BACKEND=gstreamer scripts/smoke_compose.sh` passed against the GStreamer API container.
- The temporary GStreamer Compose stack on ports `18086`, `11936`, and `18889` was shut down with `docker compose ... down`.
- `docker compose build api` passed for the default lean FFmpeg image after adding `docs/` to the image.
- `python3 -m unittest tests.test_engine` passed with 11 focused tests after adding `avenc_aac` raw caps handling.
- Browser verification passed on temporary API `http://127.0.0.1:18087/`: creating sources rendered two canvas layers, dragging a layer updated table X/Y, resizing from the canvas handle updated width/height, and selection metadata/table highlighting stayed in sync.
- Screenshot saved at `artifacts/visual-canvas-editor.png`.
- `scripts/dev_check.sh` passed with 28 tests after adding the visual canvas editor.
- The temporary API on port `18087` was stopped after browser verification.
- `python3 -m unittest tests.test_engine` passed with 14 focused tests after adding `audio` source validation, audio layer rejection, `audiomixer` pipeline generation, and audio-only default video coverage.
- `node --check online_obs/static/app.js` passed after adding audio source controls.
- `bash -n scripts/smoke_audio_mix.sh scripts/dev_check.sh` passed.
- `python3 -m json.tool docs/openapi.json >/dev/null` passed after adding the `audio` source schema and pipeline metadata.
- `scripts/dev_check.sh` passed with 31 tests after adding real audio input and mixing.
- `API_URL=http://127.0.0.1:18088 scripts/smoke_audio_mix.sh` passed against a temporary current-code API with dry-run GStreamer audio-mix verification.
- Browser verification passed on temporary API `http://127.0.0.1:18088/`: audio upload switched the source form to `audio`, the volume control was visible before save, the saved audio source appeared in the source list, and the canvas/layer table rendered only the visual camera layer.
- Screenshot saved at `artifacts/real-audio-input.png`.
- `API_URL=http://127.0.0.1:18088 LIVE_AUDIO_SMOKE=1 scripts/smoke_audio_mix.sh` passed against the temporary current-code API and existing MediaMTX, proving the GStreamer audio-mix pipeline starts.
- The temporary API on port `18088` was stopped after browser and audio smoke verification.
- `python3 -m unittest tests.test_config tests.test_service` passed with 17 focused tests after adding optional auth, upload limits, content-type validation, and upload path isolation checks.
- `node --check online_obs/static/app.js` passed after adding the API Token field and bearer-token header wiring.
- `python3 -m json.tool docs/openapi.json >/dev/null` passed after adding auth/upload-limit public config fields and the bearer auth security scheme.
- Direct HTTP verification on temporary API `http://127.0.0.1:18089/` with `--auth-token secret-token` passed: `/sessions` returned `401` without auth and `200` with `Authorization: Bearer secret-token`; `/config` stayed public and reported `authRequired: true`.
- Browser verification passed on temporary API `http://127.0.0.1:18089/`: entering `secret-token` in the API Token field allowed refresh and session creation, and the token was stored in `sessionStorage`.
- Screenshot saved at `artifacts/auth-and-security.png`.
- Upload limit verification on temporary API `http://127.0.0.1:18089/` passed: a >4096 byte upload returned `413`, and a `text/plain` upload returned `400`.
- `scripts/dev_check.sh` passed with 33 tests after auth/security hardening.
- `API_URL=http://127.0.0.1:18090 API_TOKEN=secret-token scripts/smoke_audio_mix.sh` passed against a token-protected temporary current-code API, proving smoke scripts can use bearer auth.
- Temporary APIs on ports `18089` and `18090` were stopped after verification.
- `ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path); puts "ok #{path}" }' .github/workflows/ci.yml .github/workflows/release.yml` passed.
- `docker compose config` passed.
- `docker compose -f docker-compose.yml -f docker-compose.gstreamer.yml config` passed.
- `python3 -m json.tool docs/openapi.json >/dev/null` passed after CI/release documentation updates.
- `scripts/dev_check.sh` passed with 33 tests after adding CI/release assets.
- Final completion audit passed: `rg -n "^- \[ \]|^- \[~\]" .harness/BACKLOG.md` returned no task lines, and `scripts/harness_next.py` reported `No open or in-progress backlog tasks found.`
- Final `scripts/dev_check.sh` passed with 33 tests.
- Final `python3 -m json.tool docs/openapi.json >/dev/null`, `docker compose config >/dev/null`, and `docker compose -f docker-compose.yml -f docker-compose.gstreamer.yml config >/dev/null` passed.
- `python3 -m unittest tests.test_engine` passed with 15 focused tests after adding `audio.loop` normalization, pipeline metadata, and clean-exit restart coverage.
- `API_URL=http://127.0.0.1:18091 scripts/smoke_audio_mix.sh` passed with a looping audio source and `loopingSources` assertion.
- Browser verification passed on temporary API `http://127.0.0.1:18091/`: selecting `audio` showed the loop checkbox, saving an audio source persisted `loop: true`, and the source list showed `loop`.
- Screenshot saved at `artifacts/audio-loop-ui.png`.
- `scripts/dev_check.sh` passed with 34 tests after adding audio source loop support.

## Active Caveats

- State is in memory unless `--db` or `ONLINE_OBS_DB` is set.
- Uploaded files are stored locally in `uploads/`; files without SQLite metadata still use directory-derived display metadata.
- File/audio-source looping restarts the GStreamer pipeline at source end; it is not seamless frame-accurate looping yet.
- Scene updates still require `restart` to apply to a running stream.
- RTMP output mixes configured `audio` sources; video-only generated pipelines still use silent AAC fallback.
- Git has been initialized, but all project files remain untracked until an initial commit is intentionally created.

## Recovery Notes

- Read `.harness/RUNBOOK.md` first, then run `scripts/harness_next.py`.
- If API or MediaMTX are no longer running, restart them before live smoke tests.
- Preserve user changes and inspect `git status --short` before editing.

## Next Recommended Task

No open backlog tasks remain. Final completion audit has passed; the thread goal can be marked complete.
