# Mission Research: charter-service pin release line

Mission: `charter-service-pin-line-01M6BTXZ` (issue #6909). Software-dev.
Discovery ran on 2026-11-01 against `origin/main` at `287a226cfe`.

Evidence gathered by reading the code, the ADRs and both service repositories. The
`spec-kitty charter context --include` calls in the procedure resolve in this checkout.

## Decisions

### D1 — The default repository becomes per service (vendor layer, not kernel)

- **Decision**: add `DEFAULT_REPOSITORIES` to `src/specify_cli/services/vendor.py`:
  `write-service` and `read-service` -> `https://github.com/spec-kitty/spec-kitty-events`,
  `charter-service` -> `https://github.com/spec-kitty/spec-kitty-charter`. Resolution order
  stays explicit argument -> current pin's repository -> service default.
- **Why**: the issue names `vendor.py:70` and `:333`; a repository is a vendor concern, while
  `kernel.service_pin` owns the tag rule, targets and asset-prefix table and must not learn
  repository identities (C-002). The pin already records the repository, so only the
  *new-pin* default changes.
- **Evidence**: `src/specify_cli/services/vendor.py:70`, `:322-333`;
  `src/kernel/service_pin.py:41-74`; issue #6909 "Requested changes" item 2; issue #6915 gap 7
  ("the pin already stores its repository, so only wording changes").

### D2 — Retire "Provisional": the prefix is the charter repository's recorded asset name

- **Decision**: drop the provisional comment; the prefix stays `spec-kitty-charter-service`,
  now stated as the name recorded by spec-kitty-charter ADR-0046 decision 4.
- **Why**: ADR-0046 states the prefix "is no longer provisional" and lists the exact asset
  names, including `-windows-x64.exe` and the raw (non-archive) native executables, which is
  what `ServiceTarget.asset_suffix` already produces. No behaviour change; the value was
  already right.
- **Evidence**: spec-kitty-charter `docs/adr/0046-service-release-line-and-native-packaging.md`
  decision 4; `.github/workflows/service-release.yml` (asset table in its header).

### D3 — Check build provenance at vendor time, automatically, for GitHub releases

- **Decision**: `vendor_pin` verifies every downloaded, digest-checked asset with
  `gh attestation verify <asset> --repo <owner/repo> --signer-workflow <owner/repo>/.github/workflows/service-release.yml --source-ref refs/tags/<tag>`
  before the lockfile is written. Default on; `file://` repositories skip (there is no
  attestation on a local fixture or mirror); a `--no-attestation` CLI flag is the explicit
  escape hatch for an offline mirror or rehearsal.
- **Why**: both release workflows attest every asset in `SHA256SUMS`, and the digest itself
  comes from the same build run, so only the attestation is independent provenance.
  spec-kitty-charter ADR-0046 decision 6 says "Core does not check the attestation yet
  (spec-kitty#6909)" — the issue is the request to close that gap. Checking at *vendor* time
  (not on every user fetch) keeps the pin the trust root (C-003) and keeps `gh` out of the
  user runtime (NFR-003).
- **Evidence**: spec-kitty-events `.github/workflows/service-release.yml` (attests
  `subject-checksums: dist/SHA256SUMS`); spec-kitty-charter `.github/workflows/service-release.yml`
  (same); `docs/development/how-to/service-pins.md:117-128` currently documents the check as a
  manual maintainer step; `src/specify_cli/services/vendor.py:23-27` records it as a follow-up.
- **Rejected alternative**: verifying inside `kernel.service_artifacts.fetch_asset` (the user
  fetch path). It would require `gh` on every user machine and re-verify the same bytes on
  every resolve, for no extra trust: the pin's digest already decides what runs.

### D4 — Prove the install half with a charter-service fixture pin

- **Decision**: add an end-to-end CLI test that pins `charter-service` from a `file://`
  fixture, runs `spec-kitty service fetch --service charter-service`, asserts the cached copy
  is the release asset, then tampers with the same fixture and asserts
  `SERVICE_BINARY_DIGEST_MISMATCH` with nothing cached.
- **Why**: the mechanism exists (`kernel.service_artifacts.fetch_asset`) but every existing
  fetch test pins `write-service`; the issue asks for the charter service specifically "with a
  fixture pin". Both assertions share one fixture (positive/negative control).
- **Evidence**: `tests/specify_cli/services/test_service_cli.py:120-198` (write-service only);
  `tests/kernel/service_release_fixture.py` (fixture builder already keyed by service).

## Evidence inventory

| Surface | State on `287a226cfe` |
| --- | --- |
| `src/kernel/service_pin.py:70` | "Provisional: until spec-kitty-charter ... names its release asset" |
| `src/specify_cli/services/vendor.py:70` | `DEFAULT_REPOSITORY = ".../spec-kitty-events"` used for all three services |
| `src/specify_cli/services/vendor.py:23` | attestation check listed as an out-of-scope follow-up |
| `src/specify_cli/cli/commands/service.py:366,372,392` | `--tag` / `--repository` help name spec-kitty-events for every service |
| `pins/README.md:7-17` | "spec-kitty-events `service-v*` tag" as the release home of every pin |
| `docs/development/how-to/service-pins.md` | manual `gh attestation verify` note for maintainers |
| `tests/specify_cli/services/test_vendor.py` | no per-service default-repository case, no attestation case |
| `tests/specify_cli/services/test_service_cli.py` | fetch tests pin `write-service` only |

## Open questions

1. **Non-GitHub `https://` repository**: no signer workflow can be derived. Decision taken
   for the plan: refuse with a stable code that names `--no-attestation` as the explicit
   escape, rather than silently skipping. No such repository is pinned today.
2. **Attestation on `check_pin --online`**: skipped for this mission. `--check` fetches only
   `SHA256SUMS`, so verifying attestations there would download every asset again; the vendor
   path is where a pin is created and where provenance is established. Recorded in the PR's
   Deferred section as a possible follow-up, not a gap in this fix.
3. **Spec-kitty-charter's ADR-0046 sentence**: it says core does not check the attestation
   yet. That sentence lives in the charter repository; nothing to change in this PR. Note it
   in the PR hand-off so the charter maintainer can update it.
