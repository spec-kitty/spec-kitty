# Data model: CI runtime stabilisation

The mission's "data" is CI configuration and evidence. Entities, their single home, and invariants:

| Entity | Home (single source) | Key fields | Invariants |
|---|---|---|---|
| **Battery base selection** | `.github/ci-module-registry.yml` → `special_tiers.architectural.base` | paths, marker expression, whole-file deselects | Deselects equal the union of the always-on lanes' pytest paths (C-002); identical arguments in every battery part |
| **Fast-gate roster** | registry → `special_tiers.architectural.fast_gate.roster[]` | path, budget_seconds, reason | Each measured duration ≤ its budget; Σ ≤ `max_total_measured_seconds`; every entry is a file of the base selection |
| **Battery shard partition** | derived by `scripts/ci/shard_select.py` (file granularity) from registry `shard_count` + timings | part → files | fast ∪ S1 ∪ S2 = base; pairwise disjoint; no file in two parts |
| **Shard timings** | `.github/ci-shard-timings.json` | module → per-test durations; battery → per-file durations; capture provenance | Captured with the SAME marker expression its consumer uses — module rows `not performance and not stress`; battery base `not performance and not stress and not timing`; battery seed provenance per D-36; length mismatch is loud |
| **Module shard row** | registry module rows | name, paths, `shard_count` | consolidation `shard_count: 2`; leaves `_MISMATCH_ALLOWLIST` (shrink-only, `_BASELINE_ALLOWLIST_COUNT` 20 → 18) |
| **Path group** | `ci-router.yml` filter block (+ job `if:` gates) | name, globs | `ci_config` gates only the battery; `ci` gates no router job (#4386 pin); `HEAVY_BATTERY_NON_SRC_GROUPS = {architectural, ci_config}` |
| **Per-change suite-job ledger** | `tests/architectural/test_no_duplicate_suite_execution.py` `AUTHORIZED_PER_CHANGE_SUITE_JOBS` | job → reason | Adds `architectural-fast` and `tests (corpus-blocking)` (D-22); removes router cli/status/consolidation/corpus; counts per matrix leg |
| **Overlap allowlist** | `tests/architectural/test_same_tier_uniqueness.py` | (job A, job B, node-id pattern) → reason | Reasoned, shrink-only, ≤ 10 entries (expected 4); tiers keyed on OS family |
| **Tested key** | workflow artifact `ci-tested-key-pr<N>-base-<sha>` | workflow, PR, head SHA, base SHA (merge first parent) | Written only by executing runs; skip runs write `ci-green-match-run-<id>-attempt-<n>` and are never matched |
| **Green-match decision** | `scripts/ci/green_match.py` outputs | skip, reason, marker, matched run id/attempt/url | Skip only on `pull_request`+`ready_for_review`+attempt 1+exact key; any error → run |
| **Measurement evidence** | `kitty-specs/ci-runtime-stabilisation-01M3TZH6/evidence/ci-measurements.md` | run id, mode, job, duration, workers seen, peak memory | ≥ 3 runs per NFR; every number cites a run id (C-011) |

## State transitions

- **Ready-for-review run**: `pull_request(ready_for_review)` → `green_match.decide` → `Skip(matched run)` (path filters skipped, required gate green, Aggregate re-points) **or** `Run(reason)` (normal execution, tested key recorded).
- **Battery on a PR**: changes job → (`architectural-fast` always) + (`architectural-heavy` legs 1/2, 2/2 iff code-scoped groups ∪ `ci_config` ∧ ¬prose_only) → router gate.
- **Nightly**: schedule → `architectural-backstop` (full base, no partition) → `nightly-summary` → release nightly gate.
