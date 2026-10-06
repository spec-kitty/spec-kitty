---
work_package_id: WP02
title: A failed upgrade restores the recorded version
dependencies:
- WP01
requirement_refs:
- FR-003
- C-004
- SC-002
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: ccr-11788f1f-qu75jg
merge_target_branch: ccr-11788f1f-qu75jg
branch_strategy: Planning artifacts for this mission were generated on ccr-11788f1f-qu75jg. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-11788f1f-qu75jg unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surface-upgrade-integrity-01M482Z3
base_commit: d70354e229b02f5e7f581efba9473908e04e972d
created_at: '2026-10-06T09:02:00.572024+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Upgrade surface planning
history:
- at: '2026-10-06T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/upgrade.py
create_intent:
- tests/upgrade/test_upgrade_version_restore_4275.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/upgrade.py
- src/specify_cli/upgrade/runner.py
- tests/upgrade/test_failed_upgrade_recoverable.py
- tests/upgrade/test_upgrade_version_restore_4275.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – A failed upgrade restores the recorded version

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log. Address every feedback item before completing.

---

## Objectives & Success Criteria

- FR-003: when the upgrade fails — in a migration, in the runner's metadata finalisation, or in the CLI's final surface repair (`finalize_upgrade`) — `.kittify/metadata.yaml` `version`, `last_upgraded_at` and schema version equal their pre-run values (#4275 second finding).
- SC-002: the regression test forces a failure in the **final surface repair**, not only a migration (migration failure is already covered by #3334 tests in `tests/upgrade/test_failed_upgrade_recoverable.py`).
- C-004: the #1158 schema-stamp repair on an already-current project still works.
- A successful upgrade's stamping is unchanged.

## Context & Constraints

- Spec FR-003, C-004; plan IC-02; research R-2 (snapshot-and-restore chosen over deferring four writers).
- Writers of the version trio (verify each, line numbers drift):
  - `src/specify_cli/upgrade/runner.py:~180-184` (no-migrations path)
  - `runner.py` `_finalize_main_metadata` `~737-742` and schema stamp `_stamp_schema_version` `~755+`
  - `src/specify_cli/cli/commands/upgrade.py` `_stamp_no_migrations_metadata` `~711-728` (called `~778`)
  - runner call `~1855`; `_prepare_finalizer_repairs` `~1033-1043` called `~1880`; `finalize_upgrade` `~1884-1911`.
- Existing #3334 restore: capture at `upgrade/runner.py:~215`, restore-on-failure in `_finalize_main_metadata` `runner.py:~738`, helpers in `upgrade/metadata.py:31,68,193`. EXTEND it (single authority). The snapshot must also be taken in `upgrade.py` before the runner, because the runner stamps success before `finalize_upgrade` (`upgrade.py:~1884`) can fail.
- Dependency on WP01 is deliberate: T006 runs the real upgrade on a kittified temp project, which hits #4275 until WP01 is green.
- Do NOT restore the applied-migrations list (`record_migration`); only the version trio.
- Depends on WP01: rebase onto WP01's lane tip; both touch the upgrade flow.

## Branch Strategy

- **Planning base branch**: `ccr-11788f1f-qu75jg` · **Merge target branch**: `ccr-11788f1f-qu75jg`. Worktree from `lanes.json`; `spec-kitty agent action implement WP02 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first repro

- Create `tests/upgrade/test_upgrade_version_restore_4275.py`, `@pytest.mark.regression`.
- Kittify a temp project stamped at an older version (reuse fixtures from `test_failed_upgrade_recoverable.py`). Monkeypatch the final surface repair (`finalize_upgrade`'s repair application, or `_prepare_finalizer_repairs`) to raise. Run the project upgrade.
- Assert non-zero exit and `metadata.yaml` `version`/`last_upgraded_at` equal pre-run values. Add a second case on the no-migration path (current == target except schema needs nothing): failure leaves the file byte-identical.
- Record RED on planning base in the Activity Log; commit test alone first.

### Subtask T007 – Snapshot

- Add a small helper (in `upgrade.py` or alongside the #3334 helper) capturing `{version, last_upgraded_at, schema_version}` (and whether the file existed) before the runner is invoked.

### Subtask T008 – Restore on failure

- Wrap runner + finalizer in one boundary: on any exception or non-zero outcome, restore the snapshot (re-raise / exit with the original code). On success, discard.
- Keep `upgrade()` complexity ≤15: put the boundary in a helper/context manager with focused tests.

### Subtask T009 – Keep #1158 and no-migration path

- Run `tests/upgrade/test_schema_version_recovery.py`, `test_metadata_schema_roundtrip.py`, `test_recovery_composition.py`, `test_worktree_stamp_guard.py` — all green.
- Convert T006 to focused tests (drop `regression` marker) once green.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/upgrade/ -q
.venv/bin/python -m pytest tests/specify_cli/cli/commands/ -q -k upgrade
make test-fast
.venv/bin/ruff check src/specify_cli/upgrade src/specify_cli/cli/commands/upgrade.py
.venv/bin/mypy src/specify_cli/upgrade/runner.py src/specify_cli/cli/commands/upgrade.py
```

## Risks & Mitigations

- Double restore with the #3334 path → extend that helper, one boundary.
- Restoring after a partially applied surface repair leaves files but an older stamp — acceptable: next run re-drives repairs idempotently. Note it in the Activity Log.

## Review Guidance

- RED→GREEN evidence; a surface-repair failure (not just migration) is tested.
- No second restore authority; #1158 tests green.

## Activity Log

- 2026-10-06T08:10:00Z – system – Prompt created.
