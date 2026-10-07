---
work_package_id: WP01
title: Red-first CLI reproductions (#5811,
dependencies: []
requirement_refs:
- FR-009
- NFR-001
- SC-001
- SC-003
planning_base_branch: issue-5811-upgrade-preserves-mission-history
merge_target_branch: issue-5811-upgrade-preserves-mission-history
branch_strategy: Planning artifacts for this mission were generated on issue-5811-upgrade-preserves-mission-history. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5811-upgrade-preserves-mission-history unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-preserves-mission-history-01M49D3A
base_commit: b1c03795babb5c29d2e7feb719086728b5624cf2
created_at: '2026-10-07T04:47:55.309102+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Red-first
history:
- at: '2026-10-07T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/migration/
create_intent:
- tests/integration/migration/test_noop_upgrade_history_untouched_5811.py
- tests/integration/migration/test_residue_dir_not_mission_5812.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/integration/migration/test_noop_upgrade_history_untouched_5811.py
- tests/integration/migration/test_residue_dir_not_mission_5812.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01: Red-first CLI reproductions (#5811, #5812)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter, and follow its guidance before reading the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show python-pedro` and apply the resolved profile.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ Review Feedback

If this WP came back from review, read the `review_ref` in the event log first (`.venv/bin/spec-kitty agent tasks status --mission 01M49D3A`). Every feedback item is part of your work.

## Objective

Land two issue-pinned reproduction tests that run through the **real CLI entry points** and are **red on the base commit**. This follows ADR `2026-07-17-1` and charter Standing Order #4 (red-first, through the pre-existing entry point). This WP changes no product code.

Spec references: FR-009, NFR-001, User Stories 1 and 3.

## Branch Strategy

- Planning base and final merge target: `issue-5811-upgrade-preserves-mission-history`.
- Execution worktrees are allocated per computed lane from `lanes.json`. Prepare yours with `.venv/bin/spec-kitty agent action implement WP01 --agent claude` and work only in the workspace path it prints.

## Context You Need

- **p0_repro marker**: `@pytest.mark.p0_repro(issue=N)`, declared at `pytest.ini:80`, logic in `tests/_support/p0_repro.py`. It is deselected unless `SPEC_KITTY_RUN_P0_REPRO=1`. Per ADR `2026-07-17-1`, this is how a P0 repro rides the nightly lane until the fix lands. The fixing WPs (WP03 for #5812, WP04 for #5811) remove the marker.
- **Drain**: on by default in tests. The autouse fixture `_drain_posture_enabled` in `tests/conftest.py` (about line 2262) patches `hosted_posture.drain_posture`. **Do not** opt out (`@pytest.mark.real_drain_posture`). The repro must run with drain on, so the drain-off path cannot make it vacuously green.
- **Blocker shape**: `IDENTITY_MISSING` comes from a `meta.json` without `mission_id` (`src/specify_cli/audit/classifiers/meta.py:92`). For #5812, the blocker comes from a residue-only directory.
- **Writer-shaped history**: produce event logs with the **live writer**, never hand-written JSON. Use `specify_cli.status.emit.emit_status_transition`, or run `.venv/bin/spec-kitty agent tasks move-task` in a subprocess. Rows whose `reason_source` / `review_result` are `None` must lack those keys, exactly as `StatusEvent.to_dict()` writes them.
- **CI placement**: `tests/integration/migration/` is a per-PR CI module (`.github/ci-module-registry.yml` about line 687); `tests/upgrade/` is nightly-only. That is why the files live here.
- **Reference harnesses**:
  - `tests/integration/migration/test_mission_state_repair_fidelity_e2e.py`
  - `tests/migration/test_mission_state_repair.py`
  - `tests/upgrade/test_mission_corpus_recovery.py`: an end-to-end corpus with `upgrade`, useful for invoking the upgrade CLI on a scratch repo.

  Reuse their helpers where they fit. Do not copy large fixture blocks.

## Subtasks

### T001: #5811 repro, no-op `upgrade --yes` leaves history byte-identical

**File**: `tests/integration/migration/test_noop_upgrade_history_untouched_5811.py` (new)

**Steps**:
1. Build a scratch git repository in `tmp_path`: `git init`, user config, and a project bootstrapped the way the reference upgrade tests do it. Use `spec-kitty init` if the corpus test does; otherwise copy the minimal `.kittify/` the upgrade needs. The upgrade must report "already up to date" for its version, so the only work left is the finalizer repair offer.
2. Create **three** Missions with a valid identity (`meta.json` with `mission_id`). In each, drive one WP through at least three lane transitions with the live writer (`planned → claimed → in_progress → for_review`), so that some rows carry `reason` but no `reason_source` key. Include a Mission whose rows are in an order that differs from `(at, event_id)` sorting; for example, append two events with the earlier timestamp second (the writer accepts an explicit `at`). That catches the re-sort.
3. Create one Mission with a **blocker**: a `meta.json` without `mission_id`, plus a `spec.md`, tracked.
4. Commit everything. Snapshot the bytes of every file under `kitty-specs/` into a dict keyed by path.
5. Run `spec-kitty upgrade --yes --no-worktrees` **in-process** with `typer.testing.CliRunner().invoke(app, ...)` (see `tests/upgrade/test_mission_corpus_recovery.py` ~:285/:319), so the autouse drain patch applies. **Do not use a subprocess**: the patch does not reach a child process, drain would read as off, and after WP04 the test would pass vacuously on the drain-off path. Bootstrap the project as that harness does (`init --ai codex --yes`, then `git init`). Assert the output shows that the gate ran (the blocker count is printed). On base, the repair runs at this point.
6. Assert:
   - every pre-existing file under `kitty-specs/` has identical bytes;
   - no new file exists under `kitty-specs/`;
   - `git status --porcelain -- kitty-specs` is empty.
7. Mark the test `@pytest.mark.p0_repro(issue=5811)` and `@pytest.mark.regression`.

**Validation**: the test fails on base. It should fail on the `reason_source`/`review_result` null keys and the re-sort, with a diff that names the Mission paths.

### T002: #5811 repro, no audit manifest and a clean `auto_commit` commit

**Same file.**
1. Assert that `.kittify/mission-state-audit/` does not exist after the run, or holds no file it did not hold before.
2. Add a second test with `auto_commit` enabled in the project config. Find the key the upgrade uses: grep `auto_commit` in `src/specify_cli/cli/commands/upgrade.py`. Run `upgrade --yes`, then assert that `git show --name-only HEAD` (or the diff between the pre-run HEAD and HEAD) contains no `kitty-specs/` path.
3. Mark both tests the same way as T001.

### T003: #5812 repro, a residue directory is not a Mission

**File**: `tests/integration/migration/test_residue_dir_not_mission_5812.py` (new)
1. Scratch repository with one real Mission (tracked `meta.json` with `mission_id`, `spec.md`, writer-shaped log).
2. Create `kitty-specs/ghost-01ABCDEF/decisions/index.json.lock`, gitignored through `.gitignore` containing `*.lock`. Commit the `.gitignore` and the real Mission.
3. Run the mission-state audit through the CLI: `spec-kitty doctor mission-state --json`, or whatever the doctor exposes for audit-only; check `--help`. Assert that no `IDENTITY_MISSING` (no blocker of any kind) names `ghost-01ABCDEF`.
4. Run `spec-kitty doctor mission-state --fix` (add any flag the doctor needs to proceed non-interactively, for example `--allow-dirty` if the gitignored file counts). Assert that `kitty-specs/ghost-01ABCDEF/` contains no `meta.json`, `status.json`, `lanes.json` or `status.events.jsonl`.
5. Mark the tests `@pytest.mark.p0_repro(issue=5812)` and `@pytest.mark.regression`.

### T004: Red-on-base evidence

1. Run `SPEC_KITTY_RUN_P0_REPRO=1 .venv/bin/python -m pytest tests/integration/migration/test_noop_upgrade_history_untouched_5811.py tests/integration/migration/test_residue_dir_not_mission_5812.py -q` in your workspace (which is at base for product code).
2. Every test must **fail**, and for the right reason. For #5811, the assertion message names at least one `kitty-specs/<mission>/status.events.jsonl` path and the `reason_source` key, or the `.kittify/mission-state-audit/` manifest. For #5812, it names `ghost-01ABCDEF` and `IDENTITY_MISSING`, or a created file. If a test passes or errors in setup, the repro is wrong; fix the repro.
3. Put the failing summary lines (test id plus the first line of the assertion) in your WP hand-off note. Do **not** edit the tracer files: several lanes appending to them causes merge staleness. The orchestrator copies the evidence into the tracers.
4. Confirm that a default run (without the env var) deselects them: `.venv/bin/python -m pytest <files> -q` reports them as deselected.

## Test Economy

Write only these tests. They are the contract. Do not add unit tests for fixtures or helpers.

## Definition of Done

- Both files exist, run through the CLI on real scratch git repositories with drain on, and are red on base for the right reason.
- The default run deselects them, and the env-var run fails them.
- `ruff check`, `ruff format --check --force-exclude` and mypy (if the test dirs are type-checked) are clean on the two files.
- Evidence is recorded.

## Reviewer Guidance

- Reject a repro that mocks `repair_repo`, readiness or the writer. It must be end to end.
- Check that the #5811 fixture includes the order-sensitive Mission and rows without `reason_source`.
- Check that the #5812 lock file really is gitignored (`git check-ignore`).
