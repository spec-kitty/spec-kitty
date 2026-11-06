---
work_package_id: WP10
title: S6 - lanes never change status; migrate existing lane worktrees; doctor probe
dependencies:
- WP05
- WP09
requirement_refs:
- FR-041
- FR-042
- FR-044
- FR-045
- SC-009
- NFR-002
- NFR-005
- NFR-008
- C-008
- C-009
- C-014
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-worktree-model-hardening-01M6QY1M
base_commit: a4e342649cfe4936e89b4da0e8599dffc658ace2
created_at: '2026-11-06T15:38:23.886901+00:00'
subtasks:
- T054
- T055
- T056
- T057
- T058
- T059
- T060
phase: Phase 3 - S2/S3/S6 lanes carry no live status
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc9_lane_checkout_status_exclusion.py
- tests/coordination/test_status_write_lane_refusal.py
- tests/specify_cli/cli/commands/agent/test_deliverable_autocommit_status_unstaged.py
- tests/specify_cli/upgrade/test_lane_checkout_status_exclusion_migration.py
- tests/specify_cli/cli/commands/test_lane_status_authored_probe.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/coordination/transaction.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc9_lane_checkout_status_exclusion.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- src/specify_cli/cli/commands/_sparse_checkout_doctor.py
- tests/coordination/test_status_write_lane_refusal.py
- tests/specify_cli/cli/commands/agent/test_deliverable_autocommit_status_unstaged.py
- tests/specify_cli/upgrade/test_lane_checkout_status_exclusion_migration.py
- tests/specify_cli/cli/commands/test_lane_status_authored_probe.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 - S6: lanes never change status; migrate existing lane worktrees; doctor probe

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP10 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP10 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

S6 (#7281), the write and migration half:

- FR-041: the status write seam refuses any write whose target is inside a registered lane checkout, classified by the worktree registry (not by `.worktrees/` path shape), code `STATUS_WRITE_TARGETS_LANE_CHECKOUT`. Positive control: the same write to the coordination worktree succeeds.
- FR-042: the deliverable auto-commit and every Spec Kitty-owned lane commit leave the Mission status files unstaged on every topology.
- FR-044: a re-runnable clone-local migration brings existing lane worktrees in line: clean -> `excluded`; dirty copy whose every event id is on the resolved surface -> `flagged_redundant` (excluded, file stays); dirty copy holding ids found nowhere else -> `refused_lane_only_events` (worktree untouched, ids reported); mid-merge/rebase/cherry-pick -> `skipped_mid_operation`; already done -> `already_excluded`. Never drops an event (C-009, NFR-002).
- FR-045: doctor finding `LANE_STATUS_AUTHORED` lists every live lane branch whose status files differ from `merge-base(lane, consolidation base)` (merged-in coordination bytes do not count).
- NFR-005 / SC-009: a second migration run changes 0 files, refs and sparse configurations; 0 events lost.

## Context & Constraints

- Read: spec User Story 5, FR-040 to FR-046, C-008, C-009, C-014, A-9; `research.md` R-4; `data-model.md` §4 (`LaneCheckoutMigrationItem`, doctor finding); `contracts/error-codes.yaml`; WP09's helper (sparse exclusion reuse); WP05's door (compare against the resolved surface).
- Migration ledger rules (CLAUDE.md "Migration Ledger Model", C-014): `clone_local_effect = True` (sparse config lives in the per-worktree git dir); idempotent `apply()`; an entry in `order_manifest.txt` in execution order (annotate `# tie: <reason>` if it shares a `target_version`); `requires_git_repository = True` if it resolves the canonical repo root; never edit a shipped migration. Migrations are auto-discovered (`upgrade/migrations/__init__.py::auto_discover_migrations`).
- **File name**: `m_4_0_0rc9_lane_checkout_status_exclusion.py` assumes the next release is `4.0.0rc9` (pyproject is `4.0.0rc8`). If the maintainers' next version differs, rename the file and its `migration_id`/`target_version` consistently and tell the orchestrator so `owned_files` can be updated.
- Shared files: `coordination/status_service.py` (owned by WP04) - your `_validate_write_contract` hunk is out-of-map (sequenced after WP04). `coordination/transaction.py` you own; WP07 has an out-of-map read hunk in `preflight_refusal` (different function).
- A-9: no git pre-commit hook. C-008: no lane-side deletion commit; `auto_rebase.py` untouched.
- C-011 red-first.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T054 - Red-first: write refusal and auto-commit

- `tests/coordination/test_status_write_lane_refusal.py`: `test_status_write_into_lane_checkout_refuses` (target resolves inside a registered lane checkout, including one NOT under `.worktrees/`) and `test_same_write_to_coord_worktree_succeeds`.
- `tests/specify_cli/cli/commands/agent/test_deliverable_autocommit_status_unstaged.py::test_deliverable_autocommit_never_stages_status_files`: a deliverable file and dirty status files in the lane; after `move-task`'s auto-commit, the commit contains the deliverable and not the status files (paired control, FR-042 ratchet).

### Subtask T055 - Red-first: migration and doctor

- `tests/specify_cli/upgrade/test_lane_checkout_status_exclusion_migration.py`: `test_migration_excludes_clean_lane_worktree`, `test_migration_flags_redundant_dirty_copy`, `test_migration_refuses_lane_only_event_ids_untouched` (report names the event ids; worktree bytes unchanged), `test_migration_skips_mid_rebase`, `test_migration_second_run_changes_nothing` (hash files, refs, sparse config before/after), `test_no_event_lost` (NFR-002: every pre-existing event id is on the surface or in the report).
- `tests/specify_cli/cli/commands/test_lane_status_authored_probe.py::test_doctor_probe_ignores_merged_in_coord_bytes` and `test_doctor_probe_reports_lane_authored_change`.

### Subtask T056 - Registry-classified write refusal

- `coordination/transaction.py::coordination_transaction_append` (`:~1025-1030`) requires a registry-classified coordination worktree; `status_service._validate_write_contract` (out-of-map) refuses a target inside a registered lane checkout with `STATUS_WRITE_TARGETS_LANE_CHECKOUT`. Use the #6884 registry classifier (WP04 helper); an unreadable registry fails closed.

### Subtask T057 - Lane commits leave status unstaged

- `tasks_move_task.py`: `_drop_lane_coord_residue` (`:~861`) and the deliverable auto-commit unstage `status.events.jsonl` / `status.json` on every topology (today coordination-only). Do not delete them from the index of the lane branch (C-008): use pathspec exclusion, not `git rm --cached`.

### Subtask T058 - Clone-local migration

- `m_4_0_0rc9_lane_checkout_status_exclusion.py`: enumerate lane worktrees from the registry for every Mission with code lanes; per worktree decide the outcome above by comparing its copy's event ids against the WP05 door's surface; apply the WP09 sparse exclusion where allowed; print the per-worktree report (it shows in `spec-kitty upgrade` and `migrate ledger`).
- `detect()` true when any lane worktree lacks the exclusion; `apply()` idempotent.
- Add the id to `order_manifest.txt` (end of list or with a `# tie:` note).

### Subtask T059 - Doctor probe [P]

- `_sparse_checkout_doctor.py`: finding `LANE_STATUS_AUTHORED {lane_branch, mission, paths, merge_base}`; compare `merge-base(lane, consolidation base)` vs lane tip for the two paths only.

### Subtask T060 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/coordination/test_status_write_lane_refusal.py tests/specify_cli/cli/commands/agent/test_deliverable_autocommit_status_unstaged.py tests/specify_cli/upgrade/test_lane_checkout_status_exclusion_migration.py tests/specify_cli/cli/commands/test_lane_status_authored_probe.py -q
uv run --frozen pytest tests/coordination tests/status tests/upgrade tests/integration/sparse_checkout -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/upgrade tests/specify_cli/cli/commands/test_sparse_checkout_doctor.py -q -n auto --dist loadfile      # out-of-matrix dirs: must run here
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -n auto --dist loadfile -k "move_task"                                    # out-of-matrix dir
uv run --frozen pytest tests/architectural/test_migration_order_manifest.py tests/specify_cli/upgrade/test_requires_git_repository_audit.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

Never `make test-full` or a bare `tests/architectural/` sweep.

**NFR-008 (Linux and Windows).** The S6 exclusion and the lane-checkout migration must pass on the Linux and Windows CI lanes: use git's own sparse/exclude commands and `pathlib` paths, never shell globs, POSIX-only path separators or `chmod`-style assumptions; the migration test must not depend on symlinks or case-sensitive paths. Run the migration test locally on Linux; mark nothing `skipif(os.name == "nt")` without a recorded reason. Reviewers check the Windows lane result on the PR (`ci-windows.yml`).

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP10] ...**`, naming the trace file); the orchestrator appends them. Record the chosen `target_version`.

## Risks & Mitigations

- Data loss: refuse rather than exclude whenever an id is lane-only (C-009).
- Harness env leaks (`SPEC_KITTY_*`) in upgrade tests: use `monkeypatch.delenv`.

## Review Guidance

- Registry, not path shape; unstaged on every topology; migration outcomes exactly the five; idempotent; manifest entry; doctor uses merge-base.

## Definition of Done

- T054-T060 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T054 T055 T056 T057 T058 T059 T060 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP10 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
