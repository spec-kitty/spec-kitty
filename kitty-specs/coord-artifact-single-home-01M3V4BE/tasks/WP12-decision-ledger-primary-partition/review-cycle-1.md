---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T19:15:58Z'
reviewer_agent: claude
wp_id: WP12
---

# WP12 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Lane-j tip `be53a1cf34`, base `0aea25ffc8` (lane-a `e7b085d26c` merged onto the WP11 tip `2e9753302b`).

## What already passes

- **The reclassification itself.** `DECISION_LEDGER` moved from `_PLACEMENT_ARTIFACT_KINDS` to `_PRIMARY_ARTIFACT_KINDS`, and `_COORD_RESIDUE_DIRS["decisions"]` keeps the dir→kind mapping. The P-1 partition invariant holds.
- **Merge-class guard.** `decisions` STAYS in `_NON_DIVERGENT_COORD_RESIDUE_DIRS`, with the ruling text amended. The new `test_decision_ledger_index_driver_is_registered` resolves the driver through the `_MERGE_DRIVERS` `config_key`.
- **`planning_recency._is_driver_covered`.** It excludes driver-covered PRIMARY paths (`decisions/index.json`), so the target-favouring `git merge-file --ours` can no longer clobber WP11's union. `test_decision_ledger_index_is_never_returned_as_target_newer` pins it, and the function-local import avoids the `consolidation → lanes` cycle.
- **Real-router and CLI tests.**
  - `test_router_commits_ledger_on_target_branch` runs the real `commit_for_mission` grouping, never `owned=`, and checks the result per branch with `git show`/`git log`.
  - `test_spec_commit_commits_ledger_on_target_branch` drives the real CLI.
- **FR-009b.** I found no new auto-committer of `decisions/` paths. The `decisions/` module never commits, and the WP03 seed now skips the ledger automatically because it collects COORD-kind files only.
- **Lane content.** `be53a1cf34` removes the stray planning artifacts: there is zero `kitty-specs/` diff against base. All 11 changed files are in `owned_files`.
- **Status-events census.** `test_lock_composition_census` is red identically at the base (`new: ['specify_cli.coordination.coord_seed']`). WP12 adds NO new census site, so this is the inherited WP03 regression assigned to WP07.
- **Dead symbols.** The gates are red only on `COORD_SEED_TRAILER` (WP06), with no allowlist change.
- **Static checks.** ruff check, C901 and mypy --strict are clean.

## Blocking

**B1 (NEW red): the formatting "boy-scout" breaks the format-exclude ratchet.**
- The five reformatted files are on `[tool.ruff.format].exclude` (the #473 formatter-debt ratchet):
  - `src/mission_runtime/artifacts.py`
  - `tests/architectural/test_merge_reconciliation_class_guard.py`
  - `tests/architectural/test_write_surface_placement_guard.py`
  - `tests/mission_runtime/test_artifact_partition.py`
  - `tests/mission_runtime/test_artifact_partition_mapping.py`
- `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` is now RED: "5 exclude entries are already formatted… Remove them from `[tool.ruff.format].exclude`".
- The format debt is genuine on `main`, `upstream/main` and the mission base, but those files are exempt from the format gate. Nothing required formatting them.
- Two of them are shared architectural guards that other lanes edit:
  - `test_write_surface_placement_guard.py`: WP05/06/08/10/20;
  - `test_merge_reconciliation_class_guard.py`: WP08/11/17/18.

  Whole-body reformatting there invites consolidation conflicts.
- The reformatted, uncovered lines also pull `artifacts.py` diff coverage down to 3/5 (lines 400 and 403 are reformat-only). Combined diff coverage is 83.3% (10/12), below 90%.
- **Required:** revert every formatting-only hunk in all five files and keep only the semantic edits. Do not touch `pyproject.toml`; removing exclude entries is shared, cross-cutting config. The format ratchet must then be green, and diff coverage must be measured again over the remaining diff.

**B2: the topology-less-callers binding correction was not discharged; the tests that claim to discharge it are vacuous.**
- The ruling (Decision Moment `plan.design.topology-less-callers`; binding correction; plan IC-11 L367-371) required:
  - a fix at the single predicate point in `coherence.py`;
  - `lanes`/`single_branch` Missions keeping TODAY's verdict at every topology-less caller (C-008), pinned by a characterization on real `lanes` and `single_branch` Missions that is green at the base;
  - coordination-Mission tests at move-task, implement and auto-rebase;
  - a list of the slug-less callers that keep the base behaviour.
- What shipped:
  - **No `coherence.py` change.** Measured verdicts for `kitty-specs/m/decisions/index.json`:

    | Call shape | Base `0aea25ffc8` | Tip |
    |---|---|---|
    | bare (no slug, no topology) | **True** (residue) | **False** |
    | `mission_slug=` only | **True** | **False** |
    | `topology=LANES` | False | False |
    | `topology=COORD` | True | False |

    So the ledger verdict changed for EVERY Mission at all six topology-less callers, `lanes`/`single_branch` included. That is a C-008 behaviour change at, for example, move-task's `_drop_lane_coord_residue` on a lanes Mission.
  - **`test_ledger_topology_less_callers.py` is tautological.** Its autouse `_any_stored_topology` fixture is never threaded into any call, so the 48 "parametrized" cases are 8 identical assertions repeated six times. They call the predicate directly, never a real caller, and their docstrings claim "keep the base behaviour" while asserting the opposite of the base (they were among the 69 base reds).
- **The real problem is a design contradiction to escalate, not paper over.**
  - Once `DECISION_LEDGER` leaves the COORD partition, no topology value makes `kind_is_coordination_residue` return True for it.
  - So "keep today's verdict for lanes/single_branch" is impossible without a compatibility set, and round 4 forbids one.
  - The implementer's mechanical conclusion ("no coherence.py change can help the ledger") is correct. Silently dropping the C-008 half of the ruling is not.
- **Required, all of these:**
  1. Raise this to the operator/coordinator as a Decision Moment amendment. Either:
     - **(a)** accept the widening: the ledger is real work at topology-less callers for every topology, lanes/single_branch included, with the C-008 exception recorded; or
     - **(b)** authorize the compatibility rule the ruling implies.

     Record the outcome in `design-decisions`.
  2. Replace the vacuous parametrization with caller-level tests that assert each caller's observable decision (DIRECTIVE_041):
     - coordination-Mission tests at `tasks_move_task.py` (`_drop_lane_coord_residue`), `implement.py` (both sites) and `lanes/auto_rebase.py`, as the binding asks;
     - a real `lanes` and a real `single_branch` Mission characterization reflecting whichever ruling the operator makes.
  3. If (b): implement it at the single predicate point in `coherence.py` (owned).
  4. List the slug-less callers explicitly (move-task, tasks_shared, implement ×2, auto_rebase) in the tracer and in the module docstring.

**B3: the re-pinned test kept a name that now lies.**
- `test_artifact_partition_mapping.py::test_decisions_ledger_classifies_to_coord` asserts PRIMARY.
- Rename it, for example to `test_decisions_ledger_classifies_to_primary`. "Grep continuity" can live in the docstring.

**B4: a mixed-batch real-router test is missing (the WP05 cross-check).**
- After the reclassification, a single `commit_for_mission` batch carrying all three must split across both branches:
  - `decisions.events.jsonl` (DECISION_LOG → COORD, translated via `write_dir`, `_StagePlan.SKIP_DECISION_LOG`);
  - `decisions/DM-<ulid>.md` (PRIMARY);
  - `decisions/index.json` (PRIMARY).
- Add one test on a real coordination Mission (no `owned=`). Assert `surfaces` (primary committed = the ledger pair; coordination committed = the log) AND `git log`/`git show` per branch, including that the coordination branch gains no `decisions/DM-*`/`index.json` and the target gains no `decisions.events.jsonl`.

## Non-blocking

- **N1:** `test_shared_residue_predicate_never_flags_ledger_as_residue` (reader-flips) has the same shape as B2. It is fine as a predicate pin, but it is not the per-reader evidence T066 asks for. Keep it, but do not count it as caller coverage.
- **N2:** the `_is_driver_covered` docstring says "today: only `decisions/index.json`". `_MERGE_DRIVERS` also covers `decisions.events.jsonl` and other `kitty-specs/**` COORD files, which `kind_is_coordination_residue` already excluded. Reword to "the only PRIMARY-partition driver-covered path today".

## Tests run by the reviewer (`-n 3 --dist loadfile`, tip `be53a1cf34`)

| Suite | Result |
|---|---|
| WP12-owned tests + `tests/specify_cli/decisions/` + `tests/mission_runtime/` + `tests/coordination/` + 9 `tests/consolidation/` files touching planning_recency/bookkeeping + `tests/lanes/test_squash_seam_reconciliation.py` | 1600 passed, 1 skipped |
| Integration: test_lifecycle_events_preserved, accept_matrix_coord_partition, hosted_posture_matrix, issue_verdict_coord_legacy_md_preservation, specify_plan_commit_boundary, placement_partition_golden_path, protected_primary_spec_commit | 81 passed |
| Gates: write_surface_placement_guard, merge_reconciliation_class_guard, no_dead_symbols, dead_symbol_allowlist_contract, layer_rules, status_events_writes_gate, ruff_format_exclude_ratchet, no_legacy_terminology, mission_runtime_surface | 269 passed, 4 failed (breakdown below) |

The 4 gate failures:
- `COORD_SEED_TRAILER` (×2, transitional, WP06);
- `test_lock_composition_census` (inherited WP03 regression; identical at base);
- **`test_every_exclude_entry_still_genuinely_reformats` (NEW, B1)**.
