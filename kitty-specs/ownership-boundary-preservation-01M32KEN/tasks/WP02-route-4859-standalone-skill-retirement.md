---
work_package_id: WP02
title: 'Route #4859 standalone-skill retirement through the guard'
dependencies:
- WP01
requirement_refs:
- C-001
- C-006
- FR-003
- FR-004
- NFR-001
- NFR-006
planning_base_branch: fix/ownership-boundary-preservation
merge_target_branch: fix/ownership-boundary-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/ownership-boundary-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ownership-boundary-preservation unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
phase: Phase 2 - Route destructive sites
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/m_3_2_0rc45_retire_standalone_skill_surface.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_3_2_0rc45_retire_standalone_skill_surface.py
- tests/specify_cli/upgrade/migrations/test_m_3_2_0rc45_retire_standalone_skill_surface.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Route #4859 standalone-skill retirement through the guard

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

- **Guard performs the delete.** T009 routes by REPLACING the raw `_safe_rmtree`/`_safe_unlink` at
  `:196`/`:198` with `guard_destructive_removal(dest, project_path, prover=ManifestProver(...),
  is_tree=<dir?>)` — the guard performs the removal when owned; **no raw destructive literal remains
  at the site** (the caller still prunes the manifest entry). See contract C1 invariant 0 / C3.
- **Owned-delete is a GREEN-on-base non-vacuity anchor**, not a RED repro: on base the name-only
  loop already deletes owned targets. The **preserve-flip** and **drifted-hash** tests are the
  RED-on-base repros. Keep the new owned-delete test required.

## Objectives & Success Criteria

Route the standalone-skill retirement migration through the shared `ManifestProver` so it preserves
an unmanifested or byte-drifted retired-basename skill and removes only proven-owned ones — closing
#4859 (P0).

- The `apply()` delete loop routes every candidate path through
  `guard_destructive_removal(..., prover=ManifestProver(...))`, checking BOTH the managed-skills
  and command-skills manifests per path.
- An unmanifested `.claude/skills/spec-kitty.advise/SKILL.md` with distinctive bytes SURVIVES (in
  place or in a recoverable backup) + the migration reports `success` + a diagnostic names the
  preserved path.
- A genuinely manifest-owned retired skill (entry + `content_hash == sha256(current bytes)` + copy
  delivery on disk) is STILL removed and its manifest entry pruned.
- A drifted-hash manifested skill is PRESERVED (fail-closed toward user edits), not deleted.
- **Success**: the flipped + new tests are RED on base `32cfc272ee`, GREEN on this WP's final
  commit; `test_apply_prunes_managed_and_command_manifests` stays green (C-006).

## Context & Constraints

- **Requirement refs**: FR-004, FR-003, NFR-001, NFR-006, C-001, C-006.
- **Bug (from spec)**: `apply()` `_safe_rmtree`/`_safe_unlink`s any path whose basename ∈
  `RETIRED_STANDALONE_SKILL_NAMES` before manifest pruning; manifests only prune stale *entries*,
  never protect an unmanifested collision.
- **Anchors** (verified on base): `_is_retired_skill_path` uses
  `Path(path).parts ∩ RETIRED_STANDALONE_SKILL_NAMES` (name-only — the exact hazard);
  `_safe_unlink`/`_safe_rmtree` at lines ~29/37; `apply()` at line ~183; the delete loop lands
  around lines ~196/198.
- **Design**: [contracts/ownership-guard-contract.md](../contracts/ownership-guard-contract.md) C4
  US1; [data-model.md](../data-model.md) census row 10; [spec.md](../spec.md) US1.
- **Charter**: unprovable ⇒ preserve + warn (L472); document the ownership proof in code (L479).

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T008 – Red-first: flip the bug-locking test + add owned-delete + drifted-hash

- **Purpose**: Lock the correct behavior BEFORE the fix (ATDD C-001). The current test locks in the
  bug; flipping it makes the defect visible as RED on base.
- **Steps**:
  1. **FLIP** `test_apply_removes_retired_skill_surface_from_all_known_project_roots`: seed an
     unmanifested retired-basename skill (e.g. `spec-kitty.advise`) with distinctive bytes; assert
     it SURVIVES (in place or recoverable backup) and that a diagnostic names it as
     not-package-owned. (Was asserting deletion.)
  2. **ADD** a NEW owned-delete test: a managed OR command manifest entry whose
     `content_hash == sha256(current on-disk bytes)`, `copy` delivery, file present ⇒ the skill is
     removed and its entry pruned.
  3. **ADD** a drifted-hash preserve test: a manifested skill whose bytes differ from the recorded
     `content_hash` ⇒ preserved with a diagnostic, not deleted.
  4. Confirm RED on base `32cfc272ee` (via `PYTHONPATH=<worktree>/src` against the merge-base) and
     GREEN after T009/T010.
- **Files**: `tests/specify_cli/upgrade/migrations/test_m_3_2_0rc45_retire_standalone_skill_surface.py`.
- **Notes**: keep `test_apply_prunes_managed_and_command_manifests` green — do not regress
  legitimate entry pruning.

### Subtask T009 – Route the delete loop through `ManifestProver`

- **Purpose**: Replace the name-only delete with an ownership-gated one.
- **Steps**:
  1. For each candidate path, call `guard_destructive_removal(path, project_path,
     prover=ManifestProver(<managed + command>))`. Configure the prover to check BOTH the
     managed-skills manifest (`_replacement_is_owned`) and the command-skills manifest
     (`fingerprint_file == entry.content_hash`) — the entry shapes/hash formats differ.
  2. On `verdict.owned` ⇒ perform the existing `_safe_rmtree`/`_safe_unlink` delete.
  3. On unprovable, when a whole skill DIRECTORY is being removed, pass a `backup_parent` OUTSIDE
     the doomed tree (e.g. `.kittify/.migration-backup/<ts>/`) so the archive survives; when the
     parent survives, preserve in place.
- **Files**: `src/specify_cli/upgrade/migrations/m_3_2_0rc45_retire_standalone_skill_surface.py`.
- **Notes**: the guard does not change the delete mechanics — the caller still owns the actual
  `_safe_*` calls.

### Subtask T010 – Diagnostics, entry pruning, and in-code rationale

- **Purpose**: Success-preserving preservation + honest manifest bookkeeping + charter L479.
- **Steps**:
  1. Append `verdict.diagnostic` to the migration's `warnings` on preservation (never a non-zero
     exit — FR-008).
  2. Prune the manifest entry ONLY for paths actually removed (owned verdicts); leave entries for
     preserved paths intact.
  3. Add a one-line in-code comment at the routed site documenting the ownership proof (manifest
     entry + matching content hash + copy delivery ⇒ owned; else preserve) — NFR-006.
- **Files**: `src/specify_cli/upgrade/migrations/m_3_2_0rc45_retire_standalone_skill_surface.py`.

## Test Strategy

- Run the module's mirror test file plus the migrations subsystem:
  ```bash
  PWHEADLESS=1 .venv/bin/python -m pytest \
    tests/specify_cli/upgrade/migrations/test_m_3_2_0rc45_retire_standalone_skill_surface.py -q
  uv run --frozen mypy --strict src/specify_cli/upgrade/migrations/m_3_2_0rc45_retire_standalone_skill_surface.py
  ```
- Verify RED-on-base → GREEN-on-fix for the flipped + new tests (record commands + counts in the PR).

## Risks & Mitigations

- **Two manifest shapes** — check managed AND command per path (missing either re-opens the bug).
- **Directory removal loses the archive** — mandatory external `backup_parent` (contract C1.4).
- **Vacuous preserve-everything** — the NEW owned-delete test is what proves non-vacuity; without
  it a preserve-everything guard passes all #4859 acceptance.

## Review Guidance

- Confirm the flipped test asserts SURVIVAL + diagnostic and the NEW owned-delete test asserts
  removal + entry pruning.
- Confirm RED-on-base evidence in the PR.
- Confirm the in-code ownership-proof rationale comment is present.
- Confirm `test_apply_prunes_managed_and_command_manifests` still passes.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
