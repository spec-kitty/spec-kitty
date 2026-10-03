---
work_package_id: WP04
title: Doctor heal reverts only recorded strand commits (#5572)
dependencies:
- WP02
requirement_refs:
- FR-007
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-004
- SC-001
- SC-002
planning_base_branch: kitty/rc5-consolidate-regressions
merge_target_branch: kitty/rc5-consolidate-regressions
branch_strategy: Planning artifacts for this mission were generated on kitty/rc5-consolidate-regressions. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/rc5-consolidate-regressions unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rc5-consolidate-regressions-01M4189Z
base_commit: fe5ea1df9fbba9fd6906a10557cff1f521e46d1f
created_at: '2026-10-03T17:10:52.368135+00:00'
subtasks:
- T014
- T015
- T016
- T017
- T018
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/terminus/test_repro_5572.py
execution_mode: code_change
model: claude-sonnet-5-5-high
owned_files:
- src/specify_cli/coordination/coherence.py
- src/specify_cli/consolidation/state.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- tests/terminus/test_repro_4973.py
- tests/terminus/test_repro_5572.py
- tests/coordination/test_coherence_integrity.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – Doctor heal reverts only recorded strand commits (#5572)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP04 --agent claude`

## Objective

`spec-kitty doctor coordination --fix` (and the `consolidate --resume` heal that shares the
primitive) must revert only the stranded `done` commits the failed consolidation wrote, recorded
by SHA when the marker is written. If the range holds any other status-log commit, or the marker
predates this field, it refuses: no revert, no "Healed", non-zero exit, manual-reconcile advice.

## Context

> **Ownership note (executor.py).** `src/specify_cli/consolidation/executor.py` is owned by WP02
> (finalize-tasks forbids overlapping ownership). This WP depends on WP02 and may edit ONLY
> `_persist_coord_reconcile_marker` and `_heal_pending_coord_reconcile` in that file, under the charter's ownership-map leeway. Any other executor.py
> change needs the orchestrator's approval first.

Read `research.md` (#5572) and `plan.md` (IC-04).

- Marker writer `_persist_coord_reconcile_marker` (`consolidation/executor.py:1075-1110`, schema
  ~1102-1109: coord_ref, captured_sha, coord_worktree, stranded_wp_ids, revert_error, detected_at).
  All marker writes go through `_restore_and_guard_coord_coherence` (~1152, nine call sites), all
  after the done bake (`_record_merged_wps_done_for_merge` ~911; capture ~904). At write time,
  `rev-list captured_sha..coord_ref -- <status.events.jsonl>` is exactly this run's strand.
- Reader/heal: `_recorded_strand_shas` (`coordination/coherence.py:546-580`) re-derives at heal
  time; `repair_coord_strand` (~613) reverts; `_head_shape_is_expected` (~471-503).
- Callers: `cli/commands/_coordination_doctor.py` (~1286; marker parse ~1045) and
  `consolidation/executor.py` `_heal_pending_coord_reconcile` (~1132; reached from `--resume` ~3568).
- Typed home: `consolidation/state.py` (`pending_coord_reconcile`); also read by
  `consolidation/rollback.py` and `consolidation/resolve.py` — keep those readers working (read
  the new field tolerantly there; do not edit them unless required — if required, report to the
  orchestrator first because they are outside this WP's owned files).
- Keep `_recorded_strand_shas` the single reader, preferring persisted SHAs; no second revert path.
- Executor.py is shared with WP02 and WP04's siblings: touch only the marker writer and the heal
  caller.
- Old test false green: `tests/terminus/test_repro_4973.py:84-87` uses a `THIRD_PARTY.txt` commit.

> Post-tasks squad: `consolidation/rollback.py:390` (sets marker to None) and `resolve.py:172` (enumerates markers) need no edits provided `strand_shas` is optional with a default in `state.py`, so legacy markers still load (and are then refused by the heal).

### Subtask T014: Red-first doctor test (separate commit)

- **Steps**: in `tests/terminus/test_repro_5572.py` (reuse the `test_repro_4973.py` fixture
  shape): real stranded `done` for WP02 committed on the coordination branch with actor
  `spec-kitty-merge`, a marker via the public `ConsolidationState`/`save_state` API, then a real
  reviewer reopen via the status emit API (`to_lane="in_progress"`, `force=True`) committed on the
  coordination branch. Cover both a sibling-WP reopen and a WP01 reopen. Invoke
  `doctor coordination --fix` via CliRunner.
  Assert ideal: exit ≠ 0; "Healed" absent; reopen event present at coord HEAD; no new revert
  commit; marker kept.
- **Validation**: RED on base; commit alone (`test(WP04): red-first #5572`).

### Subtask T015: Record strand SHAs in the marker

- **Steps**: add `strand_shas` to the marker (state.py typed field + writer), computed at write time.
- **Validation**: unit test for the writer.

### Subtask T016: Heal reverts only recorded SHAs or refuses

- **Steps**: thread `strand_shas` into `repair_coord_strand`; if the heal-time status-log commit
  set in `captured_sha..HEAD` ≠ recorded set → refuse (a typed result such as
  `foreign_status_commits`), no revert; legacy marker without `strand_shas` → refuse.
- **Validation**: unit tests in `tests/coordination/test_coherence_integrity.py`.

### Subtask T017: Doctor + resume surface the refusal honestly

- **Steps**: doctor maps refusal to an error finding (exit 1) with a manual-reconcile hint naming
  the foreign commits; never prints "Healed". `_heal_pending_coord_reconcile` passes the recorded
  SHAs and treats refusal as non-success.
- **Validation**: T014 green; positive control (strand-only) heals and clears the marker.

### Subtask T018: Update the #4973 repro to a real status commit

- **Steps**: make `test_repro_4973.py`'s "third party" case include a real status-log commit
  (or keep it and rely on T014) so the original repro is no longer vacuous; run coordination +
  terminus heal tests.

## Definition of Done

- T014 red on base, green on tip; strand-only positive control green; legacy marker refuses.
- Lint/format/mypy clean; subtasks marked done.

## Risks

- Rollback/resolve readers of the marker break on the new field — verify they ignore unknown keys.

## Reviewer Guidance

- Verify the heal never reverts a commit it did not record; refusal is non-zero and honest.
