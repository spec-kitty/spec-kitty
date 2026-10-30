---
work_package_id: WP01
title: Doctor read surfaces route through the Mission predicate
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-007
- FR-009
- NFR-001
- SC-001
- SC-002
planning_base_branch: issue-6758-kitty-specs-walkers-mission-predicate
merge_target_branch: issue-6758-kitty-specs-walkers-mission-predicate
branch_strategy: Planning artifacts for this mission were generated on issue-6758-kitty-specs-walkers-mission-predicate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6758-kitty-specs-walkers-mission-predicate unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Doctor read surfaces
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/_support/mission_residue_fixture.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_identity_audit.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- src/specify_cli/cli/commands/_review_cycle_reconcile_doctor.py
- tests/_support/mission_residue_fixture.py
- tests/specify_cli/cli/commands/test_identity_audit.py
- tests/specify_cli/cli/commands/test_coordination_doctor.py
- tests/specify_cli/cli/commands/test_review_cycle_reconcile_doctor.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Doctor read surfaces route through the Mission predicate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## Objectives & Success Criteria

Three `doctor` read surfaces stop deciding "is this a Mission?" for themselves and ask
`specify_cli.context.mission_resolver.is_selectable_mission_dir` instead:

1. `_collect_topology_rows` (`doctor topology`, `src/specify_cli/cli/commands/_identity_audit.py`)
2. `_resolve_mission_dirs` (`doctor coordination`, `src/specify_cli/cli/commands/_coordination_doctor.py`)
3. `_mission_dirs_for` (`doctor review-cycle-reconcile`, `src/specify_cli/cli/commands/_review_cycle_reconcile_doctor.py`)

Done means: on the shared fixture (one Mission + one residue child in a git repository) each
walk returns the Mission and not the residue child; every existing test in the three owning
test files still passes; and the new tests were seen to fail before the walkers changed.

## Context & Constraints

- Mission spec: `kitty-specs/route-kitty-specs-walkers-through-the-mission-predicate-01M66YN5/spec.md` (FR-001, FR-002, FR-003, FR-007, FR-009).
- Plan: `.../plan.md` (IC-01, "Per-walker change and proof"); data model: `.../data-model.md`.
- The predicate already exists on `main`: `is_selectable_mission_dir(path, *, repo_root, tracked=...)`
  plus the per-walk memo `TrackedMissionPaths(repo_root)`. Read
  `src/specify_cli/context/mission_resolver.py` (around `is_selectable_mission_dir`) and copy the
  pattern #5875 used in `src/specify_cli/cli/commands/_mission_type_audit.py` (`audit_mission_types`):
  `tracked = TrackedMissionPaths(repo_root)` once per walk, passed as `tracked=` per child.
- **Do not** swap these walks onto `FsMissionResolver` / `all_missions()`: the resolver index needs a
  `mission_id` and would hide legacy id-less Missions that selection lists.
- **Do not** touch `src/specify_cli/audit/engine.py` (C-001, #6757 owns it) or the predicate's own rules (C-002).
- Keep each walker's enumeration posture (C-003):
  - `_collect_topology_rows` may use the sanctioned shared walk
    `mission_resolver.iter_kitty_specs_children(repo_root)` (fail-soft, `safe_is_dir`, sorted) — the
    same walk its `doctor identity` sibling already uses.
  - `_resolve_mission_dirs` must keep `safe_is_dir` evaluated **before** the predicate, so an
    unstattable child still raises (`#3194`).
  - `_mission_dirs_for` keeps its `Path.is_dir()` comprehension and just filters it.
- Term: "read-side residue" (a folder Mission selection never lists). Never write bare "residue"
  where the sense matters.

## Branch Strategy

- **Strategy**: feature branch, planning and implementation on the mission branch (single-branch topology).
- **Planning base branch**: `issue-6758-kitty-specs-walkers-mission-predicate`
- **Merge target branch**: `issue-6758-kitty-specs-walkers-mission-predicate`

Implementation commits land on this branch; the operator merges the PR into `main`. Never push `main`.

## Subtasks & Detailed Guidance

### Subtask T001 – Shared git-aware Mission + residue fixture

- **Purpose**: one fixture, reused by all six walker tests (WP01 and WP02), so the positive control and
  the absence assertion cannot drift.
- **Files**: create `tests/_support/mission_residue_fixture.py`.
- **Steps**:
  1. Reuse `tests/_support/activation_cli.py::init_git_repo` and `git` (real subprocesses) and
     `tests/_support/status_seed.py::seed_status_event` with `specify_cli.status.models.StatusEvent`.
  2. Expose `MISSION_SLUG = "001-real-mission"`, `RESIDUE_SLUG = "leftover-spec-only"`, a frozen
     dataclass `ResidueFixture(repo_root, mission_dir, residue_dir, tracked_paths)` and
     `seed_mission_and_residue(repo_root: Path) -> ResidueFixture`.
  3. Build the **Mission**: `kitty-specs/001-real-mission/` with `meta.json`
     (`mission_id` ULID-shaped string, `mission_slug`, `friendly_name`, `created_at`, `topology: "single_branch"`),
     `spec.md`, `tasks/WP01-real.md` (frontmatter `work_package_id: WP01`, `status: done`), and one
     in-flight status event for `WP02` (`planned -> in_progress`).
  4. Build the **residue** child identically **but with no `meta.json`**: `spec.md`,
     `tasks/WP01-leftover.md` (`status: done`), and the same in-flight `WP02` event. This is read-side
     residue (no `meta.json`), and it is git-tracked, so the git-aware rule applies.
  5. `git add -A` and commit both children so nothing is left untracked.
  6. Docstring: state that both children sit on one fixture and why (positive control for the absence
     assertion).
- **Validation**: `python -c` smoke check or the first test that uses it; the Mission must satisfy
  `is_selectable_mission_dir` and the residue child must not, in a throwaway assertion you keep in T002.

### Subtask T002 – Red-first tests for the three doctor walkers

- **Purpose**: pin each walker's behaviour before changing it.
- **Files**: `tests/specify_cli/cli/commands/test_identity_audit.py`,
  `test_coordination_doctor.py`, `test_review_cycle_reconcile_doctor.py`.
- **Steps**: add one test each (names below), each using the shared fixture and asserting
  `{row["slug"] ...} == {MISSION_SLUG}` / `[p.name ...] == [MISSION_SLUG]`, plus one assertion that the
  Mission itself is present (the positive control):
  - `test_collect_topology_rows_skips_residue` — assert no row for `RESIDUE_SLUG` and no row carrying
    `error == "meta.json not found"`.
  - `test_resolve_mission_dirs_skips_residue`.
  - `test_mission_dirs_for_skips_residue`.
- **Run them now, against the unchanged walkers, and record the failing ids** for the PR's `## Tests run`
  section. Do not weaken the assertions to make them pass.
- Add one probe-cost assertion (NFR-001) in `test_collect_topology_rows_skips_residue`: monkeypatch
  `specify_cli.context.mission_resolver.tracked_mission_paths` (or `kernel.git.tracked_paths`, whichever
  the memo calls) with a counter, run the walk twice — once with a fixture whose children all carry a
  `mission_id` (expect 0 calls) and once with the shared fixture (expect exactly 1) — so the memo's
  "at most one probe per walk" promise is pinned rather than assumed.
- **Notes**: keep the existing `test_collect_topology_rows_all` etc. untouched — they are the non-git
  positive control that proves the filter does not hide real Missions.

### Subtask T003 – `doctor topology` walks Missions only

- **Purpose**: stop rendering residue as a Mission with `meta.json not found`.
- **Files**: `src/specify_cli/cli/commands/_identity_audit.py`.
- **Steps**:
  1. In `_collect_topology_rows`, replace the whole-repo branch's raw `specs_dir.iterdir()` with
     `iter_kitty_specs_children(repo_root)` and keep only children where
     `is_selectable_mission_dir(entry, repo_root=repo_root, tracked=tracked)` with one
     `TrackedMissionPaths(repo_root)` built before the comprehension.
  2. Import them lazily inside the function (the module already imports `status` lazily elsewhere) or at
     module top if that introduces no cycle — check `_identity_audit`'s existing import block and prefer
     the smallest correct choice; `status` must not gain a module-level edge into `context`.
  3. Leave the `--mission` branch (placement seam `PRIMARY_METADATA`) untouched and update the docstring
     to say residue folders are not rows (one sentence; `doctor identity` remains the residue reporter).
- **Validation**: `test_collect_topology_rows_skips_residue` and `test_collect_topology_rows_all` pass.

### Subtask T004 – `doctor coordination` scan walks Missions only

- **Purpose**: no coordination findings for a folder that is not a Mission.
- **Files**: `src/specify_cli/cli/commands/_coordination_doctor.py`.
- **Steps**: in `_resolve_mission_dirs`, keep the `safe_is_dir(mission_dir)` guard **first** and add
  `is_selectable_mission_dir(mission_dir, repo_root=repo_root, tracked=tracked)` with one memo per call;
  keep the `mission_filter` branch untouched; extend the docstring by one sentence.
- **Validation**: `test_resolve_mission_dirs_skips_residue` plus the existing unstattable-child tests.

### Subtask T005 – `doctor review-cycle-reconcile` scan walks Missions only

- **Purpose**: reports name Missions only.
- **Files**: `src/specify_cli/cli/commands/_review_cycle_reconcile_doctor.py`.
- **Steps**: filter the `sorted(specs_dir.iterdir())` comprehension in `_mission_dirs_for` through the
  predicate with one memo per call; keep the `mission` branch untouched; one docstring sentence.
- **Validation**: `test_mission_dirs_for_skips_residue` plus the file's existing tests (including
  `tests/specify_cli/cli/commands/test_bare_modern_slug_ambiguity_cli.py`, which imports
  `_mission_dirs_for`).

### Subtask T006 – Red-first proof and doctor blast radius

- **Steps**:
  1. Confirm each T002 test failed before its walker change (re-run by temporarily reverting the walker
     hunk, or keep the recorded failing output from T002).
  2. Run: `uv run pytest tests/specify_cli/cli/commands/test_identity_audit.py
     tests/specify_cli/cli/commands/test_coordination_doctor.py
     tests/specify_cli/cli/commands/test_review_cycle_reconcile_doctor.py
     tests/specify_cli/cli/commands/test_doctor_coordination.py
     tests/specify_cli/cli/commands/test_bare_modern_slug_ambiguity_cli.py -q`
  3. Run `uv run pytest tests/specify_cli/cli/commands -q -x` if the above is green and time allows.
  4. `uv run ruff check` and `uv run ruff format --check` on the three source files and three test files.
- **Record** exact commands and passed/failed counts for the PR body.

## Test Strategy

- Red first, then green, per walker; never adjust an assertion to accommodate a walker-local rule.
- Every new test asserts both the absence of the residue child **and** the presence of the Mission on the
  same fixture (acceptance-criteria-non-vacuity).
- Git must be real (`init_git_repo`), because file-presence mode would classify both children as Missions.

## Risks & Mitigations

- **Weakening `#3194`**: `safe_is_dir` must run before the predicate in `_resolve_mission_dirs`; the
  existing unstattable-child tests are the guard.
- **Hidden legacy Missions**: do not route through the resolver index (needs `mission_id`).
- **Fixture pollution**: build everything under `tmp_path`; never touch the repository's own `kitty-specs/`.

## Review Guidance

- Verify each walker's docstring names the read-side predicate and that no walker keeps a second rule.
- Confirm the residue child in the fixture genuinely has no `meta.json` and is committed.
- Confirm no `audit/engine.py` change and no predicate-semantics change.
