---
affected_files: []
cycle_number: 2
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T21:55:06Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review, cycle 2: changes requested (one blocker, a regression introduced by the B5 fix)

Reviewer: claude (reviewer-renata, opus). Lane-d tip `6a2c520cf9`.

## Verified fixed

- **B1, resume probe.** `_status_events_log_path` resolves through `placement_seam(...).read_dir(STATUS_STATE)`. A healthy fresh create probes `found`, exit 0, for `coord`, `lanes_with_coord` and `lanes` (reviewer probe). The failure test asserts the specific message again.
- **B2, rollback holder.** The holder is filled before `write_dir`. My cycle-1 rollback probe now leaves no branch and no worktree at all three injection points, including the one inside the `write_dir` seed. The new parametrized test covers the same three points.
- **B3, format churn.** It is reverted:
  - `_coordination_doctor.py` is now +32/−5 against base;
  - `test_coord_staleness.py` is +4/−1;
  - `test_ruff_format_exclude_ratchet` is GREEN (6 passed).
- **B4, abort re-pin.** It now compares the worktree bytes too, and adds the root-never-regains-the-log guard in both abort tests.
- **Diff coverage.** 97.1% (167/172) against `e7b085d26c`.
- **Dead-symbol gates.** `no_dead_symbols` and `dead_symbol_allowlist_contract` are fully GREEN on lane-d.

## Blocking

**B5′ (regression from the B5 fix): an owned create with a coordination topology is a supported, ratcheted path, and the new refusal breaks it.**
- **What fails.** The four tests below were all green in my cycle-1 run (which included `test_owned_lifecycle_acceptance_next.py`). They now fail with `OWNED_TOPOLOGY_UNSUPPORTED`:
  - `tests/integration/test_owned_lifecycle_acceptance_next.py::TestFr022CoordinationTwin::test_next_after_create_is_a_typed_json_outcome_never_a_traceback`
  - `tests/integration/test_owned_lifecycle_acceptance_next.py::TestFr022CoordinationTwin::test_next_after_create_is_a_non_error_decision`
  - `tests/integration/test_owned_lifecycle_acceptance_next.py::TestFr022CoordinationTwin::test_advance_after_create_materialises_the_coordination_worktree_and_is_not_an_error`
  - `tests/core/test_mission_creation_unborn_head.py::test_guard_uses_owned_checkout_head[committed-owned]`
- **Why it is supported.** `TestFr022CoordinationTwin` is the in-process twin of `tests/e2e/test_worktree_owned_root_concurrency.py`. It is an FR-022 ratchet: an owned sibling-checkout `agent mission create --topology lanes_with_coord`, followed by `next`, must be a non-error decision. Owned plus coordination is therefore not merely an "operator override". ADR 2026-09-03-1's "single_branch only" covers lifecycle commands (`LIFECYCLE_OWNED_TOPOLOGIES`), not create plus `next` (`NEXT_OWNED_TOPOLOGIES` includes `LANES_WITH_COORD`).
- **The cycle-1 ask.** It was "refuse OR pin its actual behaviour". Refusal is ruled out by the ratchet, so pin the behaviour, either way:
  - **(preferred, scope-safe)** Make the owned arm truly byte-identical to pre-WP06, as the cycle-1 docstring claimed. Gate the coordination-routed scaffold change on `owned is None` in both `_scaffold_mission_dir` and `_build_create_result`, so an owned coordination create still scaffolds and commits `status.events.jsonl` exactly as at base. Then:
    - add a test pinning that on an owned `lanes_with_coord` create: the log is present, it carries `MissionCreated`, and it is committed exactly as at base;
    - keep `TestFr022CoordinationTwin` and the unborn-head owned case green;
    - record "owned plus coordination create is not seeded onto the coordination surface (INV-COORD-HOME residual for owned creates)" in `design-decisions`, and ask the coordinator for a follow-up issue or WP owner.
  - **(alternative)** Seed owned coordination creates properly: thread a `mission_runtime.OwnedCheckout` fact into `write_dir`. That is larger. Only do it if the coordinator rules it in scope.
- Remove the `OWNED_TOPOLOGY_UNSUPPORTED` refusal and its test (`test_mission_creation_owned_charter.py::test_owned_checkout_with_coordination_topology_is_refused`), or re-scope it to a genuinely unsupported shape.

## Non-blocking

- **N1:** `mission_check_prerequisites._status_events_log_path` adds `# noqa: BLE001`. BLE is not enabled, so this is an unused directive (RUF100, NFR-005). Remove the noqa and keep the rationale comment.
- **N2:** for a coordination Mission whose worktree is UNMATERIALIZED (for example a fresh clone with a local branch), `read_dir` resolves the PRIMARY dir. There the log no longer exists, so the resume probe reports `malformed`. That is acceptable, since the probe serves failed-create resume, but a one-line docstring note would help.

## Read blast-radius classification (WP06 grep list)

**Method.** Before WP06, create put only `MissionCreated` and `SpecifyStarted` on the primary log; lane, decision and retrospective events already lived on the coordination surface. A WP06 (b)-regression is therefore a reader of those creation events, or of the primary file's existence, on a live coordination Mission.

**Resolvers.** `candidate_feature_dir_for_mission`, `resolve_status_surface` and `read_dir(STATUS_STATE)` all return the coordination dir once the worktree is MATERIALIZED, which is the post-WP06-create state.

**Result: no (b) regressions.**

| Site | Dir source | Class | Owner |
|---|---|---|---|
| retrospective/summary.py:216 | `candidate_feature_dir_for_mission` (resolver) | a | — |
| retrospective/summary.py:645 | caller passes the resolver dir | a | — |
| retrospective/gate.py:214 | `resolve_status_surface`; primary only on error | a | — |
| retrospective/events.py:208 `emit_retrospective_event` | post-merge `run_terminus` primary dir | WRITE (post-merge, after projection; not WP06) | **no owner**: needs a WP14 assignment or a recorded residual |
| retrospective/generator.py:200 | primary `kitty-specs/<handle>` | a (post-merge terminus) | — |
| doctrine_synthesizer/apply.py:130 | primary via `FsMissionResolver` | a (post-retro; fails closed to empty) | — |
| audit/classifiers/status_events.py:57 | corpus scan; missing file skipped | a | — |
| migration/normalize_mission_lifecycle.py, migration/rebuild_state.py | legacy data | a | — |
| decisions/service.py:252 | `read_dir(STATUS_STATE)` | a; **probe below** | WP09 owns the module |
| release/changelog.py:136 | primary, release-time post-merge | a | — |
| cli/commands/retrospect.py:122 / :1145 | resolver-backed | a | WP14 |
| lanes/auto_rebase.py:416 `_hydrate_status_events_from_index` | parent of a conflicted `status.json` | a; **probe below** | — |
| status/cutover_eligibility.py:187 | corpus scan | a (pre-existing) | — |
| charter_activate.py:181 `_inflight_missions_for` | primary `kitty-specs/*` scan | a (pre-existing blind spot; warning only) | no owner, not WP06 |
| agent/mission_finalize.py:313 | write candidate list (router translates via `write_dir`) | a | — |
| agent/tasks_mark_status.py:561 | owned `status_dir` failure envelope | a | — |

**Probe 1, `decisions/service.py`, on a fresh default (coord) create.**
- Before `open_decision`: the coordination log holds `[MissionCreated, SpecifyStarted]`, and the root log is absent.
- `_events_path` resolves to `…/.worktrees/<m>-coord/kitty-specs/<m>/status.events.jsonl`.
- After `open_decision`: the coordination log holds `[MissionCreated, SpecifyStarted, DecisionPointOpened]`, and the root log is still absent.
- `_opened_event_exists` is True.

**Probe 2, `lanes/auto_rebase.py`.**
- `_hydrate_status_events_from_index(primary dir)` returns the `R-STATUS-JSON-REMATERIALIZE` diagnostic and creates no root log. Called on the coordination dir it returns `None`.
- The primary-dir call only runs for a conflicted `status.json` in that tree. A coordination Mission never carries one on target or lane branches, before or after WP06, so this is not a regression.

## Tests run by the reviewer (`-n 3 --dist loadfile`, tip `6a2c520cf9`)

| Suite | Result |
|---|---|
| `tests/core/` + `tests/missions/` + `tests/coordination/` + test_coordination_doctor + test_birth_cutover + test_zeitgeist_moment_handler + test_mission_creation_specify_started + test_mission_create | 1431 passed, 3 skipped, **1 failed** (unborn_head committed-owned, B5′) |
| The 15 integration files + 4 B1 guards + #4863 | 155 passed, **3 failed** (TestFr022CoordinationTwin, B5′) |

Named gates, run individually:

| Gate | Result |
|---|---|
| layer_rules | 74 passed |
| **no_dead_symbols** | 36 passed |
| **dead_symbol_allowlist_contract** | 4 passed |
| no_write_side_rederivation | 27 passed |
| write_surface_placement_guard | 17 passed |
| **ruff_format_exclude_ratchet** | 6 passed |
| no_legacy_terminology | 96 passed |
| no_read_side_bypass | 40 passed |
| status_events_writes_gate | 1 failed — inherited lane-a red, WP07 |
| mission_resolver_walker_gate | 1 failed — inherited lane-a red, WP07 |
| destructive_op_routing | 1 failed — inherited lane-a red, WP07 |
