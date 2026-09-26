---
work_package_id: WP03
title: close the destructive-op class in the arch gate + document (FR-005)
dependencies:
- WP01
- WP02
requirement_refs:
- FR-005
planning_base_branch: spec/asset-preservation-migrate-fetch
merge_target_branch: spec/asset-preservation-migrate-fetch
branch_strategy: Planning artifacts for this mission were generated on spec/asset-preservation-migrate-fetch. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into spec/asset-preservation-migrate-fetch unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-asset-preservation-migrate-fetch-01M3E857
base_commit: 73a88bfc7e52da1e9bcd2b9f7bca10514d3e04bb
created_at: '2026-09-26T08:06:18.162994+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Guard the class
history:
- at: '2026-09-26T07:18:36Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_destructive_op_routing.py
- tests/architectural/test_mutation_ownership_routing.py
- tests/architectural/_destructive_op_census.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – close the destructive-op class in the arch gate + document (FR-005)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the frontmatter profile and behave per its guidance first.

- **Profile**: `reviewer-renata`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Close the destructive-op class by construction (FR-005): make the architectural gate scan the two
now-fixed product modules so any future un-rationalised raw destructive literal fails CI, and document the
fix in the CHANGELOG (no version bump).

Done when:
- `tests/architectural/test_mutation_ownership_routing.py` scans `runtime/migrate.py` and
  `doctrine/sources/git_source.py`; the gate is GREEN over the combined WP01+WP02 tip.
- `migrate.py` is in `_ROUTED_MODULES`; `git_source.py` is scanned-but-not-routed with a never-allowlist guard.
- The git-argv reset allowlist entry is re-pinned to the fixed line with a truthful rationale.
- The gate is proven fail-able (adding a raw literal reds it).
- CHANGELOG has an entry for #4961/#4960/#4989; no CLI version bump.

## Context & Constraints

- **DEPENDS ON WP01 AND WP02** — the gate can only pass once both fixes exist. Start only after both are approved.
- Authority: `../research.md` F4, F9; `../contracts/preservation-contract.md` Site C; `../plan.md`.
- **Two gates (F9)**:
  - git-argv gate `tests/architectural/test_destructive_op_routing.py` already scans all of `src/specify_cli`.
    The ONLY change: re-pin/trim the allowlist entry `src/specify_cli/doctrine/sources/git_source.py:98:reset_hard`
    (`:160-164`) to the fixed line and fix its now-false "throwaway doctrine-pack clone" rationale.
  - FS-op gate `tests/architectural/test_mutation_ownership_routing.py` (+ `_destructive_op_census.py`) scans a
    fixed `_module_set()` (`:106-107`).
- **`_ROUTED_MODULES` (F9)**: adding `migrate.py` (which routes through `guard_destructive_removal`) requires
  adding it to `_ROUTED_MODULES` (`:449`) or `test_pinned_routed_module_set_is_complete` (`:616`) fails.
  `git_source.py` uses backup/temp-swap (NOT the removal guard) → scanned but NOT routed; mirror the
  `research.py` never-allowlist guard (`test_research_py_removal_literals_are_never_allowlisted`, `:526-545`).
- **Allowlist entries (F9)**: `migrate.py:239` empty-only `Path.rmdir` (guarded by `iterdir()`); the
  `git_source.py` temp-clone `shutil.rmtree` cleanup (ephemeral-temp rationale); a `shutil.move` swap if WP02
  used one. Note `Path.rename`/`os.replace` are NOT caught by the FS classifier (#4901) — do not add entries for them.
- No new `# noqa`/`# type: ignore`. No CLI version bump (C-002).

## Branch Strategy

- **Strategy**: pr-bound feature branch
- **Planning base branch**: `spec/asset-preservation-migrate-fetch`
- **Merge target branch**: `spec/asset-preservation-migrate-fetch`

> Work only inside your lane worktree. `.venv/bin/python`, never bare `uv run`. Prefix `PWHEADLESS=1`.

## Subtasks & Detailed Guidance

### Subtask T011 – Extend the FS-op scanned module set
- **Steps**: Add `src/specify_cli/runtime/migrate.py` and `src/specify_cli/doctrine/sources/git_source.py`
  to `_module_set()` in `tests/architectural/test_mutation_ownership_routing.py` (and any mirror in
  `_destructive_op_census.py`).
- **Files**: `tests/architectural/test_mutation_ownership_routing.py`, `tests/architectural/_destructive_op_census.py`

### Subtask T012 – Routed vs scanned classification
- **Steps**: Add `migrate.py` to `_ROUTED_MODULES` (`:449`). Keep `git_source.py` scanned-but-not-routed;
  add/extend a never-allowlist guard mirroring `test_research_py_removal_literals_are_never_allowlisted`
  (`:526-545`) so a user-content removal literal in `git_source.py` can never be allowlisted.
- **Files**: `tests/architectural/test_mutation_ownership_routing.py`

### Subtask T013 – Allowlist the guarded literals + re-pin the reset entry
- **Steps**: Add allowlist entries for `migrate.py:239` empty-only `rmdir` and the `git_source.py` temp
  `shutil.rmtree` (+ `shutil.move` swap if present) with truthful rationales. In
  `test_destructive_op_routing.py`, re-pin the `git_source.py:<line>:reset_hard` allowlist entry to the fixed
  line and replace the false "throwaway clone" rationale with the guarded-reset rationale (or remove the entry
  if WP02 removed the reset entirely).
- **Files**: `tests/architectural/test_mutation_ownership_routing.py`, `tests/architectural/test_destructive_op_routing.py`

### Subtask T014 – Prove the gate fail-able
- **Steps**: In a scratch copy (not committed), add an un-rationalised raw destructive literal to each scanned
  module and confirm the gate reds; revert. Document the check in the Activity Log / PR. If a self-mutation test
  helper exists, extend it; otherwise verify manually and note the evidence.
- **Files**: `tests/architectural/test_mutation_ownership_routing.py`

### Subtask T015 – CHANGELOG entry (no version bump)
- **Steps**: Add a `docs/changelog/CHANGELOG.md` entry documenting #4961/#4960/#4989 under the existing
  unreleased/preservation section, matching the #4915 entry style (before/after). Do NOT bump the version.
- **Files**: `docs/changelog/CHANGELOG.md`

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_destructive_op_routing.py tests/architectural/test_mutation_ownership_routing.py -q -p no:xdist`
- Run over the combined WP01+WP02 tip (both fixes present) — the gate must be GREEN.

## Risks & Mitigations

- **Line-pin drift (F4)**: the `git_source.py:98:reset_hard` entry is line-pinned — WP02's edits shift it;
  re-pin to the exact fixed line.
- **`_ROUTED_MODULES` completeness test** fails if `migrate.py` scanned-but-not-listed — add it.
- **Running before WP01/WP02** would red the gate — this WP depends on both; do not start early.

## Review Guidance

- Confirm the gate is GREEN over the combined tip AND proven fail-able.
- Confirm `git_source.py` is scanned-not-routed with a never-allowlist guard (research.py parity).
- Confirm no version bump; CHANGELOG entry present and accurate.
- Issue-matrix: FR-005 has no dedicated issue; #4961/#4960/#4989 already mapped to WP01/WP02.

## Activity Log

- 2026-09-26T07:18:36Z – system – Prompt created.
