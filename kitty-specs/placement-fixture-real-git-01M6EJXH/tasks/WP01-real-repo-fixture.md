---
work_package_id: WP01
title: Real-repo fixture and the seam-distinction pin (#7055)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
planning_base_branch: issue-7055-placement-fixture-real-git
merge_target_branch: issue-7055-placement-fixture-real-git
branch_strategy: Planning artifacts for this mission were generated on issue-7055-placement-fixture-real-git. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7055-placement-fixture-real-git unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - One module, two fail-safe seams
history:
- at: '2026-11-02T17:00:00+00:00'
  actor: system
  action: Prompt generated during tasks phase
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/migration/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/migration/test_runtime_state_cutover_placement.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7055'
---

# Work Package Prompt: WP01 – Real-repo fixture and the seam-distinction pin (#7055)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Fix the deterministic red in
`tests/specify_cli/migration/test_runtime_state_cutover_placement.py` by making its
enclosing-repo fixture a real git repository, and pin the tracked-meta refusal seam that the
bare marker accidentally exercised. **No `src/` change.**

**Done when**:

- `_init_bare_git_marker` is replaced by a real `git init` helper used by all six call sites,
  with a docstring that states why a marker is no longer sufficient.
- `test_mismatched_feature_dir_fails_closed_without_writing` raises `PlacementMismatchError`
  again, with its `pytest.raises` / "nothing written" assertions byte-identical (FR-002).
- A new regression test pins the unusable-anchor path: `cutover_mission` returns
  `flipped=False` with a `TRACKED_META_UNAVAILABLE` `skipped_notice`, raises nothing, writes no
  `meta.json` (FR-003).
- The module is 10/10 green and `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` is
  green (FR-004, NFR-003, SC-001, SC-002).

## Context & Constraints

- Issue: #7055 (reproduced on `origin/main` `9aed3a8012`: 1 failed, 8 passed).
- Evidence and the probe of both fixture shapes: [research.md](../research.md) D1–D4.
- Design: [plan.md](../plan.md) Phase 1 and IC-01/IC-02; requirements: [spec.md](../spec.md).
- Product path (read-only): `src/specify_cli/migration/runtime_state_cutover.py` —
  `cutover_mission` calls `_tracked_meta_notice(feature_dir)` **before** seeding; a refusal
  returns `CutoverResult(flipped=False, skipped_notice=...)`. The placement check lives in
  `_flip_phase` and is reached only after seed + verify.
- Classification (read-only): `src/specify_cli/upgrade/tracked_meta_notice.py` +
  `specify_cli.mission_metadata.read_tracked_meta`. A `.git` anchor that git runs and refuses
  (`fatal: not a git repository`) is deliberately `unavailable=True` — "unknown", never
  "nothing tracked" — which is why a bare marker short-circuits.
- The existing pin for that product decision:
  `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py::test_a_git_that_refuses_to_answer_is_not_read_as_nothing_tracked`.
- `pytestmark = [pytest.mark.fast]` and `-p no:randomly -n0` compatibility must survive.
  `GIT_CEILING_DIRECTORIES` stays pinned to the test's `tmp_path`.
- Do not touch `packs/built-in/**` or agent copies.

## Branch Strategy

- **Strategy**: planning on `issue-7055-placement-fixture-real-git` (single_branch topology);
  this WP runs in the lane worktree `finalize-tasks` computes, and merges back into
  `issue-7055-placement-fixture-real-git`.
- **Planning base branch**: `issue-7055-placement-fixture-real-git`
- **Merge target branch**: `issue-7055-placement-fixture-real-git`

## Subtasks & Detailed Guidance

### T001 – Capture the red baseline and the two-shape probe

- **Purpose**: prove the failure exists before touching the file, and that the only difference
  between the failing and passing fixture shape is the marker vs a real repo.
- **Steps**:
  1. Run `uv run --frozen pytest -q -p no:randomly -n0
     tests/specify_cli/migration/test_runtime_state_cutover_placement.py` and record
     `1 failed, 8 passed` plus the failing node id.
  2. Optionally re-run the two-shape probe from `research.md` D2 (bare marker →
     `skipped_notice`; `git init` → `PlacementMismatchError`) and paste the two lines into the
     WP history note.
- **Files**: none (evidence only).
- **Notes**: the module takes ~2 minutes on a cold venv because of git subprocesses; a warm run
  is fast. Do not run the full suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

### T002 – Replace the bare marker with a real repo helper

- **Purpose**: give the fixture the shape every live Mission has, so the tracked-meta seam
  answers "nothing tracked for this path" and the cutover reaches the placement check.
- **Steps**:
  1. Rename `_init_bare_git_marker(repo_root)` to `_init_git_repo(repo_root)` and implement it
     as `subprocess.run(["git", "init", "-q", str(repo_root)], check=True,
     capture_output=True)`. Import `subprocess` at module top (alphabetical position per the
     repo's import style).
  2. Rewrite its docstring: the cutover path shells out to git for the tracked-`meta.json` seam
     (#6673), and a bare `.git` marker makes git run and refuse, which the classifier treats as
     "unknown" and refuses — so a marker would short-circuit before the placement check. State
     that no commit is needed: an unborn `HEAD` classifies as "nothing tracked".
  3. Update all six call sites (mismatch, direct `_flip_phase` mismatch, genuine-primary flip,
     symlinked-root agreement, two action-context degrade tests) and any comment that says
     "bare marker".
  4. Keep the module-level `_hermetic_git_ceiling` fixture unchanged.
- **Files**: `tests/specify_cli/migration/test_runtime_state_cutover_placement.py`
- **Notes**: `git init` does not need an identity; do not add `git commit` (plan Q2). The
  fixture must still work when `tmp_path` sits inside a larger repository — the ceiling env var
  is what guarantees that.

### T003 – Prove the mismatch test reaches the fail-close

- **Purpose**: the assertion is the contract; it must fail before and pass after with no edits.
- **Steps**:
  1. Re-run the module.
  2. Confirm `test_mismatched_feature_dir_fails_closed_without_writing` passes and that
     `git diff` shows no change inside that test's body (only the helper and comments).
  3. Confirm no `xfail`, `skip`, or `pytest.raises(..., match=...)` relaxation was introduced.
- **Files**: same test module (no assertion edits).
- **Notes**: if the test still fails, stop and report rather than adjusting the assertion — the
  fixture change would then be wrong and the product path needs re-examination.

### T004 – Add the seam-distinction regression pin

- **Purpose**: make the two fail-safe paths distinguishable from the tests alone, so a future
  fixture "simplification" cannot silently move a test onto the wrong seam.
- **Steps**:
  1. Add `test_unusable_git_anchor_refuses_with_tracked_meta_notice_without_writing` after the
     mismatch tests. Build the marker shape explicitly (a local `(root / ".git").mkdir()` or a
     small local helper named to say what it is, e.g. `_init_unusable_git_anchor`).
  2. Call `rsc.cutover_mission(divergent_dir, status_feature_dir=status_dir)` and assert:
     the call does not raise; `result.flipped is False`; `result.skipped_notice` is not `None`
     and ends with `[TRACKED_META_UNAVAILABLE]`; `result.seeded_count == 0`;
     `not (divergent_dir / "meta.json").exists()`; `not (canonical_dir / "meta.json").exists()`.
  3. Docstring: explain this is the deliberate #6673 refusal (git ran and refused → identity
     unknown → no identity may be minted), and that `test_mismatched_feature_dir_fails_closed_*`
     therefore must use a real repo.
- **Files**: same test module.
- **Notes**: assert the stable code suffix, not the whole notice sentence (the wording is out of
  scope; see `## Deferred` in the PR). Keep `tmp_path`-only paths.

### T005 – Neighbour suite and static checks

- **Purpose**: prove the fixture change did not drift from the product contract it leans on,
  and that the module is clean under the repo's linters.
- **Steps**:
  1. `uv run --frozen pytest -q -p no:randomly -n0
     tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`
  2. `uv run --frozen ruff check tests/specify_cli/migration/test_runtime_state_cutover_placement.py`
  3. `uv run --frozen mypy tests/specify_cli/migration/test_runtime_state_cutover_placement.py`
     (if the repo's config covers this path; otherwise record the exact command and its
     not-covered reason).
  4. Record all three outcomes in the WP history note.
- **Files**: none (evidence only).
- **Notes**: `tests/specify_cli/migration` is out-of-matrix in CI (nightly only), so this local
  evidence is what the PR cites.

## Test Strategy

- Primary: the module itself, 10 tests, `-p no:randomly -n0`.
- Regression: `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` (the product pin).
- Static: `ruff check` and `mypy` on the edited module.
- No new test file, no shared fixture changes, no product code edits.

## Risks & Mitigations

- **Risk**: a call site keeps the marker and silently exercises the wrong seam.
  **Mitigation**: T002 enumerates all six; the new T004 test is the explicit marker-shape
  coverage; T003 proves the mismatch path.
- **Risk**: `git init` picks up a repo above `tmp_path` on some host. **Mitigation**: the
  existing `_hermetic_git_ceiling` fixture stays and the repo is created under `tmp_path`.
- **Risk**: the new test over-pins notice text. **Mitigation**: assert the code suffix and the
  outcome only.
- **Risk**: a reviewer reads the fixture change as weakening the test. **Mitigation**: the
  `pytest.raises` and "nothing written" assertions are untouched; the diff is visible in the
  helper and comments only.

## Review Guidance

- Confirm the mismatch test's assertion body is unchanged and no skip/xfail was added.
- Confirm the new test fails if the marker fixture is "fixed" to a real repo (mutation check:
  swap the marker helper for `_init_git_repo` in the new test and observe the assertion fail
  with a raised `PlacementMismatchError`).
- Confirm no `src/` file is in the diff.
- Confirm the module's `pytestmark` and hermetic git ceiling survive.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`) — never
in this prompt file. Do not hand-edit a history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission placement-fixture-real-git-01M6EJXH`
