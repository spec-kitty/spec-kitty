---
work_package_id: WP01
title: migrate preserves customised assets (#4961)
dependencies: []
requirement_refs:
- FR-001
- FR-002
planning_base_branch: spec/asset-preservation-migrate-fetch
merge_target_branch: spec/asset-preservation-migrate-fetch
branch_strategy: Planning artifacts for this mission were generated on spec/asset-preservation-migrate-fetch. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into spec/asset-preservation-migrate-fetch unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-asset-preservation-migrate-fetch-01M3E857
base_commit: e53732542b3d2cf4c73c1323bac3ded3a63eca76
created_at: '2026-09-26T07:25:47.483793+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Product fixes
history:
- at: '2026-09-26T07:18:36Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/runtime/migrate.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/runtime/migrate.py
- tests/upgrade/test_migrate_integration.py
- tests/runtime/test_e2e_runtime_integration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – migrate preserves customised assets (#4961)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter and behave per its
guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Fix #4961: `spec-kitty migrate --force` must never delete a `.kittify/` asset that differs from its
package default (a team customisation OR an outdated default), and `migrate --dry-run` must label such a
file honestly. Only a file **byte-identical** to its shipped counterpart may be removed.

Done when:
- A customised shipped template survives `execute_migration(dry_run=False)` (bytes recoverable in place),
  exit 0, and a later `mission create` still renders the team section. (SC-002)
- A byte-identical shipped default is STILL removed (no NFR-004 regression).
- `--dry-run` labels a differing customised file as customised/preserved, never "superseded".
- No raw `path.unlink()` remains in `execute_migration`'s removal path (it routes through the guard).
- All re-pinned tests pass; the red-first regression is RED before the fix and GREEN after.

## Context & Constraints

- Authority: `../research.md` F1 & F5, `../contracts/preservation-contract.md` Site A, `../plan.md`.
- **Root cause (F1)**: `classify_asset` (`src/specify_cli/runtime/migrate.py:69`) returns `SUPERSEDED`
  (:112) when a package counterpart exists and differs; `execute_migration` (:145) then `path.unlink()`s
  SUPERSEDED files at :189-195 with no backup and no way for a differing shipped-template copy to be
  treated as customised.
- **Corrected design (F5) — do NOT use the naive prover**: route BOTH the IDENTICAL and SUPERSEDED
  removal through
  `guard_destructive_removal(path, project_dir, prover=CanonicalContentProver(canonical=<package-counterpart bytes>), backup_parent=None, dry_run=dry_run)`
  (`src/specify_cli/asset_preservation/guard.py:148`, `provers.py:174`).
  - Byte-identical to the counterpart → `canonical_content` proof → removed (NFR-004 preserved).
  - Differs (customised OR outdated default) → unproven → **preserved in place** (`backup_parent=None`),
    reported via the verdict diagnostic.
  - Do NOT use `CanonicalContentProver()` with the default marker (it would delete a customised
    marker-bearing command file) and do NOT use `ManifestProver` (inert for `.kittify/templates`).
- The counterpart bytes must be threaded into the removal site: `classify_asset` computes the counterpart
  internally (`_find_package_counterpart`, migrate.py:50-66) but returns only the enum. Re-derive it at the
  removal site, or extend `classify_asset` to return it.
- Mirror the CLOSED sibling init fix (#4931/#4861) at `src/specify_cli/cli/commands/init.py:1604`.
- Reuse only; do not open-code backups (NFR-003). No CLI version bump (C-002).

## Branch Strategy

- **Strategy**: pr-bound feature branch
- **Planning base branch**: `spec/asset-preservation-migrate-fetch`
- **Merge target branch**: `spec/asset-preservation-migrate-fetch`

> Execution worktree is allocated per computed lane from `lanes.json`. Work only inside your lane worktree.
> Use `.venv/bin/python`, never bare `uv run`. Prefix test runs with `PWHEADLESS=1`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first regression: customised template survives
- **Purpose**: Prove the bug and lock the fix.
- **Steps**: In `tests/upgrade/test_migrate_integration.py`, add a `@pytest.mark.regression` test: set up a
  `.kittify/templates/spec-template.md` = package bytes + an appended team section; run `execute_migration`
  with `dry_run=False`; assert the file still exists with the team section (or is recoverable from a
  reported backup path), the command reported preservation (not "removed"), and exit is success. It must be
  RED on the current code (file gets unlinked) and GREEN after T002-T003.
- **Files**: `tests/upgrade/test_migrate_integration.py`
- **Notes**: cite `#4961` in the test docstring.

### Subtask T002 – Thread package-counterpart bytes into the removal site
- **Purpose**: The guard's canonical prover needs the shipped-counterpart bytes.
- **Steps**: At the removal site in `execute_migration`, obtain the package counterpart for the asset via
  `_find_package_counterpart(rel, package_root, mission)` (migrate.py:50-66) — or extend `classify_asset` to
  return `(disposition, counterpart_path)` and use it. Read the counterpart bytes for the prover.
- **Files**: `src/specify_cli/runtime/migrate.py`

### Subtask T003 – Route removal through the guard (drop raw unlink)
- **Purpose**: The actual fix.
- **Steps**: Replace the raw `path.unlink()` (migrate.py:~195) for BOTH IDENTICAL and SUPERSEDED with
  `guard_destructive_removal(path, project_dir, prover=CanonicalContentProver(canonical=<counterpart bytes>), backup_parent=None, dry_run=dry_run)`.
  Surface the returned `OwnershipVerdict.diagnostic` in the migration report. Ensure the IDENTICAL path
  still removes (proven) and the differing path preserves (unproven).
- **Files**: `src/specify_cli/runtime/migrate.py`
- **Notes**: keep the `overrides/` move path for genuinely user-created (no-counterpart) files unchanged.

### Subtask T004 – Honest classification/report for `--dry-run`
- **Purpose**: NFR-002 honest messaging.
- **Steps**: Ensure the report/`--dry-run` labels a differing customised file as customised/preserved, not
  "superseded (outdated defaults) -- removed". Keep `classify_asset` semantics honest for reporting even if
  the guard is the sole removal authority.
- **Files**: `src/specify_cli/runtime/migrate.py`

### Subtask T005 – Re-pin the deletion tests in test_migrate_integration.py
- **Purpose**: Tests currently enshrine the deletion; re-pin to the corrected contract (do NOT weaken).
- **Steps**: Update `test_superseded_when_differs_from_package` (:824-838), `test_outdated_agents_md_superseded`
  (:686), `test_mix_of_identical_customized_and_superseded` (:709), `test_superseded_files_removed_not_moved_to_overrides`
  (:891), `test_version_skew_scenario_end_to_end` (:957 — redefine removed→preserved/archived per #285
  trade-off), `test_superseded_count_in_report` (:1005), and the in-file IDENTICAL-removal pins. Assert
  preservation for differing files; keep IDENTICAL removal asserted.
- **Files**: `tests/upgrade/test_migrate_integration.py`

### Subtask T006 – Re-pin e2e runtime pins + run convergence unit
- **Purpose**: F9 — a second file pins both dispositions and is easy to miss.
- **Steps**: Update the SUPERSEDED (`:299-321`,`:487`,`:503-506`) and IDENTICAL (`:385-389`,`:481-505`,`:530-537`)
  pins in `tests/runtime/test_e2e_runtime_integration.py` to the corrected contract. Run
  `tests/runtime/test_global_runtime_convergence_unit.py` (idempotency); if it asserts deletion, re-pin it too
  (record a one-line out-of-map rationale in the Activity Log if you must touch it — it is not in owned_files).
- **Files**: `tests/runtime/test_e2e_runtime_integration.py`

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest tests/upgrade/test_migrate_integration.py -q -p no:xdist`
- `PWHEADLESS=1 .venv/bin/python -m pytest tests/runtime/test_e2e_runtime_integration.py tests/runtime/test_global_runtime_convergence_unit.py -q -p no:xdist`
- New code must pass `ruff check` and `mypy` with zero issues (no new `# noqa`/`# type: ignore`).

## Risks & Mitigations

- **NFR-004 regression** (identical default no longer removed): mitigated by the byte-match canonical
  prover — verify an IDENTICAL default is still removed in tests.
- **Marker false-positive** (deleting a customised marker-bearing file): avoided by byte-match (not marker) proof.
- **Baseline-red gotcha**: classify any unrelated red per CLAUDE.md before attributing it here.

## Review Guidance

- Confirm no raw `unlink` remains in the removal path; the guard is the sole removal authority.
- MUTATION TEST: restore `path.unlink()` (or swap the prover to the default marker prover) → a test MUST go
  RED. If it stays green, the fix is unprotected → reject.
- Confirm IDENTICAL removal preserved and differing files preserved; `--dry-run` labels honest.
- Issue-matrix: #4961 → WP01.

## Activity Log

- 2026-09-26T07:18:36Z – system – Prompt created.
