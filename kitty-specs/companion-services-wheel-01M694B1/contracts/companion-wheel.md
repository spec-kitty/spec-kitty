# Contract: the companion wheel and the install slot

- **Distribution:** `spec-kitty-services`. Its version equals the `spec-kitty-cli` version of the same release.
- **Entry points:** group `spec_kitty.service_binaries`:
  - `write-service = spec_kitty_services:write_service`
  - `charter-service = spec_kitty_services:charter_service`
- **Provider:** a zero-argument callable that returns `str | None` (see data-model.md, "Provider decision").
- **Consumer:** `specify_cli.services.resolution._install`. The consumer is unchanged by this Mission.
  - It runs after the explicit path and before the cache.
  - Any returned path must be the pinned host build or the pinned jar; otherwise it refuses with `SERVICE_BINARY_DIGEST_MISMATCH`.
  - The verified bytes are adopted into the cache and run from there.
- **Extra:** `spec-kitty-cli[services]` requires `spec-kitty-services==<cli version>`.
- **Never carried:** `read-service`, any jar, any extras asset (contracts, fixtures).
- **Manifest:** `spec_kitty_services/_manifest.json`, schema `companion-manifest.schema.json`.
