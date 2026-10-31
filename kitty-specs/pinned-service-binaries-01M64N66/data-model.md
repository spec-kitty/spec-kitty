# Data model: Pinned service binaries

## ServicePin (value object, from `pins/<service>.source.yaml`)
| Field | Type | Rule |
|---|---|---|
| `service` | str | one of `write-service`, `read-service`, `charter-service`; equals the file stem |
| `repository` | str | `https://…` or `file://…` only |
| `tag` | str | `service-v<semver>`; a placeholder value (`service-v0.0.0`) refuses at load |
| `commit` | str | 40 lowercase hex characters; all-zero refuses (placeholder) |
| `protocol_versions` | list[int] | non-empty; the launcher refuses a pin with no intersection with `SUPPORTED_PROTOCOL_VERSIONS` |
| `requires_core` | str | PEP 440 specifier; checked at vendor time |
| `assets` | map[ServiceTarget → ServiceAsset] | at least one entry; keys are known targets |
| `extras` | map[name → ServiceAsset] | optional: `contracts`, `contract_tools`, `fixtures` |

## ServiceAsset (value object)
| Field | Rule |
|---|---|
| `name` | a plain file name: no `/`, `\`, `..` or empty value |
| `sha256` | 64 lowercase hex characters |

## ServiceTarget (enum)
`linux-x64`, `linux-arm64`, `macos-arm64`, `windows-x64`, `jvm`. Host detection maps `platform.system()` and `platform.machine()` to a target. Any other host has no native target (for example macOS x64), so only `jvm` is possible.

## CachedAsset (derived)
The path is `<cache_root>/<service>/<tag>/<name>`. It is trusted only while `sha256(file) == pin.sha256`. A mismatch deletes the file.

## ResolvedBinary (value object)
Fields: `argv_prefix` (`[path]` or `[java, -jar, path]`), `source` (one of `explicit`, `install`, `cache`, `jar`, `unpinned`), `verified_sha256`, and `pinned: bool`.

## ServiceInstance (state, owned by the service)
Read from `endpoint.json` through `write_service_protocol.read_endpoint_file`, then checked by handshake and health.

| State | Meaning | Launcher action |
|---|---|---|
| absent | no endpoint file | start, then wait for ready |
| published + healthy + identity match | usable | reuse |
| published + dead pid / handshake fails | stale | start a fresh one (the old lock is free once the process is dead) |
| published + identity mismatch (repositoryId) | foreign | refuse `SERVICE_VERSION_MISMATCH` |
| published + protocol mismatch | incompatible | refuse `SERVICE_VERSION_MISMATCH` |
| started but not ready within the budget | unhealthy | stop the process; refuse `SERVICE_UNHEALTHY` |

Invariant: the launcher never writes `endpoint.json` or `service.lock`; the service owns both. The launcher only reads the endpoint file, creates `<gcd>/spec-kitty-write-service/` with owner-only mode if it is missing, and opens `service.log` for the child.

## ServiceRefusal (error)
Each refusal carries `code`, `message` and `remedy`, and never carries the token. The codes are `SERVICE_BINARY_MISSING`, `SERVICE_BINARY_DIGEST_MISMATCH`, `SERVICE_UNSUPPORTED_PLATFORM`, `SERVICE_UNHEALTHY`, `SERVICE_VERSION_MISMATCH` and `SERVICE_PIN_INVALID`, plus the existing `WRITE_SERVICE_ENDPOINT_*` codes, which pass through unchanged.
