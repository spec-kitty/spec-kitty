---
work_package_id: WP01
title: Pin the post-fold convergence of the interview promotion (#6549)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6549-promote-answers-post-fold-convergence
merge_target_branch: issue-6549-promote-answers-post-fold-convergence
branch_strategy: Planning artifacts for this mission were generated on issue-6549-promote-answers-post-fold-convergence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6549-promote-answers-post-fold-convergence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-promote-answers-post-fold-convergence-01M68JDG
base_commit: 7cba80465d0a32f976704f7726e783a75a353172
created_at: '2026-10-31T08:52:49.050708+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Guard
history:
- at: '2026-10-31T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/upgrade/
create_intent:
- tests/upgrade/test_promote_answers_post_fold_convergence_6549.py
- docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
execution_mode: code_change
model: ''
owned_files:
- tests/upgrade/test_promote_answers_post_fold_convergence_6549.py
- docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
---

# WP01: Pin the post-fold convergence of the interview promotion (#6549)

See `tasks.md` for the subtask list, `spec.md` for requirements and `plan.md` (`## Design`)
for the fixture/assertion design that grounding validated.

## Context

#6549 is already fixed on `main` by #6629: `unify_charter_activation_promote_answers` is
a recorded no-op through `SUPERSEDED_MIGRATIONS`, and `4.0.0rc8_promote_interview_selections`
writes through the resolved activation write target. Nothing pins the promote step's
post-fold behaviour or the two-run convergence of the project shape that regressed —
`tests/upgrade/test_activate_builtin_post_fold_dedup.py` covers the rc35 pair only.

## Do

1. **Fixture (T001)** — `_fold_crossing_project(tmp_path)`: real `git init`, commit a root;
   `save_agent_config`; `ProjectMetadata(version="3.2.0rc30")` (below the fold and the
   promotion's `3.2.6rc1`, so both are selected and adoption does not settle them);
   `answers.yaml` with `selected_directives: [DIRECTIVE_001]`; `config.yaml` carrying
   `activated_directives: [001-architectural-integrity-standard]`. Then a snapshot helper
   covering every file under the project except `.git/`, plus `git rev-list --count HEAD`.
2. **Two-run convergence (T002)** — drive the production CLI `upgrade` app
   (`typer.Typer` + `specify_cli.cli.commands.upgrade.upgrade`, `CliRunner`,
   `contextlib.chdir`), exactly as `tests/upgrade/test_init_ledger_seed_idempotency.py`
   does. Run once, snapshot, run again, assert every byte identical, commit count
   unchanged, and no `activated_*` key in `.kittify/config.yaml`.
3. **Post-fold seam (T003)** — run the real fold (`ConsolidateCharterBundleMigration().apply`)
   on the fixture, then assert the **registered** class for the id is a
   `SupersededMigration` with `detect() is False` and `apply()` leaves bytes identical;
   and, on the same fixture, the **shipped** class's own `detect()` is still True (the
   positive control that makes the False meaningful).
4. **Bite proof (T004)** — remove the id from
   `specify_cli.upgrade.supersession.SUPERSEDED_MIGRATIONS`, `MigrationRegistry.clear()`
   + `auto_discover_migrations()` (the production discovery path, so the substitution
   branch is real), run the same two-run fixture, and assert `.kittify/config.yaml`
   gains `activated_directives` listing every available built-in directive stem — the
   #6549 symptom on the same fixture. Restore the table and the registry in `finally`.
5. **ADR cross-reference (T005)** — one sentence in Amendment 2026-10-25 of
   `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` naming the new module.
6. **Evidence (T006)** — run the new module and `tests/upgrade/test_activate_builtin_post_fold_dedup.py`,
   `tests/upgrade/test_upgrade_keeps_absent_activation_6629.py`,
   `tests/specify_cli/upgrade/test_unify_charter_activation_migration.py`; paste the counts
   into the PR's `## Tests run`.

## Don't

- Do not edit anything under `src/` (NFR-002) or the shipped migration module (C-001).
- Do not skip/xfail/deselect a test or touch a CI gate (NFR-003).
- Do not strip a divergent `config.yaml` activation copy from a project that already
  took the pre-#6629 second pass: the runtime ignores it, `doctor charter-packs` reports
  it, and removing it is a maintainer decision (C-003; see the PR's `## Deferred`).
