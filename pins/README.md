# Service pins

This directory holds one pin lockfile for each service that core runs:
`pins/<service>.source.yaml`, where `<service>` is `write-service`,
`read-service` or `charter-service`.

A pin records which released build of the service core runs: the
`service-v*` tag of the service's own release repository, the commit it
resolves to, the protocol versions, the core version range it needs and, for
each target, the release asset's file name and SHA-256 digest. The wheel ships
no service binary; the pinned assets are fetched and checked against these
digests.

## Release homes

| Service | Release repository | Asset prefix |
| --- | --- | --- |
| `write-service` | `spec-kitty/spec-kitty-events` | `command-cli` |
| `read-service` | `spec-kitty/spec-kitty-events` | `mission-status-api` |
| `charter-service` | `spec-kitty/spec-kitty-charter` | `spec-kitty-charter-service` |

The events services release on spec-kitty-events' `service-v*` line
(ADR 2026-10-29-1); the charter service releases on its own `service-v*` line
from its own repository (spec-kitty-charter ADR-0046). A service's tag, assets
and `SHA256SUMS` all live in that repository.

## What is pinned

- `read-service.source.yaml`: the Mission Status read service from spec-kitty-events
  `service-v0.1.0-rc.1`, with its contract bundles, contract tools and conformance
  fixtures. It is pinned for CI conformance only: the CLI never launches it, and
  `spec-kitty service fetch --all` does not fetch it (ADR 2026-10-29-1 D-6).
- The write service and the charter service are not pinned yet: each waits for a
  release that carries it.

`make sync-services` fetches, verifies and unpacks the pinned assets for this host;
`make dev-setup` fetches the extras only. A placeholder pin (tag `service-v0.0.0` or an
all-zero commit) is refused when it is loaded.

## Rules

- Bump a pin only with `spec-kitty service vendor --service <name> --tag <tag>`.
- Never hand-edit a digest, a tag or a commit in a pin.
- The loader refuses an unknown key, a malformed field or a file whose name
  does not match its `service` field, with the code `SERVICE_PIN_INVALID`.

## Provenance

A GitHub `https://` bump verifies each downloaded asset's build attestation
before it writes the lockfile:

```bash
gh attestation verify <asset> --repo <owner/repo> \
  --signer-workflow <owner/repo>/.github/workflows/service-release.yml \
  --source-ref refs/tags/<tag>
```

A release whose attestation is missing, signed by another workflow, or from
another ref is refused, and the lockfile is left byte-identical. `--no-attestation`
skips the check: use it only for an offline mirror or a rehearsal, never for a
real bump. A `file://` repository has no attestation and is skipped, and an
installed CLI's `service fetch` verifies the pinned digest alone - the pin is
the trust root, not the release page.

## References

- Schema: [service pin lockfile contract](../kitty-specs/pinned-service-binaries-01M64N66/contracts/service-pin.schema.md)
- Decision: [ADR 2026-10-29-1](../docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md) (D-3)
- Charter release line: spec-kitty-charter ADR-0046
- Model: `src/kernel/service_pin.py`
