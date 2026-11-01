# Quickstart: verify the charter service pin line

## For a maintainer bumping the charter pin

```bash
# inside a spec-kitty source checkout, with gh installed and authenticated
uv run spec-kitty service vendor --service charter-service --tag service-v0.1.0
```

What you should see:

- the release repository defaults to `https://github.com/spec-kitty/spec-kitty-charter`
  (no `--repository` needed);
- each asset the pin records is verified against `SHA256SUMS` **and** against the
  release's build attestation
  (`gh attestation verify ... --signer-workflow .../service-release.yml --source-ref refs/tags/<tag>`);
- `pins/charter-service.source.yaml` is written only when every check passes.

Refusals leave the lockfile byte-identical and name a stable code:

| Code | Meaning |
| --- | --- |
| `SERVICE_VENDOR_ATTESTATION_UNSUPPORTED` | the repository is not a GitHub `https://` URL, so no signer workflow can be derived |
| `SERVICE_VENDOR_ATTESTATION_UNAVAILABLE` | `gh` is missing or cannot run |
| `SERVICE_VENDOR_ATTESTATION_FAILED` | `gh` rejected the asset: no attestation, another signer workflow, or another source ref |

`--no-attestation` skips the provenance step. Use it only for an offline mirror or a
rehearsal, never for a real bump: it is the one flag that makes a pin trust `SHA256SUMS`
alone.

## For an operator verifying an install

```bash
uv run spec-kitty service fetch --service charter-service
```

The pinned native asset (or the jar on a host without one) is downloaded into the cache,
hashed, and compared with the pin's digest before it is used. A mismatch refuses with
`SERVICE_BINARY_DIGEST_MISMATCH` and caches nothing.

## Independent second source

The manual check from spec-kitty-charter ADR-0046 decision 6 still works:

```bash
sha256sum --check --ignore-missing SHA256SUMS
gh attestation verify <asset> --repo spec-kitty/spec-kitty-charter \
  --signer-workflow spec-kitty/spec-kitty-charter/.github/workflows/service-release.yml \
  --source-ref refs/tags/<tag>
```

## What did not change

- `_TAG_RE`, `ServiceTarget`, `service_hosts`, the jar fallback, and the pin schema.
- The charter service stays `launchable=False` until the per-worktree launcher lands
  (spec-kitty-charter #70).
- A user fetch or start never calls `gh`.
