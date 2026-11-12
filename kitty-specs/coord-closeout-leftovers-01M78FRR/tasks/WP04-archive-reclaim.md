---
work_package_id: WP04
title: Archive reclaim (#4041)
dependencies: []
requirement_refs:
- C-003
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-005
- SC-002
planning_base_branch: fix/7598-coord-closeout-leftovers
merge_target_branch: fix/7598-coord-closeout-leftovers
branch_strategy: Planning artifacts for this mission were generated on fix/7598-coord-closeout-leftovers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7598-coord-closeout-leftovers unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
- T017
phase: Phase 2 - Closeout fixes
history:
- at: '2026-11-12T18:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/missions/archive_reclaim.py
create_intent:
- src/specify_cli/missions/archive_reclaim.py
- tests/specify_cli/cli/commands/test_archive_reclaim.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/archive.py
- src/specify_cli/missions/archive_reclaim.py
- tests/architectural/test_destructive_op_routing.py
- tests/architectural/test_json_contract_enumeration.py
- tests/specify_cli/cli/commands/test_archive_reclaim.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Archive reclaim (#4041)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before reading further.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address all feedback; record progress with `add-history`.

---

## Objectives & Success Criteria

Operator ruling Decision `01M78G5TMBJWFRE1ZPVSS2ATKN`: a new `spec-kitty archive reclaim <mission>`,
refused unless archived; reuse `teardown_coordination_topology`, a tip-bound absorption-proved
branch delete (one new named `operator_intent` caller in the routing-gate pin), and
`flatten_coordination_metadata` + commit.

Done when (FR-005..FR-008, C-003, NFR-005; contract `contracts/cli-refusals.md`):
- Reclaim of an archived, landed coordination Mission removes worktree, branch and marker (committed), reports each step, exits 0.
- Refusals (exit 1, named code, nothing changed): `RECLAIM_NOT_ARCHIVED`, `RECLAIM_NO_COORDINATION`, dirty coordination worktree (existing teardown refusal; triple kept), `RECLAIM_UNABSORBED` (names the branch; for a canceled Mission points at `spec-kitty mission close --discard`; on git < 2.38 says the proof is unsupported).
- Idempotent: a second run says nothing is left and exits 0; a partial state finishes the remaining steps.
- `archive create` of a Mission that still holds a coordination triple prints the reclaim command.

## Context & Constraints

Facts (`research/code-grounding.md` §5, §7):
- `archive create`: `cli/commands/archive.py:43-118`; core `missions/_archive.py:300-357` is **record-only** ("never mutates mission state", `:30-32`) — do NOT put git work there. `is_mission_archived` (`_archive.py:279`) has no production caller yet (listed in `tests/architectural/dead_symbol_allowlist.yaml:1335`); this WP gives it one — remove the allowlist entry if the dead-symbol gate requires (check `tests/architectural/test_no_dead_symbols.py` semantics; the allowlist file is shared, so a one-line removal is a recorded leeway edit).
- Worktree: `coordination/teardown.py::teardown_coordination_topology(repo_root, mission_slug, mid8, *, persist=..., check_ledger=..., follow_up_command=..., ...)` (`:323-446`): ledger guard, optional gate, retrospective persist, then `CoordinationWorkspace.teardown` through `guarded_worktree_remove`; dirty → `CoordTeardownKeptOnlyCopy` (exit 76 in consolidate). Pass `follow_up_command` = the reclaim command so its remedy points back here. Decide `persist` from how `mission close` calls it for a merged Mission (`cli/commands/mission_type.py:566-607`): mirror that.
- Branch: `git/destructive_guard.py::guarded_branch_delete(repo_root, branch, creation_base=None, operator_intent=LANDED_INTENT, expected_tip=<tip read before the delete>)`; a unique-commit tip is kept under `refs/spec-kitty/discarded/` (keep-record), and the delete is a compare-and-swap. Only call it after the absorption proof passes.
- Absorption proof: `lanes/lane_tip.py::is_absorbed(repo_root, tip, target, base=None)` (ancestor, else `merge-tree --write-tree` no-op; raises `AbsorptionUnsupported` on git < 2.38 → refuse).
- Marker: `mission_metadata.py::flatten_coordination_metadata(feature_dir)` (sole authority, `tests/coordination/test_flatten_primitive_single_source.py`), then commit through the canonical mission commit path (`commit_for_mission` / the placement seam the `mission close` flatten uses — copy its call, do not hand-roll git; C-004).
- Names: compose the worktree path/branch only through `lanes/branch_naming.py` / `CoordinationWorkspace` (`tests/architectural/test_no_worktree_name_guess.py`).
- Gates: `tests/architectural/test_destructive_op_routing.py::_OPERATOR_INTENT_CALLERS` (`:618-623`) — add exactly one entry `("src/specify_cli/missions/archive_reclaim.py", "<function name>")` (ruled). `tests/architectural/test_json_contract_enumeration.py::ADOPTED` (`:108+`) — classify `archive reclaim` beside `archive create` / `archive list` if it takes `--json`.
- No new `doctor workspaces` flag; no change to `_archive.py`.

## Branch Strategy

Planning base / merge target: `fix/7598-coord-closeout-leftovers`.

```bash
spec-kitty agent action implement WP04 --agent claude --mission coord-closeout-leftovers-01M78FRR
```

## Subtasks & Detailed Guidance

### Subtask T013 – Red: `archive reclaim` CLI tests

- **Steps**:
  1. `tests/specify_cli/cli/commands/test_archive_reclaim.py`, `CliRunner` over the real `archive` app with a real tmp git repo. Template: `tests/specify_cli/workspace/test_landed_worktrees_mission_lane_prune.py` (real git, `_SLUG = "demo-01ABCDEF"`) plus `tests/terminus/conftest.py` builders for a coordination Mission.
  2. Fixture: a coordination Mission whose coordination branch content is on the target (simplest: the target merges the coordination branch with a real merge, so leg 2 of the proof holds), all WPs done, archived via `archive create --by t --reason done`, coordination worktree still registered.
  3. Cells: happy path (worktree gone from `git worktree list`, branch gone, `meta.json` has no `coordination_branch` and `flattened: true`, a commit was made, exit 0); not archived → `RECLAIM_NOT_ARCHIVED`; single_branch Mission → `RECLAIM_NO_COORDINATION`; dirty coordination worktree → refusal, triple kept; unabsorbed coordination commit → `RECLAIM_UNABSORBED`, triple kept; second run → "nothing left", exit 0; worktree already gone but branch + marker present → finishes.
  4. Red on the base: `No such command 'reclaim'`. Commit `test(archive): reclaim an archived Mission's coordination triple (#4041, red)`.

### Subtask T014 – Measure the absorption proof on a realistic fixture (R1 — escalation point)

- **Purpose**: plan risk R1. After a **squash** landing (the default), the coordination branch may carry planning or `meta.json` bytes the target later changed, so `is_absorbed` may say "not absorbed" on the canonical case.
- **Steps**:
  1. Build the realistic case: a coordination Mission consolidated by `spec-kitty consolidate` (default squash) whose teardown kept the triple (the #7491 fixture's first run, exit 76, is one), then archived.
  2. Run `is_absorbed(repo, coord_tip, target, None)` and record the result and the differing paths (`git merge-tree --write-tree target coord_tip`, then diff trees) in `traces/approach.md`.
  3. **If the proof refuses the canonical case: STOP, record it in `traces/tooling-friction.md`, and escalate to the orchestrator with the measured paths and two options** (e.g. scope the proof to non-bookkeeping paths; or require `merged_at` + a recorded landing). Do not invent a proof.
  4. If it passes, continue.

### Subtask T015 – Reclaim service module

- **Steps**:
  1. `src/specify_cli/missions/archive_reclaim.py`: `reclaim_archived_mission(repo_root, mission_selector) -> ReclaimReport` with a frozen dataclass report (`steps: tuple[ReclaimStep, ...]`, `nothing_left: bool`) and `ReclaimRefused(Exception)` carrying `error_code` and `remedy`.
  2. Order (each step idempotent, skipped when already done): resolve Mission → `is_mission_archived` else refuse → read the coordination branch from `meta.json` (no marker and no branch → `nothing_left`; never-coordination topology → `RECLAIM_NO_COORDINATION`) → if the branch exists: read tip, prove absorption into the Mission's `target_branch` (refuse `RECLAIM_UNABSORBED`) → worktree teardown via the seam (if registered) → `guarded_branch_delete(..., LANDED_INTENT, expected_tip=tip)` → flatten + commit the marker.
  3. Keep each function ≤ 15 complexity; constants for codes.

### Subtask T016 – CLI subcommand and `archive create` pointer

- **Steps**:
  1. `cli/commands/archive.py`: `@app.command("reclaim")` taking the Mission selector and `--json`; render each step; refusals print the code line `Error code: <CODE>.` and the remedy; exit 1. Help text with an example.
  2. `archive create`: after a successful archive, when the Mission's `meta.json` still names a coordination branch, print `Reclaim its coordination worktree and branch with: spec-kitty archive reclaim <slug>` (and include it in the JSON as a field only if the JSON contract test allows; otherwise text-only).

### Subtask T017 – Gate pin and JSON contract enumeration

- **Steps**:
  1. Add the one named intent caller to `_OPERATOR_INTENT_CALLERS` with a comment citing #4041 and the ruling.
  2. Classify `archive reclaim` in `ADOPTED` (valid args, exit code, fixture) like `archive create`.
  3. Run both gate files.

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/test_archive_reclaim.py tests/integration/test_mission_archiving.py tests/specify_cli/missions/test_archive_locked_append.py
.venv/bin/python -m pytest -q tests/architectural/test_destructive_op_routing.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_git_path_listing_owner.py tests/coordination/test_flatten_primitive_single_source.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py
ruff / format --force-exclude / mypy on changed files
```

## Risks & Mitigations

- R1 above (stop and escalate).
- Destroying unabsorbed work: proof first, CAS delete, keep-record for unique commits.

## Review Guidance

- Red→green through the CLI; every refusal leaves the triple unchanged (assert on `git worktree list`, branch list and `meta.json` bytes).
- Exactly one new intent caller; `_archive.py` untouched.

## Progress & Status

Event log only.
