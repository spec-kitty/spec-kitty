---
work_package_id: WP02
title: Gates count only this Mission's dirt (#7556)
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-008
- NFR-001
planning_base_branch: fix/7545-cli-owns-its-commits
merge_target_branch: fix/7545-cli-owns-its-commits
branch_strategy: Planning artifacts for this mission were generated on fix/7545-cli-owns-its-commits. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7545-cli-owns-its-commits unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
phase: Phase 2 - Gates
history:
- at: '2026-11-11T16:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/mission_record_analysis.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_record_analysis_mission_scoped_7556.py
- docs/changelog/unreleased/7556-mission-scoped-dirty-gates.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/mission_record_analysis.py
- src/specify_cli/lanes/implement_support.py
- tests/specify_cli/test_analysis_report.py
- tests/specify_cli/cli/commands/agent/test_record_analysis_mission_scoped_7556.py
- tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py
- docs/changelog/unreleased/7556-mission-scoped-dirty-gates.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Gates count only this Mission's dirt (#7556)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `implementer-ivan` (role `implementer`).

---

## Objectives & Success Criteria

- `record-analysis` refuses `DIRTY_WORKTREE` only for this Mission's own uncommitted paths,
  after its existing filters. Every other dirty path is reported: in JSON as
  `foreign_dirty_paths` on the success payload, and in human output as one warning line per
  path (contract `contracts/cli-observable-behaviour.md`).
- The single_branch claim (`_ensure_repo_root_checkout_available`) stops refusing on another
  Mission's paths and prints a warning naming them. Code dirt and this Mission's own
  non-exempt files still refuse `WRITE_CHECKOUT_DIRTY` (#5905: the WP commits code in that
  checkout).
- Closes #7556.

## Context & Constraints

- Research D2. Decision Moment `01M75NY1Q2F35PYMESZB0S5DWN`.
- The predicate from WP01, `partition_mission_dirt`. The Mission's own directory names come
  from `specify_cli.missions._read_path_resolver.mission_dir_aliases(repo_root, slug)`, the
  same source `ResidueContext.for_mission` uses, so composed `<slug>-<mid8>` directories count
  as own.
- Do not change the claim's own prefix list (`_owned_status_prefixes`): its docstring says
  "Do not align the lists". Apply the Mission scoping after it.
- No new git call: classify the paths each gate already listed (NFR-001).

## Branch Strategy

- **Strategy**: single_branch, direct in the repository root checkout
- **Planning base branch**: fix/7545-cli-owns-its-commits
- **Merge target branch**: fix/7545-cli-owns-its-commits

## Subtasks & Detailed Guidance

### Subtask T004 – Red test: record-analysis

- New file `tests/specify_cli/cli/commands/agent/test_record_analysis_mission_scoped_7556.py`.
  Copy the fixture shape of `tests/specify_cli/test_analysis_report.py::test_record_analysis_refuses_dirty_worktree_before_write`
  (real git repository, `CliRunner` on `mission_app`).
- Case A (red before the fix): an untracked `kitty-specs/other-01ABCDEF/notes.md`, plus a
  collapsed directory. Expect exit 0, the report written, and `foreign_dirty_paths` naming
  `kitty-specs/other-01ABCDEF/`.
- Case B (control, green before and after): an uncommitted edit to this Mission's `spec.md`
  is still refused with `DIRTY_WORKTREE`.
- Case C: root `dirty.txt` → success with a warning (the issue's Expected section).
- Commit the red test alone first.

### Subtask T005 – Scope the record-analysis gate

- In `_enforce_analysis_report_write_preflight`, after the two existing filters, partition with
  `partition_mission_dirt(dirty_paths, own_dir_names=...)`. Refuse only on `own`. Return the
  foreign paths (`other_mission + outside`) to the caller and thread them into the success
  payload as `foreign_dirty_paths` (omitted when empty). In human mode print
  `Warning: uncommitted path outside this Mission (not recorded): <path>` per path.
- Keep the function ≤ 15 complexity: extract a `_report_foreign_dirt` helper.
- Update the remediation text if it still says "Commit or stash the listed paths": it is still
  correct for own paths.

### Subtask T006 – Re-pin the root-dirt test

- `test_record_analysis_refuses_dirty_worktree_before_write` plants a root `dirty.txt`. Under
  #7556 that is a warning, so the test is stale, not wrong. Move its dirt into the Mission
  directory (for example an edit to `spec.md`) so it keeps pinning "the gate refuses before
  any write", and say why in a comment citing #7556.

### Subtask T007 – Red test: single_branch claim

- In `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`, next to
  `test_dirty_checkout_refuses`, add:
  - `test_other_mission_residue_does_not_refuse_the_claim`: an untracked
    `kitty-specs/other-01ABCDEF/notes.md`; the claim succeeds and the output warns.
  - Keep `test_dirty_checkout_refuses` as the same-fixture control (code dirt refuses).

### Subtask T008 – Scope the claim gate

- In `_ensure_repo_root_checkout_available`, partition `_claim_dirty_paths(...)` and refuse on
  `own + outside`; warn about `other_mission` through the module logger plus a
  `rich`/`print` line consistent with how this module reports (check
  `implement_support.py` for an existing warning sink; if there is none, return the list and
  let `implement_cores` print it, following the existing claim-warning pattern
  `implement_claim.py:95-99`).

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_record_analysis_mission_scoped_7556.py tests/specify_cli/test_analysis_report.py tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py -q
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py tests/integration/test_single_branch_write_checkout_e2e.py tests/lanes -q
```

## Risks & Mitigations

- Weakening a real guard: the claim keeps refusing on code dirt, and record-analysis keeps
  refusing on its own Mission. Both controls are tested in the same fixture.

## Review Guidance

- Red commit before fix commit; controls present; no new git call in either gate.
