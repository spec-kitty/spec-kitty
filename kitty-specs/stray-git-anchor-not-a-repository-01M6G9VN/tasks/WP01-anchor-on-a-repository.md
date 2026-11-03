---
work_package_id: WP01
title: Anchor on a repository, not a .git name
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
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-7093-stray-git-anchor-not-a-repository
merge_target_branch: issue-7093-stray-git-anchor-not-a-repository
branch_strategy: Planning artifacts for this mission were generated on issue-7093-stray-git-anchor-not-a-repository. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7093-stray-git-anchor-not-a-repository unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Fix
history:
- at: '2026-11-03T08:58:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/mission_metadata.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/mission_metadata.py
- tests/specify_cli/upgrade/test_read_tracked_meta_6673.py
- tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Anchor on a repository, not a `.git` name

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

`specify_cli.mission_metadata.read_tracked_meta` is the ONE answer to "what does git hold
for this Mission's `meta.json`". It answers one of three things: the tracked copy, "nothing
is tracked for this path", or the refusal `TrackedMeta(None, unavailable=True)` — which
means *git knows the path but cannot give its content back*, so no seam may mint an
identity over it.

`_has_no_git_anchor` decides which of the last two applies when git exits non-zero. It
currently treats *any* `.git` entry at or above the folder as an anchor. A `.git`
*directory* that holds no `HEAD` is not a repository — git itself answers
`fatal: not a git repository` for every path below it — so a project under such a
directory is reported as "a repository exists and git refuses", which is false:
nothing is tracked there and no history can be orphaned.

Reported symptom (#7093):
`tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py::test_apply_repairs_feature_state_and_legacy_prompt_refs`
is red on pristine `origin/main` on this host: the frozen sweep reports
`Wrote baseline meta.json` and no file appears. `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py::test_nothing_tracked_is_not_a_refusal`
is red for the same reason.

Done when: an anchor is a `.git` pointer *file* or a `.git` *directory that holds `HEAD`*;
a folder outside any work tree reads as "nothing tracked" again; every existing refusal is
unchanged; and both pre-existing red tests pass with their assertions byte-identical to
`origin/main`.

## Context & Constraints

- Spec: [spec.md](../spec.md) · Plan: [plan.md](../plan.md). Read both before editing.
- `src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py` is a **byte-frozen
  shipped migration** (DIRECTIVE_044: its bytes are its `content_hash`; it is superseded
  through `SUPERSEDED_MIGRATIONS`). Do **not** edit any file under
  `src/specify_cli/upgrade/migrations/`. The fix belongs in the shared seam the migration
  calls.
- Do **not** change any existing assertion in the two test modules, and do not add
  `xfail`/`skip`. The reported test must pass because the subject changed.
- Machine fact for reproduction: this host has `/tmp/.git`, a directory with `hooks/` and
  no `HEAD` (the shape the literal-`.git/hooks` writer of #5756 leaves behind), which is
  why the pre-existing tests are red only here. Your new tests must build that shape
  themselves so they are environment-independent.
- `read_tracked_meta` must not gain a git subprocess: the anchor decision is a filesystem
  check (NFR-001).
- Terminology: Mission, `.git` anchor, tracked `meta.json`, refusal, baseline meta.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `issue-7093-stray-git-anchor-not-a-repository`. Completed changes must merge back into that branch.
- **Planning base branch**: `issue-7093-stray-git-anchor-not-a-repository`
- **Merge target branch**: `issue-7093-stray-git-anchor-not-a-repository`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first unit test: a stray non-repository `.git` is not an anchor

- **Purpose**: Pin the contract at the seam that is wrong, environment-independently.
- **Steps**: In `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` add one test
  (name it for the behaviour, e.g.
  `test_a_git_directory_that_is_not_a_repository_is_not_an_anchor`). Build the tree under
  `tmp_path`: `tmp_path / "ancestor" / ".git" / "hooks"` (a directory named `.git` with no
  `HEAD`), then a project below it with `kitty-specs/<slug>/` holding `tasks.md` (so the
  folder is not residue). Assert `read_tracked_meta(mission_dir) == TrackedMeta(None,
  unavailable=False)`. Then, on the **same fixture**, remove the stray directory, write
  `ancestor/.git` as a pointer file (`"gitdir: /nonexistent/gitdir\n"`) and assert the
  same call returns `unavailable=True` — the positive control that proves the probe can
  still see a refusal. Assert `build_baseline_feature_meta(mission_dir, project)` returns
  a payload (not `None`) in the first shape.
- **Files**: `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`
- **Parallel?**: no (T002 reproduces the same shape end to end).
- **Notes**: Run it before the fix and record the red output in the PR's Tests run section.
  The module's `pytestmark` already marks it `unit` + `git_repo`; keep the module's existing
  helpers (`_repo`, `_git`) if useful, but the new test must not need git at all.

### Subtask T002 – Red-first integration test: the frozen sweep leaves `meta.json` behind

- **Purpose**: Make the reported symptom reproducible on any host, including CI where no
  stray `.git` exists above the temp root.
- **Steps**: In `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py` add one test
  modelled on `test_apply_repairs_feature_state_and_legacy_prompt_refs`: build
  `project/.git/hooks/` (a non-repository `.git` above the project), a Mission folder
  under `project/kitty-specs/001-upgrade-sweep/` with `tasks/`, `tasks.md`, `status.json`
  and no `meta.json`; monkeypatch `resolve_primary_branch` and `_migrate_runtime_assets`
  exactly as the existing test does; apply the migration and assert
  `(feature_dir / "meta.json").is_file()` and its `target_branch` / `mission_type`.
- **Files**: `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py`
- **Parallel?**: no.
- **Notes**: Leave `test_apply_repairs_feature_state_and_legacy_prompt_refs` untouched —
  it is the reported red and must not be edited.

### Subtask T003 – Fix the anchor test and its docstrings

- **Purpose**: The production change. One helper, no new walk, no signature change.
- **Steps**: In `src/specify_cli/mission_metadata.py`, rewrite `_has_no_git_anchor` so it
  walks `(feature_dir, *feature_dir.parents)` and returns `True` only when **no** anchor is
  found. At each candidate, `os.lstat` the `.git` entry:
  - missing (`FileNotFoundError`) → keep walking;
  - any other `OSError` → an anchor (fail closed; return `False`);
  - a directory → it is an anchor **only if** `HEAD` exists inside it; `FileNotFoundError`
    on `HEAD` means "not a repository", so keep walking; any other `OSError` means we
    cannot tell, so treat it as an anchor (fail closed);
  - a file or symlink → an anchor (a worktree/submodule/separate-git-dir pointer is a
    repository the caller may not be able to read).
  Update the docstring to say an anchor is a repository, not a name, cite #7093, and note
  that the first anchor wins so a non-repository `.git` never shields a real repository
  above it. Adjust `read_tracked_meta`'s Returns docstring only if the wording now needs
  it ("a folder outside any work tree" already states the contract).
- **Files**: `src/specify_cli/mission_metadata.py`
- **Parallel?**: no.
- **Notes**: Keep the imports honest — `os` and `stat` must be used, and import order must
  satisfy ruff. Do not add a second repository detector in a caller (C-003).

### Subtask T004 – Verify both environment directions and the standing refusals

- **Purpose**: Prove the fix is neither environment-specific nor a weakening.
- **Steps**: Run, and record the outputs:
  1. `uv run pytest tests/specify_cli/upgrade/test_read_tracked_meta_6673.py tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py -q -p no:randomly`
  2. the same two modules with `--basetemp=<a dir outside /tmp>` (both must pass — the
     reported red is red only under a stray ancestor `.git`, and the new tests must hold in
     both shapes).
  3. `uv run ruff check src/specify_cli/mission_metadata.py tests/specify_cli/upgrade/test_read_tracked_meta_6673.py tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py`
  4. `uv run mypy src/specify_cli/mission_metadata.py`
  5. `git diff origin/main -- src/specify_cli/upgrade/migrations/` must be empty.
- **Files**: none edited; this is the verification gate.
- **Parallel?**: no.
- **Notes**: Do not run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Test Strategy

- Red first: T001 and T002 fail on the base commit for the reason described above; paste
  the failing node ids in the PR's Tests run section.
- The new unit test carries its own positive control on one fixture (stray directory →
  nothing tracked; pointer file → refusal), so the absence assertion cannot pass by
  accident.
- Existing refusal coverage stays green: index-only, corrupt, staged-differs, dangling
  `.git` pointer, and the tracked-copy seed.
- Typecheck: `uv run mypy src/specify_cli/mission_metadata.py` (CI's compiler gate); a
  passing test runner does not replace it.

## Risks & Mitigations

- **A symlinked `.git` or a `.git` file stops being an anchor** → the refusal tests regress.
  Mitigation: treat any non-directory entry as an anchor, and run the existing refusal
  tests.
- **An unreadable anchor reads as absent** → the refusal is weakened by an I/O error.
  Mitigation: any `OSError` other than "not found" returns "anchor" (fail closed).
- **A real repository above a stray `.git`** → the walk could stop too early. Mitigation:
  the walk continues past any non-repository `.git`; the first *anchor* wins.
- **Frozen-module edit temptation** → `content_hash` drift. Mitigation: T004 step 5 asserts
  the migrations tree is untouched.

## Review Guidance

- Confirm the diff contains no change under `src/specify_cli/upgrade/migrations/` and no
  edit to the reported test's assertions (`git diff origin/main -- tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py` shows additions only).
- Confirm the new unit test fails when `_has_no_git_anchor` is reverted to the base version
  (the red-first proof), and that the pointer-file half still refuses.
- Confirm `read_tracked_meta` gained no git subprocess and that the anchor check is O(depth)
  stats with no directory listing.
- Confirm both test modules pass with a basetemp outside `/tmp`, so the green does not
  depend on this host.

## Progress & Status

Not started. Record progress with `spec-kitty agent tasks mark-status T001 --status done`
as each subtask completes; the event log is the authority, not this file.
