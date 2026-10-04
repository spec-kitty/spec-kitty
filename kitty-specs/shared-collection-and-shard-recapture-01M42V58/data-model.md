# Data Model: Shared battery collection and complete shard-timing provenance

## Stored collection record

One JSON file per collection key in the store directory.

| Field | Type | Rule |
|---|---|---|
| `schema` | int | `1`; any other value is treated as absent |
| `key` | str | hex digest; must equal the consumer's computed key |
| `commit` | str | `git rev-parse HEAD` at production; must equal the consumer's |
| `tree` | str | `git rev-parse HEAD^{tree}` at production; must equal the consumer's |
| `created_at` | str | ISO-8601 UTC, informational |
| `count` | int | must equal `len(records)` and be at or above the collection floor |
| `records` | list | `{nodeid, relpath, markers}` exactly as `collect_universe()` returns today |

**Invariants**

- A record is written only after a collection that completed with an accepted exit status and produced its dump.
- A record that fails any rule above is treated as absent and replaced by the next successful collection.
- Writing a record removes every other record file in the store directory.
- The store is neither read nor written when the checkout has uncommitted changes or the caller passed a `repo_root` override.

## Collection key inputs

| Input | Source |
|---|---|
| committed tree | `git rev-parse HEAD^{tree}` |
| interpreter | `sys.version_info` (major, minor, micro) and implementation name |
| platform | `sys.platform` |
| dependencies | digest of sorted `name==version` of installed distributions |
| environment family | sorted `NAME=value` for `SPEC_KITTY_*` and `PYTEST_ADDOPTS`, minus the declared exclusions, taken after the operator env file (`.kitty.env`, both tiers) is overlaid with the product's own loader |

## Reuse report line

One JSON object per `collect_universe()` call, appended to the report file named by an environment variable (no file, no report).

| Field | Values |
|---|---|
| `outcome` | `reused` \| `collected` \| `bypassed` |
| `reason` | for `collected`/`bypassed`: `no-record`, `invalid-record`, `origin-mismatch`, `dirty-checkout`, `root-override`, `unsupported-platform`, `git-unavailable`, `env-file-unreadable` |
| `detail` | free text for a lock or store failure reported as `bypassed` / `unsupported-platform` |
| `dirty_paths` | for `dirty-checkout`: the first five paths that made the checkout dirty |
| `key` | the computed key, or null when bypassed |
| `caller` | the requesting test file or `prestep` |
| `seconds` | wall time of the call |

## Module timing data (existing, `.github/ci-shard-timings.json`)

| Section | Rule after this mission |
|---|---|
| `module_test_durations[module]` | written only by the capture producer |
| `module_test_count[module]` | equals the collected count at the capture commit (strict) |
| `module_capture_provenance[module]` | present for every registry module; valid per the shared predicate (exit status 0 or 1, at least one duration) |

## Recapture run result

| Field | Meaning |
|---|---|
| `drifted` | modules whose committed count or provenance disagrees with the count-only pass |
| `captured` | modules recaptured this run |
| `failed` | modules whose capture was not valid; committed data untouched |
| `deferred` | drifted modules not started because the time budget was spent |

State transitions for one module in one run: `clean` (no action) or `drifted` → `captured` \| `failed` \| `deferred`. The run exits non-zero when `failed` is non-empty.
