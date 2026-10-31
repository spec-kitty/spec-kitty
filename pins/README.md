# Service pins

This directory holds one pin lockfile for each service that core runs:
`pins/<service>.source.yaml`, where `<service>` is `write-service`,
`read-service` or `charter-service`.

A pin records which released build of the service core runs: the
spec-kitty-events `service-v*` tag, the commit it resolves to, the protocol
versions, the core version range it needs and, for each target, the release
asset's file name and SHA-256 digest. The wheel ships no service binary; the
pinned assets are fetched and checked against these digests.

## Empty until the first release

This directory is empty until spec-kitty-events cuts its first `service-v*`
release. No pin with real digests is committed before then, and a placeholder
pin (tag `service-v0.0.0` or an all-zero commit) is refused when it is loaded.

## Rules

- Bump a pin only with `spec-kitty service vendor --service <name> --tag <tag>`.
- Never hand-edit a digest, a tag or a commit in a pin.
- The loader refuses an unknown key, a malformed field or a file whose name
  does not match its `service` field, with the code `SERVICE_PIN_INVALID`.

## References

- Schema: [service pin lockfile contract](../kitty-specs/pinned-service-binaries-01M64N66/contracts/service-pin.schema.md)
- Decision: [ADR 2026-10-29-1](../docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md) (D-3)
- Model: `src/kernel/service_pin.py`
