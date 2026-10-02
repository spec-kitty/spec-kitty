---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T20:50:41Z'
reviewer_agent: claude
wp_id: WP15
---

# WP15 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Lane `lane-m`, compared against the lane base `e7b085d26c`. Commits reviewed: `2bd0aad5a0` (red-first) and `a17b88e269` (feat).

## What works

These parts are sound and should be kept:

- The automatic pin refresh is threaded through `_resolve_preserve_planning_commit_decision`. The AST gate `test_finalize_refresh_pin_authority.py` is green.
- #4827 still fails closed on an orphaned pin. `test_plain_finalize_fails_closed_on_orphaned_pin` is green and was not re-pinned.
- Finalize's exit code now comes from `commit_outcome_exit_code`. Each of these mutations made 2 tests fail:
  - forcing `surface_refusal=False`;
  - deriving it from the legacy `status`;
  - deleting the `raise typer.Exit(1)`.
- The `lanes.json` compare-and-swap guard was extracted correctly.
- `_emit_local_canonical_events` and `_emit_tasks_started` now write through `write_dir`. Migrating `_emit_tasks_started` too was correct: TasksStarted is a STATUS_STATE write, and leaving it out would have forked the log.
- Diff coverage is 98%.
- The four regression guards are green.
- The re-pin of `test_preserve_path_warns_on_drift_without_flag` is a legitimate replacement under FR-012 (see the notes for an additional control test).

## Blocking

### B1. `agent tasks finalize-tasks` no longer seeds WP status on coordination-routed Missions (HIGH, regression)

`tasks_finalize.py:462` (`_ft_emit_status_events`) replaces all of `st.feature_dir` with `write_dir(STATUS_STATE).path`. That directory is also used for PRIMARY reads:

- `bootstrap_canonical_state` scans `feature_dir/tasks/` for WP files (`status/bootstrap.py:138`);
- `_tasks._mission_identity_payload(st.feature_dir)` reads `meta.json` (`tasks_finalize.py:514`, `:525`).

The coordination Mission dir holds only COORD records, so both reads find nothing.

Reproduction: `make_prefix_coord_mission(COORD, worktree="empty")` plus a committed tasks fixture, then a real `_do_finalize_tasks(validate_only=False, json_output=True)`:

| | bootstrap result | `planned` rows in the coord log | `mission_type` |
|---|---|---|---|
| base `e7b085d26c` | `total_wps=2, newly_seeded=2` | 2 | `"software-dev"` |
| HEAD | `total_wps=0, newly_seeded=0` | none | `""` |

The `make_coord_mission(materialized=True)` shape already seeded 0 WPs at base. That defect existed before this WP, but WP15 extends it to the EMPTY and UNMATERIALIZED shapes.

The prompt (T080 step 2) says: "keep reads on `read_dir`, and keep `primary_feature_dir` for PRIMARY reads".

Fix:
- Separate the directory WP files are read from (`st.primary_feature_dir`) from the status write directory.
- Feed bootstrap's WP discovery and the identity payload from PRIMARY. Only the event and snapshot writes should use `write_dir`.
- Add an unmocked test on a coordination-routed Mission, covering both the pre-fix and the materialized shapes. Assert `newly_seeded == <WP count>` and the correct `mission_type`. The existing `_ft_emit_status_events` tests mock bootstrap, so they cannot catch this.

### B2. `--validate-only` now writes to the repository (HIGH, NFR-002 regression)

`_ft_apply_writes` also runs under `--validate-only`, and `_ft_emit_status_events` now calls `write_dir` in that mode. `write_dir` can materialize the coordination worktree, seed it and commit.

Reproduction: `_do_finalize_tasks(validate_only=True)`:
- On `make_prefix_coord_mission(worktree="absent")`, the coordination worktree gets materialized, and a new commit `chore(<slug>): seed coordination surface` lands on the coordination branch.
- On `worktree="empty"`, the same seed commit lands.
- At base, both shapes leave the branch tip, the worktree and the Mission dir unchanged.

`test_ft_emit_status_events_writes_to_the_resolved_write_dir` (in `test_finalize_extracted_helpers.py`) pins `write_dir` with `validate_only=True`. It locks in the regression.

Fix:
- In validate-only mode, never call `write_dir`. Use the read projection or a side-effect-free resolution.
- Add a regression test: after `--validate-only` on the pre-fix and UNMATERIALIZED shapes, the coordination branch tip, the worktree's existence and the coordination Mission dir are unchanged.

### B3. `write_dir` refusals are swallowed, so lifecycle events are lost silently (HIGH, FR-003a and the T080 edge cases)

Two best-effort `except Exception` blocks wrap the new `write_dir` calls:
- `_emit_local_canonical_events`, around `mission_finalize.py:2331`: it prints a yellow warning in text mode and nothing in JSON mode;
- `_emit_tasks_started`, around `:4183`: it only writes a `logger.debug` line.

Reproduction: `make_prefix_coord_mission(COORD, remote_only=True)` with `--json`. Finalize reports `result: success` and exits 0, but WPCreated and TasksCompleted are never written anywhere, and the JSON gives no sign of it. At base the events at least landed in the root log (forked, but kept).

T080's edge cases require: "Remote-only coordination branch … Render it as a clean error with the recovery hint, no traceback, and nothing written. Seed fork (`COORD_SEED_FORK_REFUSED`): same rendering." FR-003a requires the same.

Fix:
- Resolve `write_dir(STATUS_STATE)` once, outside the best-effort blocks, before the first writer.
- Fail closed with the refusal's code and recovery hint in both text and JSON modes.
- Add tests for remote-only and for `COORD_SEED_FORK_REFUSED`. Each must assert a non-zero exit, the code in the error envelope, and that nothing was written.

### B4. The R10 test does not catch the FR-007b defect (MEDIUM)

Mutation: change `has_relevant_changes=primary_dirty or coord_dirt.is_dirty` to `has_relevant_changes=primary_dirty` (`mission_finalize.py`, `_resolve_finalize_commit_candidates`). All 19 tests in `test_finalize_tasks_commit_surface.py` still pass.

Instrumenting R10's second run shows why: the root-checkout porcelain is always dirty. It shows `M lanes.json` and `?? status.json`. The untracked root `status.json` comes from bootstrap's `materialize(planning_dir)` and already existed at base. So the coordination-only-dirt branch never decides the outcome.

At base, R10 also fails only at its precondition assertion ("root checkout's status log must stay clean"), not on the "no changes" defect. So FR-007b has no test that is red for the right reason.

Fix: add a test in which the PRIMARY candidates are clean and only the coordination copy is dirty. A direct test of `_resolve_finalize_commit_candidates`, with the root residue removed or committed, is enough. It must fail under the mutation above.

### B5. WP15 turned an architectural gate red: `test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` (MEDIUM)

WP15 reformatted two files that are still listed in `[tool.ruff.format].exclude`:

- `tests/integration/test_coord_loop_tasks.py` (`pyproject.toml:1477`);
- `tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py` (`pyproject.toml:1807`).

The gate is green at base and red at HEAD. Remove both exclude entries. `pyproject.toml` is a cross-cutting file, so add a coordination note.

The `test_coord_loop_tasks.py` change is mostly formatting churn outside `owned_files` (only the `write_dir` stub is substantive). Alternatively, drop the reformatting and remove only the owned file's entry.

### B6. ACCEPTANCE_MATRIX: the finalize writer still uses a read resolver, and "owning copy wins" was not flipped (MEDIUM)

Decision `DM-01M3W6J63JSPT07CRQN7FEHSW4` (`plan.design.translate-if-present-kinds`) assigns "acceptance-matrix (finalize) -> WP15". The WP15 Definition of Done also says: "No finalize write leg uses a read resolver for a COORD kind."

At HEAD:
- `_resolve_acceptance_matrix_home` (`mission_finalize.py:3593-3613`) still calls `_acceptance_matrix_read_dir` or `placement_seam(...).read_dir(ACCEPTANCE_MATRIX)`.
- `_scaffold_acceptance_matrix_if_lane_based` uses its result to choose the write target (`writes_to_planning_dir` selects a bare write into `planning_dir`).
- The router's per-kind treatment for ACCEPTANCE_MATRIX is still the unconditional legacy `copy2` from root to coordination.
- `_coord_candidate_dirt` now passes the coordination copy of `acceptance-matrix.json` in place, and `_collect_finalize_artifacts` still passes the root copy. A stale root copy therefore still overwrites the owning coordination copy.

Fix:
- Move the finalize matrix home and write target to `write_dir(ACCEPTANCE_MATRIX)`, establishing the Mission dir through `write_dir` first, as the decision requires.
- Flip ACCEPTANCE_MATRIX to "owning copy wins" in `commit_router._act_on_stage_plan`. `commit_router.py` is not in WP15's `owned_files`, so ask the orchestrator for the ownership grant (or a ruling) before editing it.
- Keep these four guards green by name:
  - `test_accept_matrix_coord_partition.py::test_matrix_lands_on_coord_via_all_three_write_paths_no_stale_copy`;
  - both tests in `test_issue_verdict_coord_legacy_md_preservation.py` that the decision record names as regressed;
  - `test_issue_verdict_selfmat_hardening.py::test_materialized_coord_verdicts_succeed`.

## Must fix in the same cycle (smaller)

### B7. `planning_commit_refresh` does not match the contract

`contracts/commit-outcome.md` defines the field as `{status, recorded, candidate, pin_class, reason}`. `_planning_commit_refresh_payload` (`mission_finalize.py:2477-2502`) emits only `status`, `recorded` and `candidate`.

The contract also says `kept_with_warning` applies to FOREIGN and INDETERMINATE pins. The code keeps INDETERMINATE as a silent `preserved`.

Keeping INDETERMINATE silent is defensible: with no capturable tip there is no candidate commit to name. But two things are needed:
- the JSON must carry `pin_class` and `reason`, so the decision is visible;
- the contract and the code must agree. Either implement the contract's INDETERMINATE row, or get the orchestrator to amend the contract and record that in the design-decisions trace.

### B8. The warning recommends a command that is guaranteed to fail

`_report_planning_sha_decision` (`mission_finalize.py:3399-3405`) tells the operator to run `--refresh-planning-commit --allow-orphaned`. Only a FOREIGN pin can reach `kept_with_warning`, and `_resolve_refresh_planning_commit_decision` (`:2598-2605`) refuses FOREIGN regardless of `--allow-orphaned`.

Give a remedy that actually works.

The comment at `:3393` says the warning covers "(FOREIGN/INDETERMINATE)", which contradicts the code.

### B9. The `--refresh-planning-commit` help text was not updated (T084 step 5, binding correction C3)

The help at `mission_finalize.py:5154-5164` still says "Without it, a re-finalize after execution has begun preserves the recorded SHA (#3311)". That is now false. Describe the automatic refresh and the flag's forcing, refresh-only role.

### B10. The pin-refresh consumer does not render on every outcome arm

In `_commit_planning_pin_refresh_locked`, the refusal arm goes `else:` → `_refuse_planning_pin_refresh` and never prints `rendered_lines` or emits `commit_surfaces`. The comment near `:2956` claims the opposite.

Its success and failure are also decided by `result.status`, not `commit_outcome_exit_code`. That breaks the outcome-consumer rule from the WP13 review.

Line `3031` (the text-mode rendering of pin-refresh success) is not covered. Add a test for each arm.

## Non-blocking notes

- **Bookkeeping-only guard.** Reusing `_drift_is_finalize_bookkeeping_only` stops the refresh from triggering itself, and it is tested: removing it made 2 tests fail. But it classifies drift by commit subject. An operator's planning edit that lands inside finalize's own `"Add tasks for …"` commit, such as a WP dependency change carried by a re-finalize, is treated as bookkeeping and never auto-refreshes. Record this as a known limitation (tracer entry or follow-up issue).
- **Re-pinned #4141 test.** No end-to-end test remains for "a non-planning commit advanced the tip → pin preserved and a drift WARN names `--refresh-planning-commit`". Only the unit test `test_mission_finalize_phases.py::test_report_planning_sha_decision_warns_on_preserved_drift` covers it. Add an end-to-end control.
- **US2.2 test.** It appends the claim event with `append_event(write_dir)` instead of running `move-task`, and it never checks that lamport values increase. It proves finalize's writes reach the coordination log, but not that `move-task` writes to the same log.
- **Unchanged-pin control.** `test_finalize_keeps_planning_commit_sha_when_unchanged` is red at base only because the new JSON field is missing. The SHA half of the control is green there, which is acceptable.
- **Owned plus coordination gap in `_commit_finalize_artifacts`.** `owned.files()` would refuse coordination-worktree candidates. This cannot happen today because `LIFECYCLE_OWNED_TOPOLOGIES == {SINGLE_BRANCH}`, where `write_dir` returns PRIMARY. Leave a guard or comment so a future topology widening fails loudly.
- **`_coord_candidate_dirt` side effects.** Calling `write_dir` before the dirt check is acceptable on the commit path: `_emit_local_canonical_events` has already established the surface, so the calls are idempotent. The real side-effect problem is the validate-only path in `tasks_finalize` (B2).
- **JSON error arm.** In JSON mode, `_apply_finalize_commit_router_result`'s legacy-error arm emits only `{"error": ...}` and drops `commit_surfaces`.
- **Edits outside `owned_files`.** WP15 also changed `tasks.py` (re-exports), `test_issue_4141_refresh_planning_commit.py`, `test_tasks_compat_surface.py`, `test_tasks_finalize_seam.py` and `test_coord_loop_tasks.py`. Add a coordination note.
- **Activity log.** The WP file's activity log has no entries. The T079 red outcomes, the commands with counts, and the new non-zero exit for a refused coordination surface (which WP21 needs) belong there.
- **Skipped T004 sub-step.** Not doing `_resolve_finalize_options` is accepted. The rationale (the AST gate plus the scout's correction) is sound.

## Evidence

### Tests at HEAD

- 45 finalize-related files: every `mission_finalize|tasks_finalize` file under `tests/specify_cli/cli/commands/agent/`, every `mission_finalize|tasks_finalize|finalize-tasks` file under `tests/integration`, the two issue-verdict integration files, `tests/lanes/test_issue_4827_*`, `test_planning_commit_classify.py`, `test_issue_4890_*`, `test_claim_ancestry_gate.py` and `tests/agent/test_agent_feature.py`. Result: **1187 passed, 2 skipped, 0 failed**.
- The four regression guards plus the #4827 orphan test: **7 passed**.

### Architectural gates (12 named files)

Result: **338 passed, 6 failed**.

- Inherited from lane-a, also red at `e7b085d26c`:
  - `test_no_dead_symbols` (`COORD_SEED_TRAILER` only);
  - `test_dead_symbol_allowlist_contract`;
  - `test_lock_composition_census` (`coord_seed`);
  - `test_no_unsanctioned_raw_kitty_specs_enumeration_in_src` (`coord_seed:420`);
  - `test_no_new_parallel_dirty_predicate_beyond_known_baseline` (`commit_router::_dirty_paths_in_checkout`).
- Caused by WP15: `test_ruff_format_exclude_ratchet` (B5).

### Red-first at `e7b085d26c`

16 failed and 1 collection error, for these reasons:

| Test | Red for the right reason? |
|---|---|
| US2.2 | yes |
| R11 | yes |
| R17 | yes |
| US5.3 | yes (the new field is missing) |
| R10 | no: red at its precondition only (B4) |
| unchanged-pin control | red only because of the new field |
| unit tests for new helpers | red because the symbols do not exist yet |

### Mutation testing

| # | Mutation | Result |
|---|---|---|
| M1 | `surface_refusal=False` | killed (2 tests) |
| M2 | refusal derived from the legacy status | killed (2) |
| M3 | coordination dirt dropped from `has_relevant_changes` | **survived** |
| M4 | bookkeeping guard removed | killed (2) |
| M5 | `lanes.json` exclusion removed | killed (1) |
| M6 | `raise` on surface refusal removed | killed (2) |

### Static checks

- Diff coverage: **98%** (125 lines; missing `mission_finalize.py:3031` and `:3945`).
- `ruff check`: clean.
- `ruff format --check --force-exclude`: clean.
- `mypy --strict`: 3 errors, identical to base (pre-existing).
- C901: at most 14 in the touched functions.
