---
work_package_id: WP02
title: Protected-target override refusal
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
planning_base_branch: issue-6464-protected-target-override-refusal
merge_target_branch: issue-6464-protected-target-override-refusal
branch_strategy: Planning artifacts for this mission were generated on issue-6464-protected-target-override-refusal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6464-protected-target-override-refusal unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-protected-target-override-refusal-01M68JPV
base_commit: 5b145d9f9b80c8af49d892201acbe5bb14e30f9c
created_at: '2026-10-31T09:22:48.650755+00:00'
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - The guard
history:
- at: '2026-10-31T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/preflight.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/preflight.py
- src/specify_cli/consolidation/entry_preflight.py
- src/specify_cli/consolidation/forecast.py
- src/specify_cli/orchestrator_api/consolidation.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6464'
---

# Work Package Prompt: WP02 – Protected-target override refusal

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completing, and record what you changed with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

- `consolidate --target <protected>` where `<protected>` is **not** the Mission's recorded target is
  refused **before any branch moves**, with `PROTECTED_BRANCH_REFUSED`, an actionable message naming
  both branches, and a followable `next_step`.
- The same refusal reaches `--dry-run --json` and `orchestrator-api consolidate-mission`.
- WP01's new tests go red → green; every pre-existing control in both touched test modules stays green
  (that is FR-004 and the whole point of the scope: the recorded-target decision belongs to #5385 and
  must not change).
- No new error code, no second protected-branch list, no growth of the CLI shim
  (`src/specify_cli/cli/commands/consolidate.py`) — its decomposition rules forbid adding logic there.

## Context & Constraints

- Read first: `spec.md` (FR-001/002/003, NFR-001/002, C-001), `plan.md` (IC-01 and its three risks),
  `research.md` (D1–D5), ADR `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md`, follow-up
  2026-09-30 ("Protected-target preflight" — it states the existing refusal reads the recorded meta
  target, not `--target`).
- The existing seam to sit beside: `src/specify_cli/consolidation/preflight.py::refuse_protected_status_target`
  (#5385). It returns a `specify_cli.coordination.types.Refused`, and its callers render
  `error_code`, `message`, `next_step`.
- The protection authority is `specify_cli.git.protection_policy.ProtectionPolicy`:
  `resolve_for_mission(repo_root, mission_slug)` then `is_protected_target(branch, primary_branch=...)`.
  It already folds the operator hatch (`SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`), the configured
  `protection.protected_branches` list, the repo's primary branch and the mission-scoped
  `commit_to_target` bypass. Do **not** re-read `.kittify/config.yaml`, do **not** compare branch names
  by hand, and do **not** consult GitHub branch protection (out of scope; see C-002 / the ADR residual).
- `PROTECTED_BRANCH_REFUSED` already exists in `specify_cli.coordination.types` and in the
  status-write protocol's allowlist. Reuse it; add no new code (C-001).
- The recorded target must be read with the **no-override** resolver:
  `specify_cli.core.paths.resolve_merge_target_branch(main_repo, mission_slug, None)[0]`. The
  executor's manifest target is already retargeted by `--target`
  (`consolidation/executor.py::_load_lanes_manifest`), so using it would make the guard vacuous.
- Quality: `ruff check`, `ruff format --check`, `mypy` clean, complexity ≤ 15, no new `# type: ignore`.
  Never run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run the two touched test modules.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6464-protected-target-override-refusal`
- **Merge target branch**: `issue-6464-protected-target-override-refusal`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with
`spec-kitty agent action implement WP02 --agent claude --mission protected-target-override-refusal-01M68JPV`.

## Subtasks & Detailed Guidance

### Subtask T005 – The decision seam

- **Purpose**: one function, one decision, three callers.
- **Steps**:
  1. In `src/specify_cli/consolidation/preflight.py`, add
     `refuse_protected_target_override(main_repo: Path, mission_slug: str, *, recorded_target: str, effective_target: str) -> Refused | None`.
  2. Return `None` when `effective_target == recorded_target` (a restatement is not a retarget) or when
     the effective target is not protected. Otherwise return a `Refused` with
     `error_code=PROTECTED_BRANCH_REFUSED` and `destination_ref=effective_target`.
  3. The **message** names both branches and the root cause in one or two sentences: the
     `--target` override would commit the branch-integration squash straight onto a branch this
     project protects, outside the protection gate every status commit goes through.
  4. The **next_step** gives three concrete routes: drop `--target` (name the recorded target), or
     correct `target_branch` in the Mission's `meta.json` if the record is wrong (so the recorded-target
     policy decides), or set `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1` when a direct local landing
     on that branch really is intended.
  5. Resolve the policy once (`ProtectionPolicy.resolve_for_mission`) and ask
     `is_protected_target(effective_target, primary_branch=<repo primary>)`; resolve the primary with
     the existing helper the codebase uses (`specify_cli.core.git_ops.resolve_primary_branch`) — check
     its signature before calling it.
  6. Keep it pure: no printing, no exits. Callers render.
- **Files**: `src/specify_cli/consolidation/preflight.py`

### Subtask T006 – The pre-lock CLI door

- **Purpose**: the real run refuses before the lock and before any mutation, with the same rendering
  shape as #5385.
- **Steps**:
  1. In `src/specify_cli/consolidation/entry_preflight.py`, extend
     `_refuse_protected_status_target_or_continue(...)` — or add a sibling called immediately after it
     from the same executor call site — so the override verdict is consulted **after** #5385's probe
     (pinned text for the recorded-target case must stay byte-identical).
  2. Render `Error: <code>: <message>` plus `  Next step: <next_step>`, then the existing
     `_protected_refusal_footer(...)` line, then `raise typer.Exit(1)`. No traceback.
  3. Pass the recorded target from `resolve_merge_target_branch(main_repo, mission_slug, None)` and the
     effective target from `lanes_manifest.target_branch`.
- **Files**: `src/specify_cli/consolidation/entry_preflight.py` (and, only if the call site genuinely
  must change, `src/specify_cli/consolidation/executor.py` — note it in the completion note; prefer the
  no-touch route of extending the existing function's body).

### Subtask T007 – `--dry-run` parity

- **Purpose**: the preview reports the same code and remedy.
- **Steps**:
  1. In `src/specify_cli/consolidation/forecast.py`, extend
     `_refuse_protected_status_target_in_forecast` (or add its sibling) so the override verdict is
     emitted through `_emit_dry_run_error(error_msg=..., json_output=..., error_code=...)` and exits 1.
  2. The forecast holds the **un-retargeted** manifest but already receives `resolved_target_branch`;
     use that as the effective target and `lanes_manifest.target_branch` as the recorded one. Do not
     resolve the recorded target twice if it is already in hand.
- **Files**: `src/specify_cli/consolidation/forecast.py`

### Subtask T008 – orchestrator-api parity

- **Purpose**: the machine contract refuses identically.
- **Steps**:
  1. In `src/specify_cli/orchestrator_api/consolidation.py`, next to
     `_refuse_protected_status_target`, consult the override verdict before any lane/mission/target
     mutation, on both the code-lane path and the planning-artifact-only closeout.
  2. Put the policy's `error_code`, `message` and `next_step` in the existing failure envelope
     (the same shape `_refuse_protected_status_target` produces).
- **Files**: `src/specify_cli/orchestrator_api/consolidation.py`

## Definition of Done

- WP01's new cases pass; every pre-existing control in both modules still passes.
- A refused run moves no branch, writes no merge record, adds no reflog entry and prints no traceback.
- `ruff check` / `ruff format --check` / `mypy` clean on the four touched source files.
- No new error code, no new config read, no change under `packs/`.

## Reviewer Guidance

- Is the recorded target read from `meta.json` (no-override resolver), not from the retargeted manifest?
- Is the guard scoped exactly to "effective != recorded AND effective is protected"? Confirm the
  #5385 controls for coordination / all-done / `commit_to_target` still pass — a blanket refusal is the
  failure mode this WP must avoid.
- Does the refusal precede every mutation and the merge lock (NFR-001)?
- Is `PROTECTED_BRANCH_REFUSED` reused rather than a new code invented (C-001)?
