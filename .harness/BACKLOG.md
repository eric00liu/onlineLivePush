# Backlog

Use this file as the task pool for long-running Codex work. Prefer finishing the first open P0/P1 task before starting lower-priority tasks.

Status markers:

- `[ ]` open
- `[~]` in progress
- `[x]` complete

## P0

- [x] `docker-compose-basic-stack`
  - Goal: provide a stable one-command local stack for contributors using the FFmpeg smoke backend.
  - Acceptance:
    - Docker Compose starts API and MediaMTX.
    - API container can publish a generated test stream to the Compose MediaMTX service.
    - Host can probe RTMP and fetch HLS from the mapped Compose ports.
    - README documents the workflow.
    - Smoke script can run against the Compose stack.
  - Verification:
    - `docker compose up -d --build`
    - `scripts/smoke_compose.sh`

- [x] `sqlite-session-store`
  - Goal: persist session definitions, outputs, sources, scenes, and animations in SQLite.
  - Acceptance:
    - A new engine instance using the same SQLite file reloads session definitions.
    - Runtime-only fields such as process, status, logs, and generated pipeline are not treated as durable state.
    - The API can opt into persistence with a CLI flag or environment variable.
  - Verification:
    - Unit tests for create/update/delete/reload.
    - `scripts/dev_check.sh`

- [x] `sqlite-upload-metadata`
  - Goal: persist uploaded asset metadata in SQLite.
  - Acceptance:
    - Restarting the API preserves original upload filenames and content types.
    - Directory-derived uploads continue to work for files without metadata.
    - Deleting an upload removes both metadata and file data.
  - Verification:
    - Unit tests for upload save/list/delete/reload.
    - Manual restart check.

## P1

- [x] `status-polling`
  - Goal: make the console reflect process exits and stream state without manual refresh.
  - Acceptance:
    - UI polls selected session status.
    - UI preview stops or retries when the backend process exits.
    - Logs are surfaced when a stream exits.

- [x] `file-source-looping`
  - Goal: stabilize video file inputs and add loop controls.
  - Acceptance:
    - Common H264 MP4 files negotiate cleanly through GStreamer.
    - File source can loop indefinitely.
    - UI exposes loop toggle.
    - Pipeline generation reflects the setting.
    - `LIVE_FILE_SMOKE=1 scripts/smoke_upload_file.sh` passes.

- [x] `openapi-schema`
  - Goal: expose API documentation for contributors and clients.
  - Acceptance:
    - OpenAPI JSON is available in the repo.
    - README links to the API reference.
    - Main routes are documented with examples.

- [x] `config-system`
  - Goal: make ports, upload directory, MediaMTX addresses, and GStreamer plugin path configurable.
  - Acceptance:
    - Environment variables work.
    - Defaults preserve current local behavior.
    - Config is documented.

- [x] `docker-gstreamer-runtime`
  - Goal: add a reliable GStreamer-capable API container image after the basic Compose stack is stable.
  - Acceptance:
    - Container includes the GStreamer binaries/plugins needed by the current RTMP pipeline.
    - Docker build is reliable enough for contributor onboarding.
    - Compose or a documented image target can run `scripts/smoke_rtmp.sh` with `BACKEND=gstreamer`.
  - Verification:
    - `docker compose build`
    - `BACKEND=gstreamer scripts/smoke_compose.sh`

## P2

- [x] `visual-canvas-editor`
  - Goal: replace table-only layer editing with drag/resize controls.

- [x] `real-audio-input`
  - Goal: support real audio source input and mixing.

- [x] `auth-and-security`
  - Goal: add local auth, upload limits, path isolation, and deployment safety guidance.
  - Acceptance:
    - Optional bearer-token auth protects sessions, sources, scenes, stream controls, and upload APIs when configured.
    - Default local development remains unauthenticated.
    - Upload size and media type limits are configurable and enforced server-side.
    - Upload file writes, listing, and deletion remain isolated to the configured upload directory.
    - The static console can send the local API token without a frontend build step.
    - README/OpenAPI document security settings and deployment cautions.
  - Verification:
    - Unit tests for config, auth enforcement, upload limits, and upload path isolation.
    - `scripts/dev_check.sh`

- [x] `ci-and-release`
  - Goal: add GitHub Actions, changelog, release workflow, and Docker image publishing.

## Recently Completed

- [x] `upload-material-library`
  - `GET /uploads` returns uploaded files with name, path, size, and content type when available.
  - `DELETE /uploads/{storedName}` deletes one uploaded file safely.
  - Console lists uploaded assets in a material library under input sources.
  - Selecting an asset fills a `file` source path and can be saved as an input source.
  - Browser flow was verified for asset listing, selecting, saving, and deleting.

- [x] `harness-hardening`
  - Repository has git initialized for local status tracking; no baseline commit was made.
  - Harness next-task script prefers `[~]` tasks before new work.
  - Runbook and state files include recovery anchors for long-running work.
  - Smoke scripts use dynamic stream names, clean temporary files, delete smoke sessions, and report missing API/MediaMTX more clearly.

- [x] `hls-auto-preview`
  - Console auto-plays MediaMTX HLS preview after stream start.

- [x] `basic-web-console`
  - Console can configure sessions, inputs, layers, output RTMP, and stream controls.

- [x] `gstreamer-real-rtmp`
  - API starts a real GStreamer process that publishes to MediaMTX.
