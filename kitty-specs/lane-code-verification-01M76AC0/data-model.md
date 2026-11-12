# Data model

## LaneTestInvocation (value object, frozen)
| Field | Type | Notes |
|---|---|---|
| `cwd` | path | the lane (or write checkout) root |
| `command` | str or null | the declared `review.test_command` template, verbatim |
| `env_set` | map str→str | lane test env (+ `PYTHONPATH=<lane>/src` when the lane has no venv) |
| `env_unset` | list str | `PYTHONPATH`, `UV_PROJECT_ENVIRONMENT`, `VIRTUAL_ENV` (removed before `env_set` applies) |
| `probe` | ProbeResult or null | filled by `probe_lane_imports` |

Invariant: `environ(base)` = `base` minus `env_unset`, then plus `env_set`. Serialized as
`to_dict()` (see `contracts/lane-test-invocation.md`).

## ProbeResult (value object, frozen)
| Field | Type | Notes |
|---|---|---|
| `status` | `verified` \| `foreign` \| `unverified` | |
| `origins` | map package→path | observed origin per probed package |
| `foreign` | list package | packages whose origin is outside `cwd` |
| `reason` | str or null | why unverified, or which package was foreign |
| `interpreter` | str or null | the interpreter the probe ran |

Rules: any foreign package → `foreign`; all inside → `verified`; no package, no interpreter,
timeout, non-JSON output or a crash → `unverified`. Never raises.

## EvidenceTree (value object, frozen)
| Field | Type | Notes |
|---|---|---|
| `path` | str | the tree the gate ran in |
| `head` | str or null | `git rev-parse HEAD` there |
| `dirty` | bool or null | any tracked change or untracked file |
| `probe` | ProbeResult | |

## GateOutcome (extended)
Adds `foreign_tree`. Aggregation precedence: TERMINAL (`timed_out`, `cancelled`,
`scope_oversized`) > REFUSE (`foreign_tree`, unless `--force`) > BLOCK (`new_failures`,
opt-in) > WARN_PROCEED.

## WorkspaceContext (extended)
Optional `lane_test_invocation` (the `to_dict()` form, probe included); absent in contexts
written before this Mission (read side ignores unknown/missing keys).
