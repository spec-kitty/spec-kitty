---
work_package_id: WP01
title: One ownership authority for mark-status (#6463)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-002
planning_base_branch: issue-6463-mark-status-owner-authority
merge_target_branch: issue-6463-mark-status-owner-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6463-mark-status-owner-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6463-mark-status-owner-authority unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Ownership authority
history:
- at: '2026-10-31T08:55:00+00:00'
  actor: system
  action: Prompt generated during tasks phase
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_mark_status_owner_authority.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- tests/specify_cli/cli/commands/agent/test_mark_status_owner_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- "6463"
---

# Work Package Prompt: WP01 – One ownership authority for mark-status (#6463)

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via the `/spk-charter-profile-load` skill before reading anything
else. It sets your implementer identity, boundaries and initialization contract for
this work package.

## Objectives & Success Criteria

`spec-kitty agent tasks mark-status <ids> --status done` currently decides which work
package owns a subtask id **twice**: once while resolving (which already refuses a
shared id since #5953) and once while writing, by first match. Three reproduced paths
still write to the wrong work package or record a work-package id as a subtask
(`research/evidence/*.txt`):

1. an id claimed by an authored roster in WP01 and by a structured `tasks.md` row in a
   legacy WP02 resolves as *unique* (roster-or-history instead of the union) and the
   unscoped mark lands on WP01;
2. a bare `WP<digits>` id skips the ownership check entirely and the pipe-table
   resolver claims it, so a WP index row is recorded as `{"WP02": "done"}` on WP02;
3. the emit falls back to `_resolve_history_wp_id` / `owning_wp_from_authored_roster`, so
   when the resolution recorded no owner the event's target is decided by document or
   filename order.

**Done when**:

- each of the five new tests is red on the base commit (`35318ef51c`) and green after
  the change;
- an id claimed by two work packages (through either source, or both) is refused
  unscoped, and each `--wp` writes only its own WP;
- a `WP<digits>` id that no WP authors is rejected with the existing lane-transition
  message **before** any legacy row shape can claim it;
- a `WP<digits>` id that a WP does author as a subtask obeys the ambiguity/`--wp` rules;
- the completion event's `wp_id` comes only from the resolved owner map, and an
  unattributable updated id refuses before any event is appended;
- `tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py` passes unchanged.

## Context

- Authority: `src/specify_cli/core/subtask_rows.py`
  (`authored_roster_owner_map`, `authored_roster_owners`) is the canonical roster
  map. `tasks_outline.history_wp_ids` yields **structured** `tasks.md` owners only —
  checkbox rows, pipe-table rows, and inline `Subtasks:` lists under a WP heading;
  prose mentions never count (#5953, `cf40a5850c`).
- Current code: `src/specify_cli/cli/commands/agent/tasks_mark_status.py`
  - `_owners_for_task` → `authored_roster_owners(...) or history_wp_ids(...)`
  - `_resolve_task_owners` → the #5953 ambiguity/`--wp` refusals, with
    `if re.fullmatch(r"WP\d+", task_id, re.IGNORECASE): continue` skipping WP-shaped ids
  - `_ms_apply_updates` → resolver chain order:
    `_resolve_checkbox` → `_resolve_pipe_table` → `_resolve_inline_subtasks` →
    `_resolve_wp_id` (the lane-transition rejection) → `_resolve_authored_roster`
  - `_ms_emit_subtask_state` →
    `st.task_wps.get(id) or _resolve_history_wp_id(...) or owning_wp_from_authored_roster(...)`
- Contract: `kitty-specs/mark-status-owner-authority-01M68JA8/contracts/mark-status-resolution.md`
- Do not change: the `--wp` flag, the `--json` envelope shape, the existing #5953 and
  #5067 messages, the command docstring/help text, `move-task`, or any other command.

## Detailed Guidance

### T001 — Write the red-first tests

New file `tests/specify_cli/cli/commands/agent/test_mark_status_owner_authority.py`,
following the fixture style of `test_tasks_mark_status.py` (patch
`locate_project_root`, `_find_mission_slug`, `_ensure_target_branch_checked_out`,
`_emit_sparse_session_warning`, `feature_status_lock`; drive the real Typer app with
`CliRunner`). Cases:

1. **Mixed sources are ambiguous.** WP01 authors `[T001]`; legacy WP02 has no
   `subtasks:` key but claims `T001` through `## WP02` + `Subtasks: T001` in
   `tasks.md`. Unscoped `mark-status T001` exits 1 naming `WP01, WP02` and appends no
   event. Today: exit 0, event on WP01.
2. **Scoped marks stay scoped.** Same fixture: `--wp WP01` and `--wp WP02` each write
   one event with the matching `wp_id`; `--wp WP09` refuses. Today: the WP02 mark is
   refused because the roster owner replaces the tasks.md claim.
3. **A WP index row cannot claim a WP id.** `tasks.md` carries
   `| WP | Title | Subtasks |` / `| WP02 | Foundation | T002 |`; no roster authors
   `WP02`. `mark-status WP02 --status done` exits 1 with
   `mark-status does not change work-package lanes` and appends no event. Today:
   `{"wp_id": "WP02", "subtasks": {"WP02": "done"}}`, exit 0.
4. **A `WP`-shaped subtask needs `--wp`.** WP01 authors `subtasks: [WP02, T001]`.
   Unscoped `mark-status WP02` exits 1 naming WP01 as the owner (and the lane
   transition for the work package itself); `--wp WP01` writes one event with
   `wp_id: WP01`, `subtasks: {"WP02": "done"}`. Today: unscoped resolves through the
   fallback, scoping is bypassed.
5. **The emit refuses an unattributable id.** Call `_ms_emit_subtask_state` (or
   `_do_mark_status` through the Typer app) with a state whose `updated_tasks` contains
   an id absent from `task_wps` on a fixture where the old fallback would find a WP;
   assert a refusal (exit 1 / `ValueError`) and that no event file was written.
   Today: the fallback attributes it.

Add one compatibility case (NFR-001): the shipped shape — two WP files authoring
`T001` only in their frontmatter, `tasks.md` with plain subtask lines — keeps today's
behaviour exactly (unscoped mark of a unique id writes one event; a repeat is
`already_satisfied`).

Run each new test on the base commit and keep the red output for T005.

### T002 — Union the ownership sources

`_owners_for_task` returns the sorted, de-duplicated union of
`authored_roster_owners(owner_map, task_id)` and
`history_wp_ids(tasks_content, task_id)`. Keep `_resolve_task_owners`'s two #5953
refusals and their message strings exactly as they are; only the owner *set* changes.
Keep the unreadable-roster fail-closed arm. Do not add a third owner derivation and do
not consult prose.

### T003 — Scope `WP`-shaped ids

Replace the blanket `WP\d+` skip in `_resolve_task_owners`:

- compute `owners` first;
- if `owners` is non-empty, apply the same ambiguous/`--wp` rules as any other id, with
  a message that names the owner and distinguishes the two readings (the subtask of
  that WP vs the work package, which is `move-task`'s job);
- if `owners` is empty and the id is `WP\d+`-shaped, keep it out of `task_wps` and let
  the lane-transition rejection run **first** in the resolution chain so
  `_resolve_pipe_table` / `_resolve_inline_subtasks` / `_resolve_checkbox` can never
  claim it (a WP index row is the reproduced case). Keep `_resolve_wp_id` as the single
  producer of that message; keep the chain's behaviour for every non-WP-shaped id.

### T004 — Attribute the emit from the recorded owner only

`_ms_emit_subtask_state` reads `st.task_wps` only. Delete the
`_resolve_history_wp_id` / `owning_wp_from_authored_roster` fallbacks. It already
collects `unresolved_tasks` before the emit loop — keep the refusal there so a batch
never half-writes, and make the raised message name every unattributable id. Leave the
`owning_wp_from_authored_roster` helper in place (it is still the existence probe behind
`_resolve_authored_roster` and part of the `tasks` compat re-export surface).

### T005 — Prove red→green and compatibility

```bash
uv run pytest tests/specify_cli/cli/commands/agent/test_mark_status_owner_authority.py \
              tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py \
              tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py -q
uv run mypy --strict src/specify_cli/cli/commands/agent/tasks_mark_status.py
```

Record the base-commit red output (each new test, with its failure reason) in the WP
history note / PR body. Do not run the full suite.

## Branch Strategy

- Planning base branch: `issue-6463-mark-status-owner-authority`.
- Merge target: `issue-6463-mark-status-owner-authority`.
- Execution happens in the lane worktree the runtime allocates from `lanes.json`; never
  hand-build a workspace path. Completed changes merge back into the merge target
  branch, and the operator — not the agent — lands it on `main`.

## Definition of Done

- The five cases are pinned by tests that fail on the base commit and pass on the tip.
- No existing mark-status test changed except where a test asserted the superseded
  first-match behaviour (then say why in the WP history note).
- `mypy --strict` clean on the changed module; no new dependency.
- Commit messages carry no machine-local path or personal data.

## Reviewer Guidance

- Verify each new test is red on `35318ef51c` — not merely absent before the change.
- Verify the refusal paths append no event (check for a missing `status.events.jsonl`,
  not just a non-zero exit).
- Verify no ownership fallback survives in the write path (`grep` the emit function).
- Verify the #5953 messages are byte-identical.
