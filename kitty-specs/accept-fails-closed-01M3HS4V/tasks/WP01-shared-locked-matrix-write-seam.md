---
work_package_id: WP01
title: Shared locked acceptance-matrix write seam
dependencies: []
requirement_refs:
- C-004
- FR-001
- FR-002
- NFR-001
- NFR-002
planning_base_branch: claude/project-thread-zj01ct
merge_target_branch: claude/project-thread-zj01ct
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-zj01ct. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-zj01ct unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-accept-fails-closed-01M3HS4V
base_commit: 8b07d554784a27d76aa2319b829a5339baf20004
created_at: '2026-09-27T16:08:31.884358+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-09-27T16:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent:
- tests/specify_cli/acceptance/test_matrix_write_seam.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/acceptance/matrix.py
- src/specify_cli/cli/commands/agent/acceptance_verdict.py
- tests/specify_cli/acceptance/test_matrix_write_seam.py
- tests/specify_cli/acceptance/test_acceptance_verdict_command.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Shared locked acceptance-matrix write seam

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it.

Mission: `accept-fails-closed-01M3HS4V`. Read `../spec.md`, `../plan.md`, `../research.md`.

## Objectives & Success Criteria

- `acceptance/matrix.py` exposes `locked_reread_splice_and_write(*, repo_root, mission_slug, matrix_dir, splice, commit, entry_id=None, message=None) -> tuple[AcceptanceMatrix, WriteSeamResult | Path]` (exact return shape is the implementer's call; keep it typed). Under `feature_status_lock(repo_root, matrix_dir.name, timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS)` it re-reads (empty schema-valid matrix if the file vanished), applies `splice(fresh)`, then writes via `write_and_commit_acceptance_matrix` (commit=True) or `write_acceptance_matrix` (commit=False). Lock timeout propagates with no write (FR-001, NFR-002, C-004).
- `splice_owned_rows(fresh, snapshot, judged) -> None` implements spec.md "Row ownership rule (FR-003)" for both `criteria` and `negative_invariants`: take `judged`'s row only when snapshot row was `pending`, judged row is not `pending`, fresh row is `pending`, and the judgement-defining fields (NI: `verification_method`, `verification_command`, `scope`; criterion: `proof_type`, `description`) are equal between snapshot and fresh. Fresh-only rows kept; snapshot-only rows not re-added. Check the actual model field names in `matrix.py` before coding.
- `locked_acceptance_verdict_guard(repo_root, matrix_dir)`: a context manager that takes the same lock, re-reads, raises a typed error (subclass or reuse of an existing acceptance error; `AcceptanceError` lives in `specify_cli.acceptance.__init__` so avoid a circular import — define a matrix-level error and let WP02 translate) unless `overall_verdict` is `pass` or `VERDICT_PASS_PENDING_CONSOLIDATION`, then yields while holding the lock (FR-010 primitive).
- `acceptance_verdict.py` calls the shared seam with `commit=True` for both modes; `_locked_reread_splice_and_write` is deleted (FR-002).

## Tests (new file `tests/specify_cli/acceptance/test_matrix_write_seam.py`)

- Lock-spy: re-read and write happen while the lock is held; the lock key is `matrix_dir.name`; timeout → no write.
- `splice_owned_rows` table: owned transition applied; fresh terminal wins; fresh-only row kept; snapshot-only row not re-added; re-registered NI (changed command) keeps fresh `pending`; criterion variant.
- Guard: pass / pass_pending_consolidation yield; pending / fail raise; lock held during the body.
- FR-002 wiring control: monkeypatch the seam to raise → the `acceptance-verdict` CLI (CliRunner) exits non-zero.
- Keep `tests/specify_cli/acceptance/test_acceptance_verdict_command.py` (#4858 concurrency + lock-spy classes) green; re-point patches to the seam module if they targeted the deleted private helper.

## Validation

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/acceptance/ tests/lanes/test_acceptance_matrix.py -q
.venv/bin/ruff check src/specify_cli/acceptance src/specify_cli/cli/commands/agent/acceptance_verdict.py && .venv/bin/ruff format --check src tests/specify_cli/acceptance && .venv/bin/mypy src/specify_cli/acceptance/matrix.py src/specify_cli/cli/commands/agent/acceptance_verdict.py
```

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: claude/project-thread-zj01ct
- **Merge target branch**: claude/project-thread-zj01ct

## Governance

- Load `.kittify/charter/charter.md` and `spec-kitty charter context --action implement --json`.
- ATDD / red-first: commit the issue-pinned `@pytest.mark.regression` test(s) first and show them RED against the pre-fix product code, then the fix.
- New code: ruff, `ruff format --check`, mypy clean; complexity ≤ 15; tests in the same commit as new branches/helpers. Terminology: Mission, never feature.
- Do NOT run `make test-full`, the whole `tests/architectural/` directory, or e2e/performance suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Run the targeted files listed below plus the owning subsystem's fast tier.

## Post-tasks squad folds (binding; out-of-map edits below are pre-authorized under ownership-map leeway)

- `tests/architectural/test_status_events_writes_gate.py` `EXPECTED_LOCK_COMPOSITION_SITES` (~L146-186, exact-set census at ~L632): replace the `...agent.acceptance_verdict` entry with `specify_cli.acceptance.matrix` and a rationale naming #4887 (shared seam + pre-stamp guard). Run that file.
- `test_acceptance_verdict_command.py` patches at ~L965, 1012, 1054-1056, 1134-1135 target `av_command.feature_status_lock` / `read_acceptance_matrix` / `write_and_commit_acceptance_matrix`; re-point ALL of them at `specify_cli.acceptance.matrix.<name>` so they stay non-vacuous. Remove the now-unused imports in `acceptance_verdict.py` (keep `FeatureStatusLockTimeoutError` for the translation).
- The seam must read the timeout constant at call time (or accept a `timeout` kwarg) so tests can shorten it; do not bind `BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS` in a default argument.
- `splice_owned_rows` must tolerate a matrix whose `criteria` / `negative_invariants` attribute is absent (unit-test doubles) — treat as empty.
