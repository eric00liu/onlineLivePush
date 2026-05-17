# Decisions

Record architectural decisions here so future Codex sessions and contributors can recover context quickly.

## 2026-05-17: CI Mirrors Local Harness Checks

Decision: GitHub Actions CI runs the same core checks as `scripts/dev_check.sh`, plus OpenAPI JSON and Docker Compose validation.

Reasoning:

- The project intentionally has a small standard-library-first toolchain.
- CI should prove the same checks contributors run locally instead of introducing a separate build system.
- Compose validation catches container wiring regressions without requiring every PR to build the large GStreamer image.

Consequence:

- `ci.yml` runs on pull requests and pushes to `main` or `release/**`.
- Release verification reuses the same checks before publishing images.
- Heavy live smoke tests remain documented manual/release-candidate checks.

## 2026-05-17: Release Publishes Lean And GStreamer Images

Decision: tagged releases publish a lean API image and a GStreamer runtime image to GHCR, using `Dockerfile` and `Dockerfile.gstreamer` respectively.

Reasoning:

- The lean image is fast enough for default onboarding and FFmpeg smoke checks.
- The GStreamer image is larger and production-oriented, so it should be tagged distinctly.
- GHCR works with the repository `GITHUB_TOKEN` and does not require extra registry credentials for the default path.

Consequence:

- Tags matching `v*.*.*` trigger the release workflow.
- Lean images publish version and `latest` tags.
- GStreamer images publish version tags with a `-gstreamer` suffix.

## 2026-05-17: Local Auth Is Optional Bearer Token Auth

Decision: keep local development unauthenticated by default, and require `Authorization: Bearer <token>` for non-public API routes only when `ONLINE_OBS_AUTH_TOKEN` or `--auth-token` is configured.

Reasoning:

- Contributors should not need a login flow for the default localhost workflow.
- A single local token is enough for protecting operator APIs in a trusted single-user deployment.
- `/health`, `/config`, `/openapi.json`, and static assets need to remain public so the console can load and operators can enter the token.

Consequence:

- The static console stores the token in `sessionStorage` and sends it with API calls.
- Smoke scripts accept `API_TOKEN` or `ONLINE_OBS_AUTH_TOKEN` for protected API routes.
- This is deployment hardening, not a multi-tenant identity system.

## 2026-05-17: Uploads Are Constrained At The HTTP Boundary

Decision: enforce upload size and media type limits before storing the file, then write only sanitized filenames below the configured upload directory.

Reasoning:

- Uploads are the most exposed local file-write surface in the current API.
- Limits should be configurable without code changes.
- The storage path should remain isolated even when original filenames contain traversal or unusual characters.

Consequence:

- `ONLINE_OBS_MAX_UPLOAD_BYTES` and `ONLINE_OBS_ALLOWED_UPLOAD_TYPES` are first-class settings.
- Upload validation returns `413 payload_too_large` for oversized files and `400 validation_error` for blocked media types.
- Uploaded file paths are resolved and checked relative to the configured upload root before writing.

## 2026-05-17: Audio Sources Are Mixed Outside Visual Layers

Decision: `audio` sources are durable session sources but never scene layers; GStreamer mixes them with `audiomixer` into the RTMP mux.

Reasoning:

- The scene canvas is video-only, while audio needs independent source ordering and volume control.
- Keeping audio out of layers prevents the visual editor from generating invalid scene entries.
- The existing silent AAC fallback should remain for video-only RTMP pipelines.

Consequence:

- Source validation owns audio URI and volume fields.
- Scene validation rejects audio sources as layer references.
- GStreamer RTMP pipeline metadata reports `audioSources` when real audio is configured.

## 2026-05-17: Visual Canvas Edits The Existing Scene Table

Decision: the canvas editor is a UI layer over the existing scene table and `PUT /scene` API. Drag and resize operations write the same layer inputs that the table saves.

Reasoning:

- This keeps the backend scene contract stable.
- Operators get direct visual placement without losing precise numeric controls.
- Existing save/restart behavior stays understandable while the console grows.

Consequence:

- The canvas editor and layer table must stay synchronized through shared form inputs.
- Non-visual source types, such as `audio`, must be omitted from visual layer defaults.

## 2026-05-17: GStreamer Runtime Uses A Compose Override

Decision: keep the default Docker Compose API image lean, and add a `Dockerfile.gstreamer` plus `docker-compose.gstreamer.yml` override for the full GStreamer media runtime.

Reasoning:

- The lean image gives contributors a fast FFmpeg smoke path.
- The full GStreamer plugin set is large and apt/CDN failures are common enough to isolate it from the default onboarding path.
- A Compose override lets the same API/MediaMTX stack run the production-oriented backend without duplicating base service configuration.

Consequence:

- Run the GStreamer stack with `docker compose -f docker-compose.yml -f docker-compose.gstreamer.yml up -d --build`.
- The GStreamer image self-checks required plugins during build: `compositor`, `x264enc`, `flvmux`, `rtmpsink`, and `avenc_aac`.
- The Dockerfile uses BuildKit apt cache mounts and download-only retries so flaky package downloads can resume instead of restarting from zero.
- The GStreamer container sets `ONLINE_OBS_GST_PLUGIN_DIR=""` and `ONLINE_OBS_AAC_ENCODER=avenc_aac`.
- `avenc_aac` requires `F32LE` raw audio caps; the local default `fdkaacenc` path keeps `S16LE`.

## 2026-05-17: Central AppConfig For Runtime Settings

Decision: centralize local runtime settings in `AppConfig`, expose a public subset through `GET /config`, and let environment variables feed CLI defaults.

Reasoning:

- Contributors need to move API, upload, MediaMTX, and GStreamer paths without editing code.
- The browser console must derive HLS preview URLs from the same runtime settings as the API.
- Defaults should preserve the existing localhost workflow while still supporting Compose and deployment overrides.

Consequence:

- `ONLINE_OBS_HOST`, `ONLINE_OBS_PORT`, `ONLINE_OBS_UPLOAD_DIR`, `ONLINE_OBS_DB`, `ONLINE_OBS_GST_PLUGIN_DIR`, `ONLINE_OBS_HLS_HOST`, and `ONLINE_OBS_HLS_PORT` are first-class settings.
- An empty `ONLINE_OBS_GST_PLUGIN_DIR` or empty `--gst-plugin-dir` disables the constrained local plugin directory.
- The static console calls `/config` before deriving HLS preview URLs.
- OpenAPI documents `/config` and its public response shape.

## 2026-05-17: File Looping Restarts The Pipeline

Decision: implement file-source looping by restarting the GStreamer process when a looping file source reaches EOS.

Reasoning:

- `gst-launch-1.0` does not expose the application-level `about-to-finish` handling needed for seamless file looping.
- The existing engine already supervises child processes and can recover from a clean file EOS.
- A restart-based loop is good enough for local preview and smoke tests while keeping the Python runtime standard-library-first.

Consequence:

- File sources have a boolean `loop` field.
- GStreamer pipeline metadata includes `loopingSources`.
- The current loop is not frame-seamless; future appsrc/native GStreamer control can improve this.
- RTMP file-source pipelines are video-only for now so file EOS can end the process and trigger the loop supervisor.

## 2026-05-17: SQLite Stores Durable Definitions Only

Decision: persist session definitions in SQLite, but keep process handles, running status, logs, and generated pipeline plans ephemeral.

Reasoning:

- Runtime process state cannot survive an API restart safely.
- Persisting only canvas, output, sources, scenes, and animations gives contributors recovery without implying streams are still running.
- The project can add richer history and process supervision later without corrupting the core session model.

Consequence:

- `--db` and `ONLINE_OBS_DB` enable SQLite persistence.
- Reloaded sessions return to `idle` with `pipeline: null`.
- Uploaded asset metadata is also persisted when the same SQLite store is configured.

## 2026-05-17: SQLite Upload Metadata With Directory Fallback

Decision: persist uploaded asset metadata in SQLite while keeping directory scanning as a fallback for files without metadata.

Reasoning:

- The browser should keep original filenames and content types across API restarts.
- Existing files in `uploads/` should remain usable even if they predate the metadata table.
- File existence remains the source of truth for whether an asset can be listed or deleted.

Consequence:

- Upload save/list/delete accepts an optional upload store.
- `GET /uploads` prefers SQLite metadata when present and falls back to sanitized filenames and MIME guessing.
- `DELETE /uploads/{storedName}` removes both the file and metadata when persistence is enabled.

## 2026-05-17: Two-Step Docker Runtime

Decision: ship the first Docker Compose task with a lean FFmpeg-capable API image, then implement the GStreamer-capable image as a separate backlog task.

Reasoning:

- Docker Compose should become usable for contributors before optimizing the full media runtime image.
- Installing the complete Debian GStreamer plugin set made the image large and repeatedly hit mirror 5xx errors during local builds.
- The existing FFmpeg backend can already publish a generated test stream to MediaMTX, which validates API orchestration, RTMP ingest, and HLS preview paths.

Consequence:

- `scripts/smoke_compose.sh` defaults to `BACKEND=ffmpeg`.
- The API image downloads static `ffmpeg`/`ffprobe` binaries instead of installing Debian media packages.
- Compose gives MediaMTX a fixed internal IP because the static FFmpeg build does not resolve Docker's internal service DNS reliably.
- GStreamer remains the primary project backend for production feature work.
- `docker-gstreamer-runtime` is P1 so unreliable media package installation does not block the P0 maturity path.

## 2026-05-17: Decomposition Gate Before Implementation

Decision: every long-running Codex session must evaluate the selected backlog task with a Decomposition Gate before editing.

Reasoning:

- Some backlog entries are intentionally feature-sized, not turn-sized.
- Splitting too early creates noisy plans, but splitting too late makes recovery brittle.
- A mandatory gate keeps the backlog high-level while still forcing fine-grained work when implementation begins.

Consequence:

- Broad tasks are split in `.harness/BACKLOG.md` before implementation.
- Each split task needs its own `Goal`, `Acceptance`, and `Verification`.
- `scripts/harness_next.py` prints a resume prompt that explicitly includes this gate.

## 2026-05-17: Sticky In-Progress Harness Tasks

Decision: treat `[~]` backlog entries as sticky work that must be resumed before selecting new open tasks.

Reasoning:

- Long Codex runs can be interrupted by compaction or user messages.
- A visible in-repo marker prevents accidental task switching.
- Recovery should be possible by running `scripts/harness_next.py` and reading the state file.

Consequence:

- A session marks exactly one selected task as `[~]` before editing.
- `scripts/harness_next.py` prefers `[~]` P0/P1 work over new `[ ]` work.
- End-of-session state must include verification results and the next acceptance target.

## 2026-05-17: Directory-Derived Upload Library

Decision: expose the upload material library by scanning `uploads/`, with SQLite metadata used when available.

Reasoning:

- The current API is still standard-library-first and in-memory.
- GStreamer file sources already need absolute local paths.
- Directory scanning gives the UI reuse/delete behavior for files that predate metadata or are placed in the upload directory manually.

Consequence:

- `GET /uploads` returns file-derived metadata.
- Original filenames come from SQLite metadata when available; otherwise list output falls back to sanitized stored filenames.
- `DELETE /uploads/{storedName}` must keep path traversal protections.

## 2026-05-17: Repository Harness As Project Memory

Decision: use `.harness/` files as the canonical long-running development memory.

Reasoning:

- Chat context is transient and can be compacted.
- Repo files survive restarts and handoffs.
- Each Codex session can resume by reading a small, stable set of files.

Consequence:

- Every substantial task must update `.harness/STATE.md`.
- Architecture changes should update this file.
- New tasks should be added to `.harness/BACKLOG.md`.

## 2026-05-16: GStreamer As Primary Backend

Decision: use GStreamer as the main runtime backend and keep FFmpeg as a fallback smoke-test backend.

Reasoning:

- GStreamer maps well to compositing, live inputs, muxing, and future appsrc overlays.
- FFmpeg is useful for local generated video/audio smoke tests.

Consequence:

- Production features should target GStreamer first.
- FFmpeg support should stay scoped unless a specific fallback use case is needed.

## 2026-05-16: MediaMTX For Local RTMP/HLS

Decision: use MediaMTX as the local RTMP ingest and HLS preview server.

Reasoning:

- It provides RTMP ingest and HLS output with minimal setup.
- It makes end-to-end verification possible on a local machine.

Consequence:

- Smoke tests may assume MediaMTX is available on `1935` and `8888`.
- Docker Compose should include MediaMTX.

## 2026-05-16: Minimal GStreamer Plugin Directory

Decision: use `gst-min-plugins/` when present to avoid slow or blocked full plugin scans on macOS.

Reasoning:

- Full Homebrew GStreamer plugin scanning can hang or emit GUI/input-service warnings on macOS.
- A small plugin set keeps local startup predictable.

Consequence:

- When new source types require plugins, update `gst-min-plugins/`.
- The configured plugin path should eventually become environment driven.

## 2026-05-16: API-Served Static Console

Decision: serve the control console from the Python API process.

Reasoning:

- The current project has no frontend build system.
- Same-origin API calls simplify local development.
- A static console is enough for the current MVP.

Consequence:

- Keep frontend dependencies minimal and vendored when practical.
- If the console grows substantially, revisit a dedicated frontend toolchain.

## 2026-05-17: Local Upload Storage

Decision: store uploaded files under repo-root `uploads/` and return an absolute local path for `file` sources.

Reasoning:

- GStreamer currently reads local file paths.
- This is the simplest bridge from browser upload to `file` input source.

Consequence:

- Upload metadata needs persistence before the workflow is production-shaped.
- Upload path isolation and file type limits are required before deployment.
