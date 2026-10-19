# Data Model

## PackPin (`packs/<pack>.source.yaml`)
| Field | Type | Rule |
|---|---|---|
| repository | str | Git URL. Comes only from the committed pin, never from the environment. |
| commit | str | 40 lowercase hex characters |
| subtree | str | Relative POSIX path inside open-packs. No `..`, not absolute. |
| tree_digest.algorithm | `clean-tree-sha256` | fixed |
| tree_digest.level | `built-in` \| `org` | Digest tier. Defaults to `built-in` when absent (backward compatible). |
| tree_digest.value | str | 64 hex characters |
| requires_core | str \| None | built-in pack only |

`BuiltInPin` remains as an alias of `PackPin`.

## Pack cache
`${XDG_CACHE_HOME:-~/.cache}/spec-kitty/open-packs/<commit>/<subtree>`. An entry is valid only when its digest matches the pin.

## Fetched pack tree
`packs/<pack>` (gitignored). States: absent → synced (digest OK) → stale (digest mismatch, which is re-synced or refused).
