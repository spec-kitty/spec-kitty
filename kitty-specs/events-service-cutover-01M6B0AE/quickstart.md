# Quickstart (maintainer)

```bash
make dev-setup                       # now also fetches the pinned extras (≈230 KB)
make sync-services                   # everything for this host, incl. the native read service
make sync-services ARGS=--check      # verify the cache against pins/*.source.yaml
uv run --frozen python scripts/sync_services.py --extras-path read-service:fixtures
uv run --frozen pytest tests/contract/test_mission_status_conformance.py -q
spec-kitty service vendor --service read-service --tag service-vX.Y.Z   # the only way to bump
spec-kitty service vendor --service read-service --check                # online check against SHA256SUMS
```
