# Release Criteria

Use this file to decide whether the project is ready for each maturity milestone.

## 0.2 Local Stable

- A new contributor can start the local stack from documentation.
- Web console can create a stream from a test source.
- Web console can upload a video file and use it as a file source.
- HLS preview auto-plays after stream start.
- Unit tests pass.
- Smoke scripts cover RTMP and upload/file source paths.
- README includes troubleshooting for GStreamer, MediaMTX, and HLS preview.

## 0.3 Deployable

- Docker Compose starts all required services.
- Configuration is environment-driven.
- API and console can be protected by basic auth or an equivalent local auth mechanism.
- Process logs are retained and bounded.
- Stream process status is monitored and exposed.
- OpenAPI reference is available.
- Upload limits and path isolation are documented and enforced.

## 0.4 Creator Experience

- Canvas editing supports drag and resize.
- Sources can be reordered visually.
- File sources can loop and expose playback controls.
- Text sources expose style controls.
- Common templates can be created or loaded.

## 1.0 Mature Open Source

- License and contributing guide are present.
- CI validates tests, static checks, and smoke checks.
- Release workflow publishes versioned artifacts or images.
- Documentation covers install, architecture, API, deployment, and examples.
- Issue and PR templates exist.
- Security policy exists.
- Known limitations are explicit.
- Project can be demoed end to end from a clean checkout.
