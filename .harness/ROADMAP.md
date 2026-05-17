# Roadmap

This roadmap is organized by maturity, not by calendar date. Each phase should leave the project more usable and easier to contribute to.

## 0.1 MVP Core

Status: mostly complete.

- In-memory sessions.
- Source and scene APIs.
- GStreamer command generation and process launch.
- RTMP output through GStreamer.
- FFmpeg fallback smoke-test backend.
- Local MediaMTX workflow.
- Web console for session, source, layer, output, and start/stop control.
- HLS auto-preview in the console.

## 0.2 Local Stable

Status: active target.

- Complete file upload flow and browser validation.
- Add uploaded asset listing, reuse, and deletion.
- Add SQLite persistence for sessions, sources, scenes, and uploads.
- Add deterministic smoke scripts.
- Add Docker Compose for API + MediaMTX.
- Improve UI error states and status polling.
- Add basic project documentation for installation, architecture, and troubleshooting.

## 0.3 Deployable

Status: planned.

- Config file and environment variable support.
- Process supervisor with restart policy and log rotation.
- Authentication for the console and API.
- CORS and upload security hardening.
- OpenAPI schema and generated API reference.
- Multi-session resource limits.
- Release-ready Docker image.

## 0.4 Creator Experience

Status: planned.

- Drag-and-resize visual canvas editor.
- Layer ordering controls and snapping.
- Text style controls.
- Template scenes for common streaming layouts.
- Video file controls: loop, pause, resume, seek, end behavior.
- Real audio input and mixing controls.

## 1.0 Mature Open Source

Status: planned.

- CI for tests, lint, smoke checks, and image builds.
- Versioned releases and changelog.
- License, contributing guide, code of conduct, issue templates, and PR template.
- Example projects and sample media.
- Deployment guide.
- Security policy and documented limitations.
