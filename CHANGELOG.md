# Changelog

All notable changes to Online OBS are recorded here.

## 0.2.0 - 2026-05-17

### Added

- Static control console for sessions, sources, scenes, stream controls, HLS preview, logs, uploads, and visual layer editing.
- GStreamer RTMP pipeline generation with H264 video, silent AAC fallback, file-source looping, and real `audio` source mixing through `audiomixer`.
- FFmpeg fallback backend for generated RTMP smoke streams.
- MediaMTX local RTMP/HLS workflow and Docker Compose stack.
- Optional SQLite persistence for sessions and uploaded asset metadata.
- Runtime configuration through environment variables, CLI flags, and `GET /config`.
- Optional bearer-token auth for non-public API routes.
- Upload material library with server-side size/type limits and path isolation.
- OpenAPI reference in `docs/openapi.json`.
- GitHub Actions CI and release workflows.

### Changed

- The default Docker image stays lean and FFmpeg-capable; the full GStreamer runtime is available through `Dockerfile.gstreamer` and `docker-compose.gstreamer.yml`.
- Smoke scripts use dynamic stream names and can pass `API_TOKEN` or `ONLINE_OBS_AUTH_TOKEN` when auth is enabled.

### Known Limits

- Running scene/source changes still require restart to apply.
- File looping restarts the pipeline at clip end and is not frame-seamless.
- The FFmpeg backend remains a smoke-test fallback, not a full compositing backend.

