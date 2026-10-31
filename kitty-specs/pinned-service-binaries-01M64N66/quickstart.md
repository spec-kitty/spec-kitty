# Quickstart: Pinned service binaries

## Developer checkout
```bash
make sync-services              # fetch and verify every pinned asset for this host into the cache
make sync-services ARGS=--check # verify only
```
Until spec-kitty-events cuts its first `service-v*` release there is no pin. `sync-services` then reports "no service pinned" and exits 0.

## User
Nothing to do: the first command that needs the write service fetches, verifies and starts it.
- Air-gapped: `spec-kitty service fetch` on a connected machine. Copy the cache, or set `SPEC_KITTY_SERVICE_ASSET_DIR` to a directory that holds the pinned asset files.
- Inspect: `spec-kitty service status`. Stop: `spec-kitty service stop`.

## Maintainer: bump a pin
```bash
spec-kitty service vendor --service write-service --tag service-v0.2.0
spec-kitty service vendor --service write-service --check
git add pins/write-service.source.yaml && git commit
```

## Working on spec-kitty-events locally
```bash
export SPEC_KITTY_WRITE_SERVICE_BINARY=/path/to/your/build/spec-kitty-write-service
export SPEC_KITTY_SERVICE_UNPINNED=1   # prints a warning on every start
```

## Tests
```bash
uv run --frozen pytest -q tests/kernel/test_service_pin.py tests/kernel/test_service_artifacts.py tests/kernel/test_release_assets.py tests/specify_cli/services tests/architectural/test_release_asset_download_owner.py tests/ci/test_sync_services.py
```
