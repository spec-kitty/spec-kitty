---
work_package_id: WP01
title: Migration repository requirement (#6539)
dependencies: []
requirement_refs:
- C-002
- C-004
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
planning_base_branch: tidy-charter-6539-followups
merge_target_branch: tidy-charter-6539-followups
branch_strategy: Planning artifacts for this mission were generated on tidy-charter-6539-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into tidy-charter-6539-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-followups-tidy-01M5CCYJ
base_commit: 44269f646d195f8656dabf0d6ef2950a2a4627c2
created_at: '2026-10-20T11:44:43.638539+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Parallel work packages
history:
- at: '2026-10-20T11:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/specify_cli/upgrade/test_requires_git_repository_audit.py
- tests/specify_cli/cli/commands/test_upgrade_preview_outside_git.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/migrations/base.py
- src/specify_cli/upgrade/runner.py
- src/specify_cli/upgrade/migrations/m_*.py
- src/specify_cli/cli/commands/upgrade.py
- tests/specify_cli/upgrade/test_runner_not_a_git_repository.py
- tests/specify_cli/upgrade/test_requires_git_repository_audit.py
- tests/specify_cli/cli/commands/test_upgrade_preview_outside_git.py
- docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
- AGENTS.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Migration repository requirement (#6539)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role `implementer`). Behave according to it before reading the rest of this prompt. If the skill is unavailable, read `packs/built-in/agent_profiles/python-pedro.agent.yaml` directly.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` in the event log (`spec-kitty agent tasks status --mission charter-followups-tidy-01M5CCYJ`). If this WP came back from review, every feedback item is your TODO list. Record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Issue #6539. Operator decisions: `migration_repo_requirement` and `migration_flag_ledger_drift` (see `kitty-specs/charter-followups-tidy-01M5CCYJ/decisions/`).

- `BaseMigration` gains `requires_git_repository: ClassVar[bool] = False`.
- **Outside a git repository**, the upgrade runner skips a migration that declares it:
  - the check happens **before `detect()`**;
  - the warning says "not inside a git repository";
  - **no ledger record** is written.
- **The runner's `apply()`-level `NotInsideRepositoryError` catch no longer turns the error into a skip.** That error, raised from `apply()`, is handled like any other failed migration:
  - it is recorded `failed`, except for `runs_first` migrations, which record nothing on failure, as today;
  - the command exits non-zero, without a traceback;
  - the existing failed-migration version-stamp handling applies.
- **The `detect()` and `can_apply()` catches stay (C-004).**
- **Every shipped migration that calls `charter.resolution.resolve_canonical_repo_root`, directly or transitively, declares the flag.** This is proven by an instrumented full-registry audit that becomes a permanent test.
- **`spec-kitty upgrade --dry-run --verbose`** reports a flagged migration as not applicable outside a repository instead of crashing.
- Spec: `kitty-specs/charter-followups-tidy-01M5CCYJ/spec.md` User Story 1, FR-001/002/003, SC-001/002.

## Context & Constraints

- Read `.kittify/charter/charter.md`. ATDD and red-first apply (NFR-003). Zero new `# noqa` / `# type: ignore` (NFR-001). Complexity ≤ 15 (NFR-002).
- Ledger model: ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`.
  - An unrecorded migration is selected again on the next run.
  - A `failed` record retries.
  - `apply()` must be idempotent.
- `runner.py` has `NotInsideRepositoryError` catches at about these lines:
  - :387, around `detect()`;
  - :434, around `can_apply()`;
  - :450, around `apply()`.
  - All three go to `_not_inside_repository_skip` (about :477).
  - The `apply()` `except` today returns `failed` only for `GitignorePathError`/`MigrationStateUnreadableError`, and does **not** call `_record_migration_result`.
  - The recording happens after it (about :465), and only for `result.success or not migration.runs_first`.
  - The main loop stops on the first failure (about :287).
- The only raiser is `charter.resolution.resolve_canonical_repo_root` (`src/charter/resolution.py:134`). It accepts a project inside a subdirectory of a repository. "Not inside a repository" means exactly what it raises for. Use the same resolver, or an equivalent probe that matches it exactly, for the pre-detect gate. Do **not** use `is_git_checkout_root`, which is stricter.
- Callers:
  - Direct: `m_3_2_0rc35_unified_bundle.apply`, about :157.
  - Transitive: `charter.activation.sync` (`ensure_charter_bundle_fresh` about :102, `_charter_yaml_path` about :215) and other `charter.activation.*` paths.
  - About 10 migrations import `charter.activation.*`. **Grep is not enough.** The audit must execute.
- **Ledger drift is accepted (C-002).** Adding the ClassVar to a shipped migration module changes its `content_hash`, which shows up as audit-only drift. Do not try to hide it: no `content_hash_sources` games. The drift is documented in T006.
- The worktree upgrade loop (`_upgrade_worktrees`, called at about `runner.py:234` and `:296`) is out of scope: a worktree is always inside a repository. Confirm in one `add-history` line whether it routes through the same per-migration step; if it does, the new gate is harmless there.

## Branch Strategy

- **Strategy**: lanes_with_coord (populated by finalize-tasks)
- **Planning base branch**: tidy-charter-6539-followups
- **Merge target branch**: tidy-charter-6539-followups

The execution worktree is allocated per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP01 --agent claude --mission charter-followups-tidy-01M5CCYJ`, and use the workspace path it prints.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first runner tests

- **Purpose**: pin the new contract before changing code (NFR-003).
- **Steps**: extend `tests/specify_cli/upgrade/test_runner_not_a_git_repository.py`. Reuse its existing non-git fixture and the way it drives the runner.
  1. **A flagged migration is skipped before `detect()`.** A fake migration with `requires_git_repository = True` whose `detect()` records a call, or raises. On a non-git temp project:
     - its `detect()` is never called;
     - the result is `skipped` with the "not inside a git repository" warning;
     - the ledger has no record for it.
  2. **An unflagged migration that writes and then raises is a failure.** Its `apply()` writes a marker file, then raises `NotInsideRepositoryError`. Assert:
     - the run reports a failure (and exits non-zero at the CLI level, if you drive the CLI);
     - a `failed` ledger record exists;
     - the marker file exists, which proves the write is visible, not silently "skipped".
     - Add the `runs_first` variant: a failure with no record.
  3. **Inside a repository, nothing changes.** In a git-initialised temp project, a flagged migration runs normally (positive control on the same fixture shape).
  4. **The rc35 migration declares the flag.** Assert `requires_git_repository is True` on its class.
- Run the tests on the unchanged source first and record the failures (the red proof): for example `uv run --frozen pytest tests/specify_cli/upgrade/test_runner_not_a_git_repository.py -q`. Note them in `add-history`.
- Mark the tests with the repo's existing markers for that file. Do **not** leave any `@pytest.mark.regression` marker on them when you finish.
- **Files**: `tests/specify_cli/upgrade/test_runner_not_a_git_repository.py`.

### Subtask T002 – ClassVar + pre-detect gate

- **Steps**:
  1. In `src/specify_cli/upgrade/migrations/base.py`, add `requires_git_repository: ClassVar[bool] = False` beside `runs_first` / `clone_local_effect`. Give it a docstring comment in the same style as those ClassVars: what it means, who sets it, and that the runner checks it before `detect()`.
  2. In `runner.py`, at the top of the per-migration step, before `detect()`: if `migration.requires_git_repository` and the project is not inside a repository, return the skip.
     - Reuse `_not_inside_repository_skip`, or rename it if its docstring no longer fits.
     - Compute "inside a repository" once per run, not once per migration, if that is simple. For example, a cached probe that calls `resolve_canonical_repo_root(self.project_path)` and catches `NotInsideRepositoryError`.
  3. Keep complexity ≤ 15. Extract a helper if the step function grows.
- **Files**: `base.py`, `runner.py`.

### Subtask T003 – apply()-time repository error is a failure

- **Steps**:
  1. Change the `apply()`-level `except NotInsideRepositoryError` (about :450) so it no longer returns the skip. Route it through the same failed-migration path as any other apply failure: a `failed` result, recorded unless `runs_first`, with a clear error message that names the migration and says it needs a git repository.
     - Check how a generic exception from `apply()` is handled today.
     - If it propagates as a traceback, catching `NotInsideRepositoryError` and returning a failed `MigrationResult` with an error message is the minimal fix. That lets the existing loop record it and stop.
  2. Keep the `detect()` and `can_apply()` catches (C-004). Update `_not_inside_repository_skip`'s docstring: the `apply()` hazard is gone, and the two remaining catches are pre-write by construction.
- **Files**: `runner.py`.

### Subtask T004 – Instrumented full-registry audit; flag every resolver caller

- **Purpose**: decide by execution, not by grep, which shipped migrations need the flag (SC-001, US1 AC4). The audit then stays as a permanent regression test.
- **Steps**:
  1. Create `tests/specify_cli/upgrade/test_requires_git_repository_audit.py`. Fixture: a temp dir that is **not** inside any git repository (use the existing fixture helpers if they exist), with:
     - `.kittify/metadata.yaml` at the oldest supported version (look at how other upgrade tests seed an old project);
     - an empty ledger;
     - `HOME`/XDG isolated, as the conftest already does.
  2. Instrument `charter.resolution.resolve_canonical_repo_root` with `monkeypatch` on every import site migrations reach it through (`charter.resolution` and any `from … import resolve_canonical_repo_root` aliases). The instrument records the calling migration and raises `NotInsideRepositoryError` as the real one would.
  3. Run the full shipped registry through the runner. Assert:
     - every migration during whose `detect`, `can_apply` or `apply` the resolver was called declares `requires_git_repository`;
     - the run reaches the last migration in `order_manifest.txt`.
     - If an unrelated migration fails on the bare fixture, make the fixture more realistic. Do not weaken the assertion.
  4. Run the audit and add `requires_git_repository = True` to each flagged migration class, at minimum `m_3_2_0rc35_unified_bundle`. One short comment line per class (why: it resolves the canonical repo root).
  5. Make sure the audit failed before step 4: rc35 is unflagged on the unchanged source.
- **Files**: the new test file, plus the flagged `src/specify_cli/upgrade/migrations/m_*.py`. **Only add the ClassVar line and its comment; change nothing else in a shipped migration.**

### Subtask T005 – Dry-run preview

- **Purpose**: `upgrade --dry-run --verbose` (`src/specify_cli/cli/commands/upgrade.py`, about :685-705) calls `migration.detect()` and `can_apply()` directly, and catches only `GitignorePathError`. Outside git it crashes on rc35.
- **Steps**:
  - In that loop, report a flagged migration as `skipped` with the reason "not inside a git repository" **without** calling `detect()`.
  - Reuse the runner's probe and helper if there is one, so the rule lives in one place (single canonical authority).
  - Do not otherwise restructure the preview.
- **Test**: `tests/specify_cli/cli/commands/test_upgrade_preview_outside_git.py`. Drive the CLI with `--dry-run --verbose` on a non-git project; it exits 0 and shows the skip for rc35. It must be red first.
- **Files**: `src/specify_cli/cli/commands/upgrade.py` and the new test.

### Subtask T006 – Docs

- ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`: append a short dated note (2026-10-20, #6539) covering:
  - the `requires_git_repository` ClassVar and its semantics: skip unrecorded, checked before `detect()`;
  - an `apply()`-time repository error is now a recorded `failed`;
  - the content-hash drift on the migrations that declare it is accepted, with the list of those migrations.
- `AGENTS.md` (`CLAUDE.md` is a symlink to it), "Authoring a NEW migration" bullets: add one bullet for `requires_git_repository`. Match the surrounding bullets' style.
- Docstrings: `_not_inside_repository_skip` and the ClassVar.
- The changelog is **not** yours. The orchestrator writes it at closeout.

## Test Strategy

- **Red-first:**
  - every new test must fail on the unchanged source;
  - record the red runs with `add-history`.
- **Blast radius (run all; both dirs are out of the PR CI matrix, so they must be green locally):**
  - `uv run --frozen pytest tests/specify_cli/upgrade/ -n 4 --dist loadfile`
  - `uv run --frozen pytest tests/specify_cli/cli/commands/test_upgrade_command.py tests/specify_cli/cli/commands/test_upgrade_preview_outside_git.py`
- **Architectural gates:**
  - `uv run --frozen pytest tests/architectural/test_migration_order_manifest.py tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py`
- **Baseline:** `make test-fast`.
- **Static checks:**
  - `uv run --frozen ruff check <changed files>`
  - `uv run --frozen ruff format --check --force-exclude <changed .py files>`
  - `uv run --frozen mypy <changed src files>`, with 0 new errors.
- **Pre-existing reds:** classify any red per the baseline-red gotcha in `AGENTS.md`. `test_upgrade_command_skill_drift::test_6155_*` is a known red (#6416).

## Risks & Mitigations

- **A transitive resolver caller is missed:** the audit executes the registry, so it catches the caller.
- **The bare fixture trips an unrelated migration:** make the fixture realistic; never loosen the audit.
- **Content-hash drift (accepted):** list the flagged migrations in the ADR note, so the PR and changelog can cite them.

## Review Guidance

- Check that the `apply()` catch no longer returns a skip.
- Check that a written-then-raise migration is recorded `failed`.
- Check that the audit:
  - executes the registry (it is not a grep);
  - instruments every import alias;
  - would fail if a flag were removed (try removing rc35's flag).
- Check that shipped migrations changed only by the ClassVar line and a comment.
- Check that the preview no longer calls `detect()` for flagged migrations outside git.
- Check that mypy and ruff are clean, with no new suppressions.

## Progress & Status

Record progress with:
- `spec-kitty agent tasks mark-status T001 --status done --mission charter-followups-tidy-01M5CCYJ`
- `spec-kitty agent tasks add-history WP01 --note "..." --mission charter-followups-tidy-01M5CCYJ`
