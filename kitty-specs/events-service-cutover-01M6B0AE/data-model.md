# Data model: pinned service assets

## Service pin (`pins/read-service.source.yaml`) — existing schema, new instance
- `service: read-service`, `repository`, `tag: service-v0.1.0-rc.1`, `commit` (40 hex, from the tag), `protocol_versions`, `requires_core`.
- `assets`: `linux-x64`, `linux-arm64`, `macos-arm64`, `windows-x64`, `jvm` → `{name, sha256}`.
- `extras`: `contracts` (contract-bundles), `contract_tools`, `fixtures` (conformance-fixtures) → `{name, sha256}`.
- Invariant: written only by `spec-kitty service vendor`; validated on load (`SERVICE_PIN_INVALID`).

## Asset cache
```
${XDG_CACHE_HOME:-~/.cache}/spec-kitty/services/read-service/service-v0.1.0-rc.1/
  mission-status-api-0.1.0-rc.1-<target>      # native build (not in dev-setup)
  contract-bundles-0.1.0-rc.1.tar.gz          # verified archive
  <sha256 of that archive>/bundle/{mission-status,mission-write}/openapi.yaml
  contract-tools-0.1.0-rc.1.tar.gz
  <sha256>/contracts/tools/*.py
  conformance-fixtures-0.1.0-rc.1.tar.gz
  <sha256>/{conformance/,artifact-conformance/,event-log/torn-tail/,leak-patterns.json,nativesmoke/}
```
- Invariants: an extraction directory exists only after its archive verified; it is created atomically (unpack into a scratch sibling, then rename); its name is the archive digest, so it changes with every pin bump; unsafe members refuse the whole archive.

## Consumer paths (read from the extraction root)
| Extra | Path | Consumer |
|---|---|---|
| fixtures | `conformance/`, `leak-patterns.json` | mission-status conformance |
| fixtures | `artifact-conformance/{cases,golden}.json` | artifact goldens |
| fixtures | `event-log/torn-tail/repair-cases.json` | glossary torn-tail goldens |
| contracts | `bundle/mission-status/`, `bundle/mission-write/` | oracle `Contract`, contract tests |
| contract_tools | `contracts/tools/` | oracle tools, `codeowners_check`, acceptance-jvm `install_tools.py` / `gradle_pin_check.py`, corpus compare |
