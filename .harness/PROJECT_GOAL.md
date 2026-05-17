# Project Goal

Online OBS is a headless, API-controlled live video composition and streaming system that can be run locally or deployed as a cloud service.

The long-term goal is to become a mature open source project for creating, controlling, previewing, and pushing live composited streams without a desktop OBS instance.

## Product Goals

- Create and manage live composition sessions through HTTP APIs and a web console.
- Combine test sources, video files, images, text, RTMP, and RTSP inputs into a canvas.
- Push output to RTMP destinations and preview through HLS.
- Support repeatable local development and deployment through documented scripts and Docker Compose.
- Provide clear operational feedback: process status, logs, playback preview, errors, and smoke tests.

## Engineering Goals

- Keep the MVP small but production-shaped.
- Prefer deterministic scripts over manual steps.
- Keep project state in the repository through `.harness/` files.
- Make each development slice independently verifiable.
- Preserve a path from local prototype to deployable service.

## Non-Goals For Now

- Full OBS feature parity.
- Browser-based real-time video editing beyond basic scene/layer controls.
- Hosted multi-tenant SaaS infrastructure.
- GPU-accelerated rendering as a first requirement.
- Perfect hot-swapping for every GStreamer element before the core workflows are stable.

## Definition Of Mature Open Source

The project reaches the target maturity when a new contributor can clone the repo, run one documented command to start the stack, create a stream from the UI, verify output playback, understand the architecture, run tests, open issues, and ship a small change through CI.
