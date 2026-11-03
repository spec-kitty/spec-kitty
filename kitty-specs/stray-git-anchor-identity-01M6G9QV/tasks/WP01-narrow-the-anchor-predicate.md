---
work_package_id: WP01
title: Narrow the anchor predicate, red-first
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-003
planning_base_branch: issue-7084-stray-git-anchor-identity
merge_target_branch: issue-7084-stray-git-anchor-identity
branch_strategy: Planning artifacts for this mission were generated on issue-7084-stray-git-anchor-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7084-stray-git-anchor-identity unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Delivered fix
history:
- at: '2026-11-03T08:57:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/mission_metadata.py
- tests/specify_cli/upgrade/test_read_tracked_meta_6673.py
- tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Narrow the anchor predicate, red-first

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this
work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- You must address all feedback before your work is complete.
- Record what you changed per item with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

`backfill_mission` mints an identity for a mission whose folder git holds nothing for, even when an
ancestor carries a `.git` entry that is not a repository; every shape that can hide a real tracked
copy still refuses.

Done when:

- `uv run pytest tests/specify_cli/upgrade/test_read_tracked_meta_6673.py -q` is green.
- `uv run pytest tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py -q` is green.
- `uv run pytest tests/lanes/test_refinalize_mission_branch.py -q` is green **with no edit to that file**.
- The new tests were observed red before the predicate changed (T001–T003), and red again when the
  predicate narrowing alone is reverted (T006).
- `uv run ruff check` on the changed module and `uv run mypy src/specify_cli/mission_metadata.py` are clean.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#7084. Evidence and the full diagnosis live in
  `kitty-specs/stray-git-anchor-identity-01M6G9QV/research.md`; the design is in `plan.md` (IC-01).
- `specify_cli/mission_metadata.py` already owns "what does git hold for this `meta.json`"
  (`read_tracked_meta`), and it is the only place that may decide it (C-001, single canonical
  authority). Do not add a second copy of the rule in `backfill_identity.py` or in a test helper.
- `_meta_checkout_prefix` already asked git, and git already said `fatal: not a git repository`.
  The refusal is fabricated by the name-only ancestor scan, so the **predicate**, not the walk,
  is what changes (C-003: no new walk, in-flight PR #7082 owns ceiling-aware walking).
- Do not weaken the #6673 contract (C-002): a usable tracked copy is still taken back, and a corrupt,
  staged, index-only or unreadable copy still refuses with its coded notice.
- No full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Branch Strategy

- **Strategy**: `issue-7084-stray-git-anchor-identity` — a dedicated non-protected topic branch; the
  operator merges the pull request. Never push `main`.
- **Planning base branch**: `issue-7084-stray-git-anchor-identity`
- **Merge target branch**: `issue-7084-stray-git-anchor-identity`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red probe-level regression (probe contract)

- **Purpose**: pin the rule at the layer that decides it, with a positive control that the probe can
  still see a real anchor.
- **Steps**:
  1. Add a test to `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` that builds a temp
     root containing a bare directory named `.git` (holding only a `spec-kitty-locks/` child, the
     shape this host demonstrates) and a `kitty-specs/<slug>/` with no repository anywhere above it;
     assert `read_tracked_meta(mission_dir) == TrackedMeta(None, unavailable=False)`.
  2. On the same fixture family, assert the two anchor shapes still refuse: a `.git` **file**
     (`gitdir:` pointer to an unavailable path) and a `.git` **directory carrying `HEAD`** whose
     repository git cannot read. The file-pointer case already exists as
     `test_a_git_that_refuses_to_answer_is_not_read_as_nothing_tracked`; add the `HEAD`-directory
     case and keep both assertions green in every state.
  3. Confirm the new test fails on unmodified `main` with `unavailable=True`, i.e. for the mission's
     reason, not a fixture error.
- **Files**: `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`

### Subtask T002 – Red entry-point regression

- **Purpose**: prove the production entry point the issue reports, not only the helper.
- **Steps**:
  1. Add a test to `tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py`:
     a mission folder with an identity-less `meta.json` under a temp root carrying a bare `.git`
     directory; assert `action == "wrote"`, `mission_id is not None`, and that `meta.json` on disk now
     carries it; assert `reason is None`.
  2. Confirm it fails on unmodified `main` with `action == "skip"` and
     `"[TRACKED_META_UNAVAILABLE]"` in `reason`.
- **Files**: `tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py`

### Subtask T003 – Record the issue's own node red

- **Purpose**: keep the report honest about which call skips.
- **Steps**: run `uv run pytest tests/lanes/test_refinalize_mission_branch.py -q` on the unmodified
  module and record the failing line (`assert result.action == "wrote"` at the `backfill_mission`
  call, before `_finalize`). Do not edit that file.
- **Files**: none (evidence for the PR body and `traces/approach.md`).

### Subtask T004 – Narrow the predicate

- **Purpose**: the fix itself.
- **Steps**:
  1. Add a private helper, e.g. `_is_repository_home(git_entry: Path) -> bool`, that returns `True`
     when the entry is a file (gitdir/worktree pointer) or a directory that carries `HEAD`, and
     `True` on `OSError` (fail closed).
  2. Use it from `_has_no_git_anchor`: an ancestor is an anchor only when its `.git` entry exists
     *and* `_is_repository_home` says it could be a repository home.
  3. Update the docstrings of `_has_no_git_anchor` and `_meta_checkout_prefix` so the rule, its two
     keeping-refusals and the `HEAD` reasoning are stated where the code is.
  4. Keep the return type, the function name, the call sites and every error code unchanged.
- **Files**: `src/specify_cli/mission_metadata.py`

### Subtask T005 – Verify

- **Purpose**: evidence for review.
- **Steps**: run and record
  - `uv run pytest tests/specify_cli/upgrade/test_read_tracked_meta_6673.py tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py tests/lanes/test_refinalize_mission_branch.py -q`
  - `uv run ruff check src/specify_cli/mission_metadata.py tests/specify_cli/upgrade/test_read_tracked_meta_6673.py tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py`
  - `uv run mypy src/specify_cli/mission_metadata.py`
- **Files**: none.

### Subtask T006 – Half-fix proof

- **Purpose**: `acceptance-criteria-non-vacuity` — the coverage must depend on this change.
- **Steps**: temporarily restore the name-only predicate, confirm the new tests (T001, T002) and the
  issue's node go red, then restore the fix. Record the observed failures in the WP history.
- **Files**: none (throwaway edit, reverted).

## Review Guidance

- Check the refusal shapes one by one against the spec's FR-002 table: no shape that could hold a
  real copy may be minted over.
- Check the diff does not touch the walk, the ceilings, or any second copy of the anchor rule.
- Check `tests/lanes/test_refinalize_mission_branch.py` is byte-identical to `main`.

## Definition of Done

- [ ] T001–T006 complete; every listed command recorded with its result.
- [ ] The three result files are green; `tests/lanes/test_refinalize_mission_branch.py` unedited.
- [ ] ruff + mypy clean on the changed module.
- [ ] No new walk, no new git call, no error-code change.
