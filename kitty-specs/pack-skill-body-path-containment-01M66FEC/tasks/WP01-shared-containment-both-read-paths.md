---
work_package_id: WP01
title: Shared containment on both pack-skill read paths
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
planning_base_branch: issue-6734-pack-skill-body-path-containment
merge_target_branch: issue-6734-pack-skill-body-path-containment
branch_strategy: Planning artifacts for this mission were generated on issue-6734-pack-skill-body-path-containment. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6734-pack-skill-body-path-containment unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-skill-body-path-containment-01M66FEC
base_commit: cab1be39f6ba43ea99cb65f4d0df7db25414a52d
created_at: '2026-10-30T13:27:04.842573+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Implementation
history:
- at: '2026-10-30T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/pack_skills/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/pack_skills/validation.py
- src/charter/offering/pack_skills/repository.py
- tests/charter_offering/pack_skills/test_validation.py
- tests/charter_offering/pack_skills/test_repository.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared containment on both pack-skill read paths

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks; use language identifiers in code blocks.

## Objectives & Success Criteria

Both pack-skill `body_path` read paths judge containment through the ONE shared
primitive `charter.offering.drg.org_pack_config.resolve_relative_path_within_root`,
anchored at the declaring `*.skill.yaml` file's directory:

- `validate_pack_skill` (via `_read_body`) refuses an escaping `body_path`
  through the primitive (hand-rolled `resolve().is_relative_to(base)` deleted).
- `PackSkillRepository.body_text` refuses the same escapes fail-closed
  (raising `PackSkillViolation`) BEFORE reading, so a post-load symlink swap or
  an injected escaping record can never read outside the skill directory.
- Tests prove absolute, `..`, and symlink escapes are refused **identically on
  both paths**, plus a positive control (a contained body still loads and
  reads), and the "not found" finding stays separate from the escape refusal.

Success: the new tests fail on pristine `main` (red-first, repository path) and
pass on the branch; `grep -rn "is_relative_to" src/charter/offering/pack_skills/`
returns nothing; `tests/charter_offering/pack_skills/` is green.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6734 (follow-up from #6418 campsite cleanup).
- Spec: `kitty-specs/pack-skill-body-path-containment-01M66FEC/spec.md`
  (FR-001, FR-002, FR-003, NFR-001..003, C-001, C-002).
- Plan: `kitty-specs/pack-skill-body-path-containment-01M66FEC/plan.md`
  (IC-01..IC-03); grounding evidence in `research.md`.
- The anchor is the SKILL FILE'S DIRECTORY (`skill_file.parent` /
  `source.parent`) — never the pack root (that is the org-DRG contract).
- Refusal surface: `PackSkillViolation` (a `ValueError`), message continuous
  with today's wording ("escapes the skill directory") plus the primitive's
  reason. Load-time skip-and-warn behaviour is unchanged.
- The primitive is stricter than the hand-roll at one edge: a string-level
  `..` that resolves back inside (`sub/../body.md`) becomes refused. This is
  deliberate (single authority); the changelog entry (WP02) records it.
- `body_text`'s `None` return stays reserved for a non-prompt-form skill or an
  unknown id — an escape is a raise, not a `None`.
- Follow CLAUDE.md/AGENTS.md code rules: `ruff` + `mypy` clean, no new
  suppressions, tests for every new branch.

## Branch Strategy

- **Strategy**: coord topology, planning on `issue-6734-pack-skill-body-path-containment`
- **Planning base branch**: `issue-6734-pack-skill-body-path-containment`
- **Merge target branch**: `issue-6734-pack-skill-body-path-containment`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first repository-path escape tests

- **Purpose**: Prove the read-time hole before fixing it (DIRECTIVE_034).
- **Steps**: In `tests/charter_offering/pack_skills/test_repository.py`, using
  the existing `skill_dirs` fixture and `prompt_skill`/`write_skill` builders:
  1. Symlink-swap case (public entry point): write a prompt skill whose
     `body_path` is a symlink inside the skill directory; load the repository
     (validation passes); repoint the symlink at a file OUTSIDE the skill
     directory (e.g. `tmp_path / "outside.md"`); assert
     `repo.body_text(<id>)` raises `PackSkillViolation` (match "escapes").
  2. Injected-record cases for `absolute` and `..` `body_path` (load-time
     validation skips such files, so the catalog cannot hold them any other
     way): put a `PackSkill` record with the escaping `body_path` into
     `repo._items` / `repo._sources` directly, with a one-line comment saying
     why; assert the same `PackSkillViolation`.
  3. Positive control: a plain contained (optionally nested, e.g.
     `nested/body.md`) body still reads unchanged.
- **Files**: `tests/charter_offering/pack_skills/test_repository.py`
- **Parallel?**: Yes (with T002).
- **Notes**: Run against pristine `main` first (e.g. `git stash` the source
  edits or run before implementing T003–T005) and record the red output in the
  WP history note. Symlink tests: guard nothing special — the suite runs on
  POSIX CI; keep `pytest.mark.unit, fast` markers used by the file.

### Subtask T002 – Red-first validation-path escape tests

- **Purpose**: Pin the validation path's refusal for every escape kind, so
  both paths are provably identical.
- **Steps**: In `tests/charter_offering/pack_skills/test_validation.py`:
  1. Absolute `body_path` (POSIX; optionally a `C:\\x` Windows-form string
     case) → `PackSkillViolation` (match "escapes").
  2. Symlink escape: `body_path` names a symlink pointing outside the skill
     directory → refused (match "escapes").
  3. Keep/extend the existing `..` test (it exists already).
  4. Pin the distinction: a contained `body_path` whose file is missing raises
     the "not found" violation, never the escape violation.
- **Files**: `tests/charter_offering/pack_skills/test_validation.py`
- **Parallel?**: Yes (with T001).
- **Notes**: The existing `test_body_path_escaping_directory_refused` covers
  `..`; do not duplicate — extend.

### Subtask T003 – Shared body-path helper on the primitive

- **Purpose**: One containment decision point for the package.
- **Steps**: In `src/charter/offering/pack_skills/validation.py`, add a module
  function (e.g. `resolve_body_path(skill, skill_file) -> Path`) that:
  - calls `resolve_relative_path_within_root(skill_file.parent, skill.body_path)`,
  - catches `OrgPackSubdirEscapeError` (and the primitive's `ValueError`/
    `OSError` family) and raises `PackSkillViolation` with a message like
    `skill {id!r}: body_path {body_path!r} escapes the skill directory (<reason>)`,
  - is exported from the module's `__all__` for the repository to import.
- **Files**: `src/charter/offering/pack_skills/validation.py`
- **Parallel?**: No.
- **Notes**: Docstring must name the primitive as the single containment
  authority and the skill-directory anchor.

### Subtask T004 – Rewire `_read_body`

- **Purpose**: Delete the hand-rolled containment.
- **Steps**: `_read_body` calls the T003 helper, then checks `is_file()` for
  the existing "not found" violation, then reads. The hand-rolled
  `resolve().is_relative_to(base)` block is gone.
- **Files**: `src/charter/offering/pack_skills/validation.py`
- **Parallel?**: No.

### Subtask T005 – Rewire `body_text`

- **Purpose**: Fail-closed read path.
- **Steps**: In `PackSkillRepository.body_text`, before reading, resolve the
  body through the T003 helper (anchored at `source.parent`); keep returning
  `None` for missing skill/source/empty `body_path`. Update the method's
  docstring to state the containment rule and the raise.
- **Files**: `src/charter/offering/pack_skills/repository.py`
- **Parallel?**: No.
- **Notes**: `skill_preparation.py::_prepare_one` is the only caller; the
  raise is intended (fail-closed). Verify no existing test in
  `tests/charter/` depends on the old leaky behaviour (run
  `tests/charter_offering/pack_skills/` and grep for `body_text` callers).

### Subtask T006 – Run the owning test surface and the baseline

- **Purpose**: Evidence for the PR's Tests-run section.
- **Steps** (from the repo root, NO full/heavy suites):
  - `uv run --frozen pytest tests/charter_offering/pack_skills/ -q`
  - `uv run --frozen pytest tests/charter_offering/ tests/charter/ -q -m "fast or unit"` (owning subsystem fast tier)
  - `make test-fast`
  - `uv run --frozen ruff check src/charter/offering/pack_skills/ tests/charter_offering/pack_skills/`
  - `uv run --frozen ruff format --check --force-exclude <changed files>`
  - `uv run --frozen mypy src/charter/offering/pack_skills/` (project invocation; match CI)
- **Files**: none (verification only).
- **Parallel?**: No.
- **Notes**: Record exact commands + pass/fail counts with
  `spec-kitty agent tasks add-history WP01 --note "..."`. A failure that is
  red on `main` too is not yours — classify per the baseline-red gotcha and
  report it.

## Test Strategy

- Tests live in `tests/charter_offering/pack_skills/` (unit/fast markers, as
  the file headers declare).
- Red-first proof: T001's repository-path tests must be shown failing on
  pristine `main` before the fix lands (recorded in the WP history).
- Every new branch (helper's escape raise, `body_text` refusal, "not found"
  vs "escape") is executed directly by a test (diff-cover ≥90%).

## Risks & Mitigations

- Stricter `..` edge (`sub/../body.md` now refused) → dedicated test +
  changelog entry (WP02).
- Symlink behaviour is POSIX-only in tests → acceptable (CI is Linux; the
  primitive itself already handles Windows path forms).
- Injected-record tests touch repository internals → justified in a one-line
  comment (no public route can hold an escaping record — that is the point of
  defense-in-depth).

## Review Guidance

- Confirm the red-first evidence (repository-path tests failing on `main`).
- Confirm NO new containment logic: the helper only translates the primitive's
  error; both callers import it from one place.
- Confirm the anchor is the skill file's directory on both paths.
- Confirm `pack_skills/` has no `is_relative_to` containment left.

## Progress & Status

Progress, history, and status live in the status event log
(`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
