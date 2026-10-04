---
work_package_id: WP03
title: Split executor.py along phase boundaries
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-003
- C-004
- C-005
- SC-001
- SC-002
- SC-003
- C-002
planning_base_branch: issue-2026-consolidation-decomposition
merge_target_branch: issue-2026-consolidation-decomposition
branch_strategy: Planning artifacts for this mission were generated on issue-2026-consolidation-decomposition. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2026-consolidation-decomposition unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Executor split
history:
- at: '2026-10-04T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/run_state.py
- src/specify_cli/consolidation/coord_strand.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/phase_advance.py
- src/specify_cli/consolidation/phase_bookkeeping.py
- src/specify_cli/consolidation/phase_gate.py
- src/specify_cli/consolidation/phase_teardown.py
- src/specify_cli/consolidation/phase_finalize.py
- src/specify_cli/consolidation/entry_preflight.py
- src/specify_cli/consolidation/resume_recovery.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/run_state.py
- src/specify_cli/consolidation/coord_strand.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/phase_advance.py
- src/specify_cli/consolidation/phase_bookkeeping.py
- src/specify_cli/consolidation/phase_gate.py
- src/specify_cli/consolidation/phase_teardown.py
- src/specify_cli/consolidation/phase_finalize.py
- src/specify_cli/consolidation/entry_preflight.py
- src/specify_cli/consolidation/resume_recovery.py
- tests/consolidation/test_single_rollback_authority.py
- tests/consolidation/test_executor_*.py
- tests/consolidation/test_issue_*.py
- tests/consolidation/test_merge_canceled_wp.py
- tests/consolidation/test_merge_rollback_resume_coherence.py
- tests/consolidation/test_merge_state_authority.py
- tests/consolidation/test_merge_divergent_end_to_end.py
- tests/consolidation/test_behind_head_recovery_coverage.py
- tests/consolidation/test_resume_coord_lag.py
- tests/integration/test_merge_*.py
- tests/integration/sparse_checkout/*.py
- tests/specify_cli/cli/commands/test_merge_coord_*.py
- tests/terminus/*.py
- tests/architectural/test_destructive_op_routing.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/architectural/test_status_events_writes_gate.py
- tests/architectural/test_coord_read_residuals_closeout.py
- tests/architectural/test_exemption_registry_ratchet.py
- tests/architectural/test_layer_rules.py
- tests/architectural/tool_artifact_enrolment/registry/_GATE_ARTIFACT_FILENAMES.md
- tests/specify_cli/test_meta_fail_closed_full_census_contract.py
role: reviewer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Split executor.py along phase boundaries

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Epic #2026 slice 1 (tactic extract-class-by-responsibility-split, applied at module level):

- `executor.py` keeps exactly: `_record_operator_attestations`, `_run_lane_based_consolidation_locked` (with its inline door `try`, inline phase calls and `anchor_before`), `_report_rollback`, `_run_lane_based_consolidation`, `__all__`, and the imports they need.
- Everything else moves **verbatim** (byte-identical bodies, decorators kept, leading comments kept) into the ten modules of plan.md (mapping: `research.md` R-2; machine-readable map in the implementer's splitter).
- Every `@_records_post_mutation_tips` decoration stays on the same six functions.
- Tests: imports and attribute reads re-pointed to the defining module; every monkeypatch on `executor.<name>` re-pointed to *every* module that loads `<name>` (so the interception set is identical).
- Gates: re-pointed or widened; none loosened (code-grounding §3).
- Commit series (one commit per step below) so each step is reviewable alone.

## Context & Constraints

- Invariants I1-I16 (code-grounding §2). C-004: `rollback_to_snapshot` callers stay `executor._report_rollback` + `consolidate._abort_restore_or_keep_record`; the door stays one `try` in the driver.
- No logic edit while moving (C-005). A move that needs a logic edit to work is a design error: stop and re-cut.
- Do not touch `p0_repro` tests or #5613 (C-002). No new size gate (C-003).

## Branch Strategy

- **Strategy**: single_branch — repository root checkout.
- **Planning base branch**: issue-2026-consolidation-decomposition
- **Merge target branch**: issue-2026-consolidation-decomposition

## Subtasks & Detailed Guidance

### T012 – Failing-first gate tightening

`tests/consolidation/test_single_rollback_authority.py::test_executor_builds_no_revert_argv` scans `executor.py` only; after the split it would silently stop covering moved code. Change it to scan the executor family (`executor.py` + the ten new modules), each file required to exist. Commit red (new files do not exist yet). Keep the non-vacuity self-tests.

### T013 – Verbatim split

Use an AST splitter: slice each top-level definition (with its decorators and leading comment block) into its target module in original order; each module gets a docstring naming its phase and the full executor import header, then `ruff check --select F401,I --fix` prunes/sorts imports; cross-module imports are computed from the names each module loads. Verify the import DAG has no cycle (plan.md). Module docstrings: one paragraph each, naming the phase, the invariants it carries (by I-number), and that it was relocated verbatim from `executor.py` by #2026.

### T014 – Byte-identity proof

Script: for every top-level definition in `git show <base>:src/specify_cli/consolidation/executor.py`, find it in its new module and compare `ast.get_source_segment` (including decorators). Zero differences required. Record the script output in the PR.

### T015 – Test imports / attribute reads

For `from specify_cli.consolidation.executor import X` and `ex.X` reads/calls where `X` moved: import from the defining module. Keep `executor` imports for names it still defines.

### T016 – Monkeypatch interception audit

For every patch of `executor.<name>` (string targets `"specify_cli.consolidation.executor.<name>"`, `setattr(<executor alias>, "<name>", ...)`, `patch.object(<alias>, "<name>", ...)`): compute L(name) = new modules whose code loads `<name>` as a global (plus `executor` if it still does). Replace the single patch by one patch per module in L(name). If L(name) is empty, the patch was already vacuous on main — keep the test's meaning by patching the module that defines/uses it and note it in the tracer. Re-run the audit at the end: zero patches on `executor` for names it no longer loads.

### T017 – Path/qualname-keyed gates

- `test_destructive_op_routing.py:235-237` (`_recover_behind_head_primary_on_resume` → `resume_recovery.py`), `:426-438` (`guarded_worktree_remove(` substring → `phase_teardown.py`).
- `test_no_write_side_rederivation.py:1363-1364` (`_phase_baseline_and_surface` → `phase_advance.py`; `_run_lane_based_consolidation` stays in executor).
- `test_status_events_writes_gate.py:140` (`write_bytes` in `_restore_regressed_gate_artifacts` → `specify_cli.consolidation.phase_advance`).
- `_GATE_ARTIFACT_FILENAMES.md:20` `module:` → `phase_advance.py`.

### T018 – Widen fixed-scope gates (never narrow)

Add the receiving modules to: `test_coord_read_residuals_closeout.py::_STATUS_BEARING_MODULES` (keep executor.py, asserted at :573), `test_exemption_registry_ratchet.py::CHURN_SURFACE_MODULES`, `test_no_write_side_rederivation.py::_WRITE_DIR_CONSUMER_MODULES`, `test_meta_fail_closed_full_census_contract.py::_WP09_OWNED_FILES`, `test_merge_compat_surface.py::_SEAM_IMPORT_TARGETS`, `test_layer_rules.py::_MERGE_CLI_CONSOLE_IMPORTERS` (the stale-entry guard decides whether executor.py stays).

### T019 – Module maps

`executor.py` module docstring: the new map. `cli/commands/consolidate.py` header comment (the `#2057 DECOMPOSITION SHIM` block): list the new modules (one comment block; out-of-map edit, WP02 owns the file).

### T020 – Validation

```bash
.venv/bin/python -m pytest tests/consolidation tests/specify_cli/consolidation tests/orchestrator_api tests/lanes -n 4 --dist loadfile -q
.venv/bin/python -m pytest tests/terminus -n 4 --dist loadfile -q
make test-fast
.venv/bin/python -m pytest <every test file touched> <named gate files from T017/T018> tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py tests/architectural/test_layer_rules.py -q
ruff check <changed>; ruff format --check --force-exclude <changed>; mypy <changed src>; ruff check --select C901 src/specify_cli/consolidation
```

## Risks & Mitigations

- Silent patch non-interception → T016 audit.
- Conflict with PR #5633 → mapping in code-grounding §5.

## Review Guidance

- Byte-identity output (T014) is the main evidence; `git diff --color-moved` should show moves only.
- Re-check each widened gate fails when a planted revert argv / status read is put in a new module.

## Activity Log

- 2026-10-04T09:00:00Z – system – Prompt created.
