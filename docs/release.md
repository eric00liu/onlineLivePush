# Release Workflow

Online OBS releases are cut from git tags and published as GitHub Container Registry images.

## Release Checklist

1. Update `CHANGELOG.md` and confirm `pyproject.toml` matches the intended version.
2. Run local verification:

   ```bash
   scripts/dev_check.sh
   python3 -m json.tool docs/openapi.json >/dev/null
   docker compose config >/dev/null
   docker compose -f docker-compose.yml -f docker-compose.gstreamer.yml config >/dev/null
   ```

3. Run live smoke checks when API and MediaMTX are available:

   ```bash
   scripts/smoke_rtmp.sh
   scripts/smoke_upload_file.sh
   scripts/smoke_audio_mix.sh
   ```

4. Create and push an annotated version tag:

   ```bash
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin v0.2.0
   ```

5. Watch the GitHub Actions `Release` workflow. It verifies the repository and publishes:

   ```text
   ghcr.io/<owner>/<repo>/api:v0.2.0
   ghcr.io/<owner>/<repo>/api:latest
   ghcr.io/<owner>/<repo>/api:v0.2.0-gstreamer
   ```

## Manual Dispatch

The `Release` workflow can also be started manually with a `version` input such as `v0.2.0`. Manual dispatch is intended for release-candidate image tests; tagged releases remain the source of truth.

## Image Notes

- `api:<version>` uses the lean `Dockerfile` image and FFmpeg smoke backend.
- `api:<version>-gstreamer` uses `Dockerfile.gstreamer` and includes the GStreamer plugin set for the production-oriented backend.
- The GStreamer image currently publishes `linux/amd64`; the lean image publishes `linux/amd64` and `linux/arm64`.

