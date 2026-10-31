# Data model: Optional companion services wheel

## Companion manifest (`spec_kitty_services/_manifest.json`, inside every companion wheel)

| Field | Type | Rule |
|---|---|---|
| `schema` | int | `1` |
| `cli_version` | str | Equals the `spec-kitty-cli` version of the release (and the wheel's own version) |
| `target` | str or null | A `ServiceTarget` value of a native target; `null` in the fallback wheel |
| `services` | list | Sorted by `service`; empty in the fallback wheel |
| `services[].service` | str | `write-service` or `charter-service`; never `read-service` |
| `services[].tag` | str | The pin's `tag` |
| `services[].asset` | str | The pin's asset name for `target` |
| `services[].sha256` | str | The pin's sha256 for that asset; equals the sha256 of `bin/<asset>` in the wheel |

**Invariants**
- The set of `(service, asset, sha256)` equals the release commit's pins for `target`, restricted to the companion services.
- Every `bin/*` member of the wheel appears in `services[]`, and the reverse.
- The wheel's version equals `cli_version`.

## Wheels per release

| Wheel | Tag | Contents |
|---|---|---|
| Platform (one per native target that has at least one pinned asset) | `py3-none-manylinux_2_39_x86_64`, `py3-none-manylinux_2_39_aarch64`, `py3-none-macosx_11_0_arm64`, `py3-none-win_amd64` | providers, manifest, `bin/<asset>` |
| Fallback | `py3-none-any` | providers, manifest with `target: null` and no services |

## Provider decision (`write_service()` / `charter_service()`)

Returns `None` unless all of these hold:
- the manifest exists;
- `cli_version` equals the installed `spec-kitty-cli`;
- `target` equals `kernel.service_hosts.host_target()`;
- the service is listed;
- `bin/<asset>` is a regular file.

When all hold, it returns that path. Resolution then digest-checks the path against the CLI's own pin.
