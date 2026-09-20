---
work_package_id: WP04
title: Synthesize fresh-gate + worktree wiring for generate/synthesize/resynthesize
dependencies:
- WP02
requirement_refs:
- FR-005
- FR-006
- NFR-004
planning_base_branch: issue-4785-charter-catalog-coherence
merge_target_branch: issue-4785-charter-catalog-coherence
branch_strategy: Planning artifacts for this mission were generated on issue-4785-charter-catalog-coherence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4785-charter-catalog-coherence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-catalog-coherence-01M2XQQF
base_commit: 0c479b4414f6db3db4e678678b3b26374c5f7366
created_at: '2026-09-19T22:55:48.985921+00:00'
subtasks:
- T017
- T018
- T019
- T020
phase: Phase 2 - Synthesis surface
history:
- at: '2026-09-19T21:23:09Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/charter/synthesize.py
- src/specify_cli/cli/commands/charter/_synthesis.py
- src/specify_cli/cli/commands/charter/generate.py
- src/specify_cli/cli/commands/charter/resynthesize.py
- tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Synthesize fresh-gate + worktree wiring

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Stop `synthesize` from misclassifying an established charter store as "fresh", and make the
remaining charter write commands worktree-safe (issue #4785, Findings 2-core & 3).

Done when:
- `charter synthesize` on an **established** store (compiled `charter.yaml` present) with no
  `.kittify/charter/generated/` directory does NOT report "fresh project" and does NOT short-circuit
  to a minimal-doctrine seed — the fresh-project predicate keys on actual catalog emptiness, not
  `generated/` absence (FR-005).
- `generate`, `synthesize`, and `resynthesize` fail closed from a linked worktree via the WP02 helper
  (FR-006).

## Context & Constraints

- **Depends on WP02** (worktree helper). Import the resolver; do not reimplement detection.
- Root-cause map: fresh-project predicate at `synthesize.py:222-228`
  (`adapter=="generated" AND not _has_generated_artifacts(repo_root) AND charter_yaml.is_file()`);
  `_has_generated_artifacts` at `_synthesis.py:568-584`; root resolution via `find_repo_root()` at
  `generate.py:296`, `synthesize.py:199`, `resynthesize.py:98`; the local duplicate
  `_is_inside_git_worktree` at `generate.py:48-67` (retire it in favor of the WP02 helper).
- **Note**: `synthesize` still does not (and by design need not) recompile `catalog.references` —
  that is `generate`/`compile_charter`'s job. This WP only stops the *misclassification*; the
  recompile coherence comes from WP01+WP03. Do not make `synthesize` a catalog writer.
- Do NOT modify `find_repo_root`/`get_main_repo_root` (C-002).

## Branch Strategy

- **Strategy**: rebase-merge to `main` via non-draft PR (operator merges)
- **Planning base branch**: `issue-4785-charter-catalog-coherence`
- **Merge target branch**: `main`
- Implement command: `spec-kitty agent action implement WP04 --agent claude` (after WP02 lands in the lane base)

## Subtasks & Detailed Guidance

### Subtask T017 – Red-first repro (RED before fix)
- **Steps**: In `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py`, add
  `@pytest.mark.regression` (#4785): on a store with `charter.yaml` present but no `generated/`,
  `synthesize` must NOT take the fresh-project branch. Add a worktree case: `generate` (or
  `synthesize`) from a linked worktree fails closed. RED today.
- **Files**: test file (new).

### Subtask T018 – Gate the fresh-project predicate on catalog emptiness
- **Steps**: Change the predicate so an established store (compiled `catalog`/`catalog.references`
  present, or non-empty `activated_*`) is NOT classified fresh. Prefer a positive
  "no compiled catalog yet" signal over `generated/` absence. Keep genuine fresh-project bootstrap
  working (no compiled catalog → still seeds).
- **Files**: `synthesize.py`, `_synthesis.py`.

### Subtask T019 – Worktree guard across generate/synthesize/resynthesize
- **Steps**: At each charter-write root-resolution site (`generate.py:296`, `synthesize.py:199`,
  `resynthesize.py:98`), **add** a call to the WP02 fail-closed resolver so these commands refuse a
  linked worktree.
- **⚠️ DO NOT delete/retire `_is_inside_git_worktree`** (`generate.py:48-68`). It is imported by
  **unowned** siblings — `pack.py:194` and `_resynthesis_preflight.py:22` (+ re-exports in
  `__init__.py`) — and is semantically a *permissive* "is there any working tree?" check (returns
  True inside a linked worktree), NOT the fail-closed guard. Deleting it breaks unowned code;
  repointing it to the WP02 guard would silently change `pack`/`preflight` behavior (out of scope).
  Keep `_is_inside_git_worktree` as-is and add the WP02 guard as a **separate** call at the write
  sites. If the reviewer wants it truly unified, that is a follow-up touching the unowned importers —
  surface it, do not silently do it.
- **Files**: `generate.py`, `synthesize.py`, `resynthesize.py`.

### Subtask T020 – Turn repro green + reconcile synthesize/resynthesize tests
- **Steps**: Make T017 GREEN. Reconcile existing `test_charter_resynthesize*` / synthesize tests to
  the new fresh-gate + worktree behavior (out-of-map edits with a one-line rationale each).
- **Files**: test file; existing synthesize/resynthesize tests (out-of-map, rationale).

## Test Strategy

- `PYTHONPATH=src python -m pytest tests/specify_cli/cli/commands/charter -q`
- Record RED-before / GREEN-after in the Activity Log.

## Risks & Mitigations

- **Don't over-narrow "fresh"**: a genuinely fresh project (no compiled catalog) must still seed.
  Test both an established store (no short-circuit) and a truly-fresh store (still seeds).
- **Shared helper coupling**: WP02 must land first; import its resolver rather than duplicating.

## Review Guidance

- Verify the predicate keys on catalog emptiness, not `generated/` absence.
- Verify `synthesize` was NOT turned into a catalog writer.
- Verify all three commands call the WP02 fail-closed resolver, and that `_is_inside_git_worktree`
  was NOT deleted or repointed (its unowned importers `pack.py`/`_resynthesis_preflight.py` must keep
  their permissive semantics).

## Activity Log

- 2026-09-19T21:23:09Z – system – Prompt created.
