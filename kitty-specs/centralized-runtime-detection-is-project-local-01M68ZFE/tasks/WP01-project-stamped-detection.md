---
work_package_id: WP01
title: Project-stamped centralized-runtime detection, red-first
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
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6551-centralized-runtime-detection-is-project-local
merge_target_branch: issue-6551-centralized-runtime-detection-is-project-local
branch_strategy: Planning artifacts for this mission were generated on issue-6551-centralized-runtime-detection-is-project-local. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6551-centralized-runtime-detection-is-project-local unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-centralized-runtime-detection-is-project-local-01M68ZFE
base_commit: bad587f3c1fc63de07642906c74d37133369c4f7
created_at: '2026-10-31T12:43:47.768915+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - The fix
history:
- at: '2026-10-30T00:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_upgrade_empty_home_noop.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/compat.py
- tests/upgrade/test_compat.py
- tests/upgrade/test_upgrade_empty_home_noop.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package WP01 – Project-stamped centralized-runtime detection, red-first

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Review Feedback

**Read this first if you are working on this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Objectives & Success Criteria

- A project whose `.kittify/metadata.yaml` stamp is `>= 2.0.0` answers
  "centralized runtime" with `True` **without consulting the operator's home**.
- Consequently `0.6.7_ensure_missions.detect()` and
  `0.12.0_documentation_mission.detect()` answer `False` for such a project even
  when `~/.kittify/cache/version.lock` does not exist.
- A converged project's real `spec-kitty upgrade --project --yes`, run with an
  empty `SPEC_KITTY_HOME`, leaves the tracked tree unchanged: no
  `.kittify/missions/`, no `.kittify/overrides/`, clean
  `git status --porcelain`.
- Every existing metadata-less and pre-2.0 behaviour stays exactly as pinned.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6551. Charter: `.kittify/charter/charter.md`.
  Spec: `kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/spec.md`.
  Plan: `kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/plan.md`
  (IC-01, IC-02). Research decisions D-1..D-4:
  `kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/research.md`.
- **Do not** touch `src/specify_cli/upgrade/registry.py`,
  `src/specify_cli/upgrade/ledger.py`, `src/specify_cli/upgrade/runner.py` or any
  migration module. C-001: the ledger's `skipped`-does-not-settle rule and
  ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` §3 stay as they
  are; this work package fixes `detect()` inputs, not selection.
- C-002: `uses_centralized_runtime` stays the single answer to "is this a 2.x
  runtime project". Do not add a second predicate or a helper that duplicates it.
- `global_runtime_configured()` has exactly one caller (this predicate) and two
  migrations use the predicate. Do not widen the surface.

## Branch Strategy

- **Strategy**: single-branch mission on a topic branch
- **Planning base branch**: `issue-6551-centralized-runtime-detection-is-project-local`
- **Merge target branch**: `issue-6551-centralized-runtime-detection-is-project-local`

> Populated by `spec-kitty agent mission finalize-tasks`. Do NOT change these
> fields manually unless you are certain the branch topology has changed.
> Execution worktrees are allocated per computed lane from `lanes.json`; never
> build a workspace path by hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Red production-path regression test

- **Purpose**: Pin the user-visible outcome at the real entry point, so a future
  rewiring cannot regress it while helper tests stay green (tactic
  `acceptance-criteria-non-vacuity`, "Exercise the production path").
- **Steps**:
  1. Create `tests/upgrade/test_upgrade_empty_home_noop.py`, modelled on
     `tests/upgrade/test_upgrade_integration.py`: build a `typer.Typer` test app
     with `_test_app.command()(upgrade)`, `CliRunner`, and `contextlib.chdir`.
  2. Fixture: a real git repo (init, `user.email`/`user.name`, initial commit)
     whose `.kittify/metadata.yaml` carries `version: 4.0.0rc8`.
  3. Seed `.kittify/migration-ledger.jsonl` as **converged**: use
     `MigrationLedger`/`build_record` to append a `success` record for every
     declared migration, then replace the two legacy mission migrations'
     records with `skipped` records for `0.6.7_ensure_missions` and
     `0.12.0_documentation_mission` — that is exactly the state the issue
     measured under user A. Commit the fixture.
  4. Point `SPEC_KITTY_HOME` at an empty directory (monkeypatch the env var) and
     assert `(home / "cache" / "version.lock").exists() is False` before the run
     (assumption check).
  5. Run `["--project", "--yes", "--no-worktrees", "--target", "4.0.0rc8"]`.
  6. Assert: exit code 0; `git status --porcelain` is empty;
     `(project / ".kittify" / "missions").exists() is False`;
     `(project / ".kittify" / "overrides").exists() is False`.
  7. **Same-fixture positive controls (both required, no escape hatch):**
     a. *Absence probe is live*: after the run, re-read the ledger and assert it
        still contains a record for `0.6.7_ensure_missions` and for
        `0.12.0_documentation_mission` (the run re-skips idempotently, it does not
        erase). A probe that cannot see the ids cannot claim they are unchanged.
     b. *The probe can observe a change*: a second test on the **same fixture
        shape** (same helper, same git repo, same empty `SPEC_KITTY_HOME`) but
        with `metadata.yaml` stamped `1.2.0` must observe the opposite outcome —
        `.kittify/missions/software-dev/mission.yaml` exists after the run and
        the ledger carries a `success` (not `skipped`) record for
        `0.6.7_ensure_missions`. This is FR-004's positive control; if it does
        not go red on the pre-fix code the fixture is not exercising the branch
        the fix touches, and that is a fixture bug.
- **Files**: `tests/upgrade/test_upgrade_empty_home_noop.py` (new).
- **Parallel?**: No — it is the red that T005 turns green.
- **Notes**: `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`.
  Do not skip the test when `git` is unavailable; the sibling harness already
  assumes it.

### Subtask T002 – Helper pins for 4.x metadata with no home

- **Purpose**: State the contract directly, where the next reader looks.
- **Steps**: In `tests/upgrade/test_compat.py` add one test that builds a project
  with `.kittify/metadata.yaml` at `4.0.0rc8`, points `SPEC_KITTY_HOME` at an
  empty dir, and asserts `uses_centralized_runtime(project) is True`,
  `EnsureMissionsMigration().detect(project) is False` and
  `InstallDocumentationMission().detect(project) is False` — all three in one
  test so a future re-widening fails loudly in one place. Keep
  `pytest.mark.fast`.
- **Files**: `tests/upgrade/test_compat.py`.
- **Parallel?**: Yes, with T003.
- **Notes**: Mind the class name: the documentation migration class is
  `InstallDocumentationMission` (module
  `m_0_12_0_documentation_mission.py`), not `DocumentationMissionMigration`.

### Subtask T003 – Pre-2.0 positive control

- **Purpose**: Prove the fix does not trade a false positive for a false
  negative (FR-004). A fixture that asserts "2.x is skipped" proves nothing
  unless the same fixture shape still *runs* for 1.x.
- **Steps**: Add a test in `tests/upgrade/test_compat.py` with
  `.kittify/metadata.yaml` at `1.2.0` and a **bootstrapped** home
  (`home/cache/version.lock` present, as the existing tests already build it).
  Assert `uses_centralized_runtime(project) is False` and
  `EnsureMissionsMigration().detect(project) is True`.
- **Files**: `tests/upgrade/test_compat.py`.
- **Parallel?**: Yes, with T002.
- **Notes**: Also keep the pre-2.0-with-fresh-home case explicitly: metadata at
  `1.2.0` and an empty home must still answer `False` (today's behaviour), so the
  reorder cannot accidentally treat "no home" as "modern".

### Subtask T004 – Capture the red

- **Purpose**: Red-first discipline (DIRECTIVE_034). The new tests must fail on
  the pre-fix predicate, and the failure must be the defect, not a fixture bug.
- **Steps**: With `src/specify_cli/upgrade/compat.py` unmodified, run
  `.venv/bin/python -m pytest tests/upgrade/test_compat.py tests/upgrade/test_upgrade_empty_home_noop.py -q`
  and paste the failing assertions into the WP history note. Expected: `True`
  where `False` is required, and (in the integration test) 22-ish new files
  under `.kittify/overrides/missions/` with a dirty tree.
- **Files**: none.
- **Parallel?**: No.
- **Notes**: If the integration test does **not** go red, the fixture is not
  reproducing the issue — fix the fixture before touching the fix.

### Subtask T005 – Reorder the predicate

- **Purpose**: The fix.
- **Steps**: In `src/specify_cli/upgrade/compat.py`:
  1. Load `ProjectMetadata` from `project_path / ".kittify"` **first**.
  2. Return `Version(metadata.version) >= Version("2.0.0")` when the stamp parses;
     keep `False` for `InvalidVersion` (a project we cannot date is not assumed
     modern — D-3).
  3. Only when metadata is `None`, run today's logic unchanged: `False` when
     `not global_runtime_configured()`, else
     `not kittify_dir.exists() and (project_path / KITTY_SPECS_DIR).exists()`.
  4. Update the docstring so it says the home is consulted only for metadata-less
     shapes, and cite #6551.
- **Files**: `src/specify_cli/upgrade/compat.py`.
- **Parallel?**: No.
- **Notes**: `ProjectMetadata.load()` swallows `OSError`/`YAMLError` and returns
  `None`; do not add a second parse. No writes, no `ensure_runtime()` call
  (NFR-002) — detection must stay side-effect free.

### Subtask T006 – Re-run and confirm no collateral

- **Purpose**: Prove the blast radius is one predicate.
- **Steps**: Run, and paste results into the WP history note. `uv run pytest ...`
  and `.venv/bin/python -m pytest ...` are equivalent in this checkout — use
  whichever is already working; do not stall on a missing `.venv`.
  - `.venv/bin/python -m pytest tests/upgrade/test_compat.py tests/upgrade/test_upgrade_empty_home_noop.py tests/upgrade/migrations/test_m_0_6_7_ensure_missions.py tests/upgrade/test_m_0_12_0_documentation_mission_unit.py -q`
  - `.venv/bin/python -m pytest tests/upgrade -q`
  - `.venv/bin/ruff check src/specify_cli/upgrade/compat.py tests/upgrade/test_compat.py tests/upgrade/test_upgrade_empty_home_noop.py`
  - `.venv/bin/python -m mypy src/specify_cli/upgrade/compat.py` (or the repo's
    configured mypy target for this module)
- **Files**: none.
- **Parallel?**: No.
- **Notes**: A red in `tests/upgrade/` that also fails on pristine `origin/main`
  is pre-existing — reproduce it in a clean worktree of `origin/main`, say so in
  the WP history, and cite it; never skip or xfail it to get green.

## Test Strategy

- Red first: T001–T003 authored before T005, red captured in T004.
- Run the suites with `uv run pytest <paths> -q` (the brief's form) or
  `.venv/bin/python -m pytest <paths> -q` — both are equivalent here.
- Unit tier: `pytest.mark.fast` in `tests/upgrade/test_compat.py`.
- Integration tier: `pytest.mark.integration` + `pytest.mark.git_repo` for the
  real `upgrade` invocation.
- Do **not** run a full heavy suite locally (NO_FULL_HEAVY_SUITES_IN_MISSION);
  `tests/upgrade/` plus the two touched migration test modules is the local bar,
  CI owns the sweeps.

## Risks & Mitigations

- **Reordering changes metadata-less answers (FR-005)**: the four existing
  `test_compat.py` cases are the guard; run them after T005.
- **Vacuous "no change" assertion**: without the positive control, an upgrade
  that never ran would pass. T001 step 7 requires the ledger assertion.
- **Fixture not converged**: an empty ledger selects a different code path.
  Seed `skipped` records for the two legacy ids exactly as the issue measured.
- **Environment leakage**: another agent's `SPEC_KITTY_HOME` must not leak in;
  set it explicitly in the test, and set
  `XDG_CACHE_HOME="$PWD/.cache-agent"` for local runs if the shared pack cache
  makes output non-deterministic.

## Review Guidance

- Confirm the diff is `compat.py` + two test files and nothing else.
- Confirm the new integration test actually drives `upgrade`, not
  `uses_centralized_runtime` alone.
- Confirm it fails when the predicate is reverted (ask for the T004 evidence).
- Confirm no `skip`/`xfail`/`-k` deselection was added anywhere.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
