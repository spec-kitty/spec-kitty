---
work_package_id: WP01
title: The late-window disposition table
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- NFR-001
- NFR-002
- C-002
- C-003
planning_base_branch: issue-7198-late-window-accounting
merge_target_branch: issue-7198-late-window-accounting
branch_strategy: Planning artifacts for this mission were generated on issue-7198-late-window-accounting. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7198-late-window-accounting unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Core fix
history:
- timestamp: '2026-11-05T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/bookkeeping_projection.py
- tests/coordination/test_projection_teardown.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – The late-window disposition table

## Objective

`assert_late_window_landed` must stop skipping changes. Today it proves only coordination-kind
records; the two status byte-sets and every primary/unclassified path are exempt, and the teardown
then approves the tip and deletes the coordination branch. Widen the assertion to one **disposition**
per changed path so a status event committed outside the coordination worktree, or a late `meta.json`
change, is either proved landed or refused — before the approved-tip advance and before the gate.

## Context

Read first:

- `src/specify_cli/consolidation/bookkeeping_projection.py`:
  - `assert_late_window_landed` (the function you change) — its loop currently has two `continue`s:
    `_classify_status_bookkeeping_filename(...) is MissionArtifactKind.STATUS_STATE` and
    `not is_coordination_kind_file(relpath)`.
  - `_project_status_bookkeeping_to_target` — the union stage. It reads
    `status_feature_dir / "status.events.jsonl"`, which for a coordination Mission is the
    **coordination worktree's working tree**, not the branch's commits. That is why byte equality is
    the wrong proof for the event log.
  - `_rematerialize_status_snapshot` — `status.json` is derived from the unioned event log.
  - `_post_checkpoint_mission_paths` — the *projection's* selector, which must keep excluding primary
    artifacts (`meta.json` excluded on purpose, #5460). Do not reuse or change it; the assertion is
    not a projection.
  - `LateProjectionRefusalKind` / `LateProjectionRefused` / `_late_projection_remedy` in
    `phase_teardown.py` (WP02 writes the remedies; you only add the kind members).
- `src/specify_cli/coordination/coherence.py#is_coordination_kind_file` — the single answer to "is
  this a coordination record".
- `src/specify_cli/status/event_log_merge.py#read_event_log_text` — the canonical JSONL reader; it
  requires a non-empty `event_id` and raises `EventLogMergeError` otherwise.
- `tests/coordination/test_projection_teardown.py` — the #6871 fixtures you write the red cases in:
  `_gated_coord_fixture`, `_coord_run_state`, `_first_run_with_coord_worktree`,
  `_materialise_coord_worktree`, `_commit_in_coord_worktree`, `_append_coord_commit`.

## Subtasks

### T001 — RED: a first run refuses a status event the union never saw

In `tests/coordination/test_projection_teardown.py`, next to the #6871 cases:

1. `run, worktree, tip = _first_run_with_coord_worktree(tmp_path)`.
2. Commit an event onto the coordination branch **outside** the coordination worktree — use
   `_append_coord_commit(repo, coord, f"kitty-specs/{SLUG}/status.events.jsonl", <the worktree log's
   text plus one new event>, "late status event")` so the branch log is ahead of the worktree copy
   the union reads. Give the event a distinct `event_id`.
3. `phase_teardown._teardown_coordination_triple(run)` must raise
   `run_state.CoordinationTeardownError` whose message names the branch, the target, the event path
   and `spec-kitty consolidate --resume`; the coordination branch must still exist, its tip must be
   the late commit, `meta.json`'s `coordination_branch` marker must be intact, and
   `run.coord_tip_after_projection` must still be the pre-window tip.

At the base commit this fails loudly: the run tears down, the branch is gone and the event is not in
the target's log. Paste that failure into the commit message body.

### T002 — RED: the same shape on a `--resume`, plus the positive control

1. Same fixture, `run.is_resume = True` and `run.state.pre_mutation_coord_sha = <pre-window tip>`
   (mirror how `tests/consolidation/test_late_teardown_projection.py` builds a resume). Same
   expectations.
2. Positive control on **both** run kinds: commit the event on the target branch as well (append the
   same line to `_mission_dir(repo) / "status.events.jsonl"` and commit it on `main`), then teardown
   completes, the branch is deleted and the event survives in the target's log.

### T003 — RED: the `meta.json` pair

1. A first-run window whose only change is a coordination-side `meta.json` key the target does not
   carry (`_commit_in_coord_worktree(worktree, f"kitty-specs/{SLUG}/meta.json", ...)`) must refuse
   with the non-coordination kind, keep the triple, and not advance the anchor.
2. The same window where the target's `meta.json` already carries that key (commit it on `main`
   first: this is the mission-number bake / baseline stamp / marker-flatten shape) must tear down
   cleanly.

### T004 — The disposition table

Replace the two exemptions with one disposition per changed path, in this order (first match wins):

1. `coord_bytes == target_bytes` → landed (`continue`). Note both `None` (absent on both) is "landed";
   that case cannot arise from `git_changed_paths`, but keep the comparison total.
2. `coord_bytes is None` → `DELETION_CANNOT_BE_EXPRESSED` (unchanged message and kind).
3. `status.json` (via `_classify_status_bookkeeping_filename` + `_STATUS_FILENAME`) → excluded as a
   derived snapshot: `continue`, with the reason in a comment (it is rematerialized from the unioned
   event log by the projection itself, so its bytes are never an independent record).
4. `status.events.jsonl` → collect the coordination `event_id`s missing from the target's committed
   log into the status bucket.
5. `is_coordination_kind_file(relpath)` → collect into the record bucket (`RECORD_NOT_LANDED`).
6. the coordination document is contained in the target's committed copy → `continue` (carried by the
   target's own copy).
7. otherwise → collect into the non-coordination bucket.

After the loop, raise the first non-empty bucket in that order (deletion is raised inline), so one
refusal names every offending path of its class, bounded to 20 with "(and N more)" exactly as today.

### T005 — Two helpers and two kinds

- `_status_events_missing_from_target(coord_bytes: bytes, target_bytes: bytes | None) -> list[str]`
  — parse both through `specify_cli.status.event_log_merge.read_event_log_text`; return the sorted
  coordination ids not present in the target's id set (`target_bytes is None` → all of them). Catch
  `EventLogMergeError` and re-raise as `LateProjectionRefused(..., kind=STATUS_EVENTS_NOT_LANDED)`
  naming the path and the parse failure — an unreadable log is never "landed" (NFR-002).
- `_json_document_carried_by(coord_bytes: bytes, target_bytes: bytes | None) -> bool` — both sides
  must decode to JSON **objects**; recursive containment: every coordination key present in the
  target, nested objects recursed, everything else `==`. Unparseable or non-object → `False`.
- Add `LateProjectionRefusalKind.STATUS_EVENTS_NOT_LANDED` and
  `LateProjectionRefusalKind.NON_COORDINATION_RECORD_NOT_LANDED` (docstring: one kind per REMEDY,
  #6791). Do not touch the remedy function — WP02 owns it.

### T006 — Docstrings as rules, not exemptions

Rewrite `assert_late_window_landed`'s docstring: it proves every Mission-directory change in the
window, states the four non-refusing dispositions and their reasons, and notes that a first run and a
`--resume` reach the same verdict because the rule is independent of the window base. Leave
`_post_checkpoint_mission_paths`'s projection exclusions alone (they are a different decision) but
correct any sentence that says the *assertion* exempts those files.

## Definition of Done

- The three red cases fail at the base commit and pass after T004–T006.
- `uv run --frozen pytest tests/coordination/test_projection_teardown.py -q -p no:randomly -n 4` is green.
- `uv run --frozen pytest tests/consolidation/test_late_teardown_projection.py -q -p no:randomly -n 4`
  is green except the two new-kind remedy cases (WP02 adds them; if the bijection test fails because a
  kind has no remedy phrase, note it and leave the test to WP02).
- `uv run --frozen ruff check` and `make format-check-files FILES="..."` clean; `uv run --frozen mypy`
  on `bookkeeping_projection.py` clean (the module is under `follow_imports=skip`, so annotate the
  cross-module reads as the existing code does).

## Risks & Mitigations

- **A false refusal on a legitimate resume window.** The resume base reaches back to the merge start.
  Merge-authored commits are byte-identical on the target except `meta.json`, which containment
  covers. Run `tests/consolidation/test_teardown_refusal_resume.py` before believing it.
- **A parse cost regression.** Only the two blobs the loop already read are parsed (NFR-001). Do not
  re-read git for the helper.
- **Aggregation hiding a deletion.** Raise the deletion inline as today; it is first and it is the only
  kind with an unrepairable-by-projection remedy.

## Reviewer guidance

- Check that no path class silently falls out of the loop. Every `continue` must be one of the four
  documented dispositions.
- Check that the status bucket compares **ids**, not bytes, and that the target side is read from
  `target_ref` (a ref), never a working tree.
- Check that `_post_checkpoint_mission_paths` is untouched.
