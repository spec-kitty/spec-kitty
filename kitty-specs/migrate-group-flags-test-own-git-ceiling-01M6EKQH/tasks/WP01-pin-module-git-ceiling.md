---
work_package_id: WP01
title: Pin the module's own git-discovery ceiling
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
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Isolation
history:
- at: '2026-11-02T17:12:00+00:00'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/cli/
create_intent:
- docs/changelog/unreleased/
execution_mode: code_change
model: ''
owned_files:
- tests/cli/test_migrate_group_flags_4964.py
- docs/changelog/unreleased/
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Pin the module's own git-discovery ceiling

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile does not resolve, run `spec-kitty agent profile list` and select the best match for a
`code_change` WP whose authoritative surface is `tests/cli/`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?** Check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."` as you go.

---

## Objectives & Success Criteria

Deliver the test-only fix for spec-kitty/spec-kitty#6957:

1. `tests/cli/test_migrate_group_flags_4964.py`'s autouse isolation fixture pins the module's own
   git-discovery ceiling at the test root, appended to whatever the harness installed.
2. Two red-first guards pin the property: one host-independent standing invariant, one behavioural
   probe through the real CLI entry point.
3. The 76 pre-existing tests keep their assertions, unchanged.
4. `uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q` is green, including with
   `GIT_CEILING_DIRECTORIES` cleared on a host whose temp root is inside a repository.

Success criteria: SC-001, SC-002, SC-003, SC-004. Requirements: FR-001 … FR-005, NFR-001 … NFR-003,
C-001 … C-003.

## Context & Constraints

Read first (repo-root-relative):

- `kitty-specs/migrate-group-flags-test-own-git-ceiling-01M6EKQH/spec.md` — requirements and edge cases.
- `kitty-specs/migrate-group-flags-test-own-git-ceiling-01M6EKQH/plan.md` — the design (sections 1–4).
- `kitty-specs/migrate-group-flags-test-own-git-ceiling-01M6EKQH/research.md` — grounding evidence,
  including the verbatim error string this mission removes.
- `src/specify_cli/core/paths.py::git_ceiling_dirs` and `resolve_canonical_root` (read only).
- `tests/_support/git_ceiling.py` (read only) — the harness ceiling contract and the rule that "such a
  test sets the variable itself".
- `tests/specify_cli/migration/test_runtime_state_cutover_placement.py:41` — the sibling module's
  idiom this WP follows.

Hard constraints:

- **C-001**: do not change any file under `src/`, `packs/`, `tests/conftest.py` or
  `tests/_support/`. The fail-close under test is correct; the harness ceiling is correct.
- **C-002**: do not delete, skip, xfail or loosen any existing assertion in the module.
- **C-003**: use the repository's existing ceiling idiom (`GIT_CEILING_DIRECTORIES` +
  `monkeypatch.setenv`), not a bespoke mechanism.
- **NFR-003**: the code diff is confined to `tests/cli/test_migrate_group_flags_4964.py` plus one
  `docs/changelog/unreleased/*.internal.md` fragment. The mission's own `kitty-specs/<mission>/`
  artifacts and the tool-written `kitty-ops/` op records are bookkeeping, not code.

## Branch Strategy

- **Strategy**: single_branch — planning and implementation land on the mission branch
- **Planning base branch**: `kitty/mission-migrate-group-flags-test-own-git-ceiling-01M6EKQH`
- **Merge target branch**: `main` (after consolidation; the operator merges the PR)

> Finalized by `spec-kitty agent mission finalize-tasks`; do not hand-edit.

## Subtasks & Detailed Guidance

### Subtask T001 – Add the two non-vacuity guards (RED first)

- **Purpose**: Prove the defect before curing it (ATDD-first, C-011; DIRECTIVE_034).
- **Steps**:
  1. Add a module-level helper `_append_ceiling(existing: str, entry: Path) -> str` that keeps the
     existing value verbatim and appends `str(entry)` only when it is not already listed.
  2. Add **Guard A** (host-independent standing invariant):
     `test_module_pins_git_discovery_to_its_own_test_root(tmp_path)` asserting
     `tmp_path.resolve() in git_ceiling_dirs()` (import `git_ceiling_dirs` from
     `specify_cli.core.paths`). If the helper's signature would make Guard A green before the fixture
     change, keep Guard A independent of it — it must assert the fixture's effect, not the helper.
  3. Add **Guard B** (behavioural probe through the production entry point):
     `test_positive_control_survives_a_temp_root_inside_a_repository(tmp_path, monkeypatch)` which
     captures the value the autouse fixture installed, clears `GIT_CEILING_DIRECTORIES`, proves the
     unpinned walk escapes (`resolve_canonical_root(feature_dir)`); skips with a reason when the host
     shape is absent or the enclosing repository is inside the test root; asserts the fixture really
     installed this test's root as a ceiling (so removing the fixture wiring reds this test too); then
     puts **only that fixture-installed entry** back, asserts the walk now raises
     `WorkspaceRootNotFound`, builds the fixture mission (`build_mission(tmp_path)`), invokes the real
     seam (`_invoke(["backfill-runtime-state", "--json"])` with `_LOCATE` patched to `tmp_path`), and
     asserts `exit_code == 0` and `summary.flipped == 1`.
  4. Add Guard A's **positive control** (FR-005): on the same fixture, create a repository *inside*
     `tmp_path` — `nested = tmp_path / "nested"; (nested / ".git").mkdir(parents=True)` and
     `mission = nested / "kitty-specs" / "042-demo"` (mkdir it) — then assert
     `resolve_canonical_root(mission) == nested.resolve()`. A repository below the ceiling stays
     discoverable, so the ceiling does not break fixtures that root their own project inside
     `tmp_path`. Keep it in Guard A so the negative (cannot climb above) and the positive (still finds
     what is below) assertions share one fixture and cannot drift apart.
  5. Keep the module docstring's isolation section truthful: state that the root walk is pinned too.
- **Files**: `tests/cli/test_migrate_group_flags_4964.py`
- **Parallel?**: No.
- **Notes**: The module's existing `pytestmark = [pytest.mark.integration]` applies to the new tests.

### Subtask T002 – Witness the red

- **Purpose**: Evidence, not assertion — the guards must be observed failing for the right reason.
- **Steps**:
  1. `uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q -k "pins_git_discovery"` →
     must FAIL (test root not listed as a ceiling).
  2. Reproduce the issue's red: clear the ambient value in a throwaway probe (not committed) and run
     the positive control → the `_flip_phase refuses … /tmp/kitty-specs/042-demo` error string.
  3. Paste both outputs into the commit message body or the PR's *Tests run* section.
- **Files**: none (evidence only).
- **Parallel?**: No.

### Subtask T003 – Implement the ceiling append (GREEN)

- **Purpose**: The fix.
- **Steps**:
  1. In `_hard_repo_isolation`, after the `_LOCATE` poison, append the test root:
     `monkeypatch.setenv("GIT_CEILING_DIRECTORIES", _append_ceiling(os.environ.get("GIT_CEILING_DIRECTORIES", ""), resolved_tmp))`
  2. Add a short comment naming the mechanism: the root walk (`core.paths.resolve_canonical_root`)
     that `runtime_state_cutover._resolve_primary_home_or_degrade` uses is not patched above, so it is
     bounded here (#6957, #7022).
  3. Re-run the module: everything green, Guard A and Guard B included.
- **Files**: `tests/cli/test_migrate_group_flags_4964.py`
- **Parallel?**: No.
- **Notes**: Append-only; `monkeypatch` restores the previous value at teardown (NFR-002). Do not
  replace the harness value — a leading empty entry is meaningful to git.

### Subtask T004 – Prove non-vacuity both ways

- **Purpose**: A gate that cannot fail is not a gate (DIRECTIVE_043).
- **Steps**:
  1. Temporarily revert only the fixture append (keep both guards) → Guard A must go red on this host;
     Guard B must go red too (on a host whose temp root is inside a repository).
  2. Restore the append → module green.
  3. Confirm the 76 pre-existing tests are byte-identical in their assertions:
     `git diff origin/main -- tests/cli/test_migrate_group_flags_4964.py` shows additions and the one
     fixture line change only.
  4. Run the sibling placement test tree for the blast radius:
     `uv run --frozen pytest tests/specify_cli/migration/test_runtime_state_cutover_placement.py -q`
     and record the count.
- **Files**: `tests/cli/test_migrate_group_flags_4964.py` (temporary revert, restored).
- **Parallel?**: No.

### Subtask T005 – Changelog fragment and evidence

- **Purpose**: The repository assembles its changelog from per-PR fragments (#6988).
- **Steps**:
  1. Read `docs/changelog/unreleased/README.md` for the required shape, then add
     `docs/changelog/unreleased/<pr>.internal.md` (test-only change → `internal`, not user-facing).
     Use the PR number once the PR exists; before that a placeholder is fine but must be renamed
     before the PR is flipped.
  2. Record tooling friction in the mission tracers:
     `spec-kitty agent tracer-append --mission migrate-group-flags-test-own-git-ceiling-01M6EKQH --category tooling-friction --entry "<what was slow or surprising>"`.
- **Files**: `docs/changelog/unreleased/<pr>.internal.md`
- **Parallel?**: No (needs the PR number).

## Test Strategy

Run, and record exact commands with counts:

```bash
uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q
uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q -k "pins_git_discovery or survives_a_temp_root"
uv run --frozen pytest tests/specify_cli/migration/test_runtime_state_cutover_placement.py -q
```

No whole-repo suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Ruff on the changed file is part of the lint
gate; `tests/cli/test_migrate_group_flags_4964.py` carries type annotations on every new helper.

## Risks & Mitigations

- **Guard B skipped on CI** → Guard A is the always-on gate; B's skip names the missing host shape.
- **Shared env leakage** → `monkeypatch` teardown; append-only value handling.
- **Fixture inside `tmp_path` needing an enclosing repo above it** → not a supported shape for this
  module (hard isolation rule already forbids the real checkout); the ceiling makes the rule explicit.

## Review Guidance

- The reviewer must confirm: no `src/`/`packs/`/conftest change; no weakened assertion; Guard A red
  without the fixture append; Guard B red (or explicitly skipped) without it and green with it.
- Confirm the append preserves an existing `GIT_CEILING_DIRECTORIES` value verbatim and is idempotent.
- Confirm the new tests run through the real CLI seam, not a helper.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never in this
prompt file.

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`
