---
work_package_id: WP03
title: Activate/deactivate coherent-by-construction + remediation
dependencies:
- WP01
- WP02
requirement_refs:
- C-006
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- NFR-001
- NFR-004
planning_base_branch: issue-4785-charter-catalog-coherence
merge_target_branch: issue-4785-charter-catalog-coherence
branch_strategy: Planning artifacts for this mission were generated on issue-4785-charter-catalog-coherence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4785-charter-catalog-coherence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-catalog-coherence-01M2XQQF
base_commit: 22cb0068218b4747129faa3fff737271e530e2a3
created_at: '2026-09-19T22:53:44.769206+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
phase: Phase 2 - Activation surface
history:
- at: '2026-09-19T21:23:09Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_activate_recompile_4785.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/charter/activate.py
- src/specify_cli/cli/commands/charter/deactivate.py
- src/charter/activation/consistency_check.py
- tests/specify_cli/cli/commands/charter/test_activate_recompile_4785.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Activate/deactivate coherent-by-construction + remediation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Make `charter activate`/`deactivate` keep the compiled catalog coherent by default, and stop the
tooling from steering operators at a command that cannot recompile (issue #4785, Findings 1 & 2).

Done when:
- `charter activate <built-in directive>` recompiles `catalog.references` by **default** via
  `compile_charter(..., from_interview=False)` (the `charter pack apply --compile` pattern), leaving
  `tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent`
  GREEN with no manual edit (FR-001).
- `charter deactivate <directive>` symmetrically recompiles and stays coherent (FR-002).
- A `--no-compile` opt-out preserves the fast config-only write and prints an explicit notice that
  the catalog was not recompiled (FR-003).
- The coherence-guard suggestion string (`consistency_check`) and `RESYNTHESIZE_HELP` name
  `charter generate` (or `activate --resynthesize`) — **never** `charter synthesize` (FR-004).
- `activate`/`deactivate` fail closed from a linked worktree via the WP02 helper; the
  `run_full_synthesize` `chdir` split-brain (activation flag in worktree, recompile in primary) is
  eliminated (FR-006).

## Context & Constraints

- **Depends on WP01** (complete + deterministic recompile) and **WP02** (worktree helper). Import
  the WP02 resolver; do not reimplement worktree detection.
- Route through the single compiler authority (`compile_charter`/`write_compiled_charter`); do NOT
  add a minimal writer (C-001/C-004).
- Recompile source is `from_interview=False` — no `CharterInterview`/`answers.yaml` (research N1).
- Root-cause map: `activate_cmd` config-only write at `activate.py:629-640`; recompile only under
  `--resynthesize` at `:666-667`; `RESYNTHESIZE_HELP` at `:67-73`; `run_full_synthesize` +
  `contextlib.chdir` at `:478-541,523` (preserve the load-bearing `prune=False` #3270 sentinel);
  coherence suggestion string in `consistency_check.py` (`_check_reference_id_parity`).
- **C-006 (reconcile, don't green-wash)**: pre-existing tests that assert config-only activation must
  be deliberately reconciled to the new default, enumerated with rationale — do not silently edit to
  green. Likely: `test_charter_activate_cli`, `test_activate_preserve`, `test_resynthesize_and_hotpath`,
  `test_activation_parity_guard`. Edit these out-of-map with a one-line rationale each.

## Branch Strategy

- **Strategy**: rebase-merge to `main` via non-draft PR (operator merges)
- **Planning base branch**: `issue-4785-charter-catalog-coherence`
- **Merge target branch**: `main`
- Implement command: `spec-kitty agent action implement WP03 --agent claude` (after WP01 + WP02 land in the lane base)

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first repro (RED before fix)
- **Steps**: In `tests/specify_cli/cli/commands/charter/test_activate_recompile_4785.py`, add
  `@pytest.mark.regression` (#4785): activating a built-in directive absent from the baseline catalog
  leaves the coherence guard GREEN (RED today because activate is config-only). Include a
  `--no-compile` case asserting the config-only path + notice.
- **Files**: test file (new).

### Subtask T012 – Recompile-by-default in `activate`
- **Steps**: After `manager.activate()` (`:629`) + `commit_project_registration()` (`:640`), recompile
  the catalog via the single authority. **Model exactly on `pack.py:208-224` `_compile_bundle_after_merge`**:
  `_load_interview_for_generate(repo_root=…, answers_path=_interview_path(repo_root), from_interview=False, …)`
  → `compile_charter(mission=…, interview=…, repo_root=<WP02-resolved>, doctrine_service=_build_doctrine_service_with_org_layer(repo_root), pack_context=PackContext.from_config(repo_root))`
  → `write_compiled_charter(charter_dir, compiled, repo_root=repo_root)`.
  **NOTE**: `from_interview` is a param of `_load_interview_for_generate`, NOT of `compile_charter`
  (which has no such param). Add a `--no-compile` flag (default: compile) that skips the recompile and
  prints an explicit deferral notice.
- **Files**: `activate.py`.

### Subtask T013 – Symmetric recompile in `deactivate`
- **Steps**: Apply the same recompile tail (+ `--no-compile`) to `deactivate`.
- **Files**: `deactivate.py`.

### Subtask T014 – Worktree guard + kill the split-brain
- **Steps**: Wire the WP02 resolver into `activate`/`deactivate` so both fail closed from a linked
  worktree. Replace the `run_full_synthesize` `contextlib.chdir(repo_root)` hack so the activation
  flag and the recompile always target the SAME (WP02-resolved) checkout. Preserve `prune=False`.
- **Files**: `activate.py`, `deactivate.py`.

### Subtask T015 – Correct remediation guidance
- **Steps**: Two strings in `consistency_check.py` recommend `spec-kitty charter synthesize` and must
  name `charter generate` (or `activate --resynthesize`): `:710-715` (in `_check_reference_id_parity`,
  corrupt-charter branch) and `:774-779` (in `_check_reference_id_forward_parity` — **this is the one
  the divergence guard emits**). Also reword `RESYNTHESIZE_HELP` (`activate.py:67-73`) to name
  `generate` as the recompiler. Before editing, grep `tests/` for `charter synthesize' (or resynthesize)`
  and update any verbatim assertion.
- **Files**: `consistency_check.py`, `activate.py`.

### Subtask T016 – Turn repro green + reconcile existing tests (C-006)
- **Steps**: Make T011 GREEN. Reconcile the pre-existing config-only-activation tests to the new
  default with a one-line rationale each: primary home is `tests/specify_cli/test_charter_activate_cli.py`
  (note `:144` asserts `activate_mod.__all__ == ["activate_cmd", "run_full_synthesize"]` — keep both
  symbols in `__all__` or update that line); also check `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py`
  and `tests/cli/test_charter_activate_warning.py`. Run the activate/consistency test surface.
- **Files**: test file; enumerated existing tests (out-of-map, rationale).

## Test Strategy

- `PYTHONPATH=src python -m pytest tests/specify_cli/cli/commands/charter tests/doctrine/test_activation_parity_guard.py tests/charter/test_consistency_check.py -q`
- Record RED-before / GREEN-after in the Activity Log.

## Risks & Mitigations

- **Performance (NFR-001)**: measure the added recompile time on activate; record it. If it exceeds
  the < 2 s target, surface as a risk (do not silently accept).
- **`#2627` global-cache race**: the compiler path does not call `ensure_global_agent_commands`, so
  the race is not on this hot path — but note it if it appears in a run (self-heals on retry).
- **C-006 green-washing**: never edit an existing assertion to green without a rationale proving the
  new behavior is correct.

## Review Guidance

- Verify recompile routes through the single authority with `from_interview=False`.
- Verify `--no-compile` is a genuine opt-out with a clear notice.
- Verify no remediation surface names `synthesize`.
- Verify the split-brain is gone (activation + recompile in one checkout).

## Activity Log

- 2026-09-19T21:23:09Z – system – Prompt created.
