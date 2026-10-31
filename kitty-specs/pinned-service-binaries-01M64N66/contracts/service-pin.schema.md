# Contract: service pin lockfile (`pins/<service>.source.yaml`)

```yaml
# round-trip: skip: illustrative lockfile with <64 hex> placeholders; ServicePin is a dataclass, validated by tests/kernel/test_service_pin.py
# Pin lockfile: which released build of this service core runs.
# Bump only with `spec-kitty service vendor --service <name> --tag <tag>`; never edit by hand.
service: write-service
repository: https://github.com/spec-kitty/spec-kitty-events
tag: service-v0.1.0
commit: 0123456789abcdef0123456789abcdef01234567
protocol_versions: [1]
requires_core: '>=4.0.0rc8,<5'
assets:
  linux-x64:   {name: spec-kitty-write-service-0.1.0-linux-x64,       sha256: <64 hex>}
  linux-arm64: {name: spec-kitty-write-service-0.1.0-linux-arm64,     sha256: <64 hex>}
  macos-arm64: {name: spec-kitty-write-service-0.1.0-macos-arm64,     sha256: <64 hex>}
  windows-x64: {name: spec-kitty-write-service-0.1.0-windows-x64.exe, sha256: <64 hex>}
  jvm:         {name: spec-kitty-write-service-0.1.0.jar,             sha256: <64 hex>}
extras:
  contracts:      {name: contract-bundles-0.1.0.tar.gz,     sha256: <64 hex>}
  contract_tools: {name: contract-tools-0.1.0.tar.gz,       sha256: <64 hex>}
  fixtures:       {name: conformance-fixtures-0.1.0.tar.gz, sha256: <64 hex>}
```

Validation (load time, `SERVICE_PIN_INVALID` on failure):
- every field exists and has the type in data-model.md;
- unknown top-level keys refuse;
- the file stem equals `service`;
- placeholder tag or commit refuses;
- asset names are plain file names, and no two assets share a name.

The vendor command also cross-checks every recorded digest against the release's `SHA256SUMS`, and refuses on disagreement.

Asset names follow spec-kitty-events' release naming (agreed on 2026-10-29: only `<ver>` changes between releases). The deployable prefix for the write service is whatever spec-kitty-events names `command-cli`'s binary. The pin stores the names verbatim, so core never constructs them.
