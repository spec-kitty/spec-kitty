# Data Model: origin freshness

## FreshnessState (enum, foundation-agnostic values)
`up_to_date`, `behind`, `ahead`, `diverged`, `local_missing`, `remote_missing`, `unreachable`, `no_remote`.

## Divergence (kernel value object)
| Field | Type | Meaning |
|---|---|---|
| `behind` | int | commits on the remote-tracking ref not on local (optionally path-scoped) |
| `ahead` | int | commits on local not on the remote-tracking ref |

## FreshnessVerdict (application value object)
| Field | Type | Meaning |
|---|---|---|
| `branch` | str | local branch name |
| `remote` | str \| None | resolved remote (FR-017) |
| `state` | FreshnessState | classification |
| `behind` / `ahead` | int | counts (0 when not applicable) |
| `scope` | str \| None | path the `behind` count is scoped to (status evidence) |
| `detail` | str \| None | git stderr summary for `unreachable` |
| `remote_sha` | str \| None | tip the remote listed (ls-remote) — the review fast-forward target, re-verified for ancestry before use |

Invariants: `up_to_date` and `remote_missing` only when the remote answered in this invocation; `behind > 0 and ahead > 0` ⇔ `diverged`.

## OriginCheckMode
`enforce` (default) | `warn`; carries `source` ∈ {`default`, `flag`, `environment`, `read-only`} (`read-only` = `accept --no-commit / --diagnose`). Unknown env value ⇒ `enforce` with a warning.

## Refusal codes
`ORIGIN_STATUS_STALE`, `ORIGIN_LANE_STALE`, `ORIGIN_LANE_DIVERGED`, `ORIGIN_UNREACHABLE`.

## Review lane action (application)
`keep` | `fast_forward(to_sha)` | `create_from(remote_ref)` | `refuse(code)` | `warn(state)`.
