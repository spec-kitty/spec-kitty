---
work_package_id: WP04
title: Source snapshot builder handles a shallow checkout
dependencies: []
requirement_refs:
- FR-006
- NFR-003
- SC-002
planning_base_branch: kitty/nightly-reds-2026-10-03
merge_target_branch: kitty/nightly-reds-2026-10-03
branch_strategy: Planning artifacts for this mission were generated on kitty/nightly-reds-2026-10-03. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/nightly-reds-2026-10-03 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-reds-2026-10-03-01M42RR1
base_commit: 77d8c1c1641f0fbff6b66d7d3f1ca727476371d8
created_at: '2026-10-04T06:21:57.879027+00:00'
subtasks:
- T011
- T012
- T013
- T014
phase: Phase 1 - Test repairs
history:
- at: '2026-10-04T06:16:20Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/_support/
create_intent:
- tests/_support/test_shared_build_artifacts.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/_support/shared_build_artifacts.py
- tests/_support/test_shared_build_artifacts.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – Source snapshot builder handles a shallow checkout

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

If this work package was returned from review, the feedback reference is in the status event log (`spec-kitty agent tasks status --mission nightly-reds-2026-10-03-01M42RR1`). Address every item before handing back.

---

## Objectives & Success Criteria

- `default_source_snapshot_builder` in `tests/_support/shared_build_artifacts.py` produces a readable repository when `source_root` is a shallow clone (FR-006).
- A new test `tests/_support/test_shared_build_artifacts.py` builds a snapshot from a depth-1 clone and is red before the fix and green after it.
- One case of `tests/e2e/test_worktree_owned_root_concurrency.py::test_installed_cli_keeps_two_owned_worktrees_isolated` still passes on this full-history checkout.

## Context & Constraints

- Evidence and classification: `kitty-specs/nightly-reds-2026-10-03-01M42RR1/research/nightly-red-memo.md`.
- Spec and plan: `kitty-specs/nightly-reds-2026-10-03-01M42RR1/spec.md`, `plan.md`.
- **Hard rules (NFR-001, C-001)**: change only the files listed under `owned_files`. Do not edit anything under `src/`. Do not raise a budget or timeout, add a retry, or skip, xfail, deselect or delete a test. Keep every existing assertion except the stale literal you are replacing (NFR-002).
- **Test runs (C-003)**: run only the named node ids or the named file, in the foreground, serially:
  `PWHEADLESS=1 <repo>/.venv/bin/python -m pytest -p no:cacheprovider -q -n0 <ids>` where `<repo>` is `/home/stijn/Documents/_code/SDD/fork/sk-nightly-reds-2026-10-03` and the command is run **from your lane worktree** with `PYTHONPATH=$PWD/src`. Never run a whole directory, `make test-fast` or `make test-full`; the orchestrator runs the breadth.
- **Red-first evidence (NFR-003)**: before editing, run the named tests and record the failing summary line. After the fix, record the passing summary line. Put both in the commit message body.
- Lint: `<repo>/.venv/bin/ruff check <files>` and `<repo>/.venv/bin/ruff format --check --force-exclude <files>` must be clean. No new `# noqa` or `# type: ignore`.
- Commit on the lane branch with a conventional message `test(<area>): ...`. Do not push. Do not touch `uv.lock`.
- Terminology: write Mission, never Feature, in new prose.

## Branch Strategy

- **Strategy**: lane worktree allocated by `spec-kitty agent action implement WP04 --agent claude`
- **Planning base branch**: kitty/nightly-reds-2026-10-03
- **Merge target branch**: kitty/nightly-reds-2026-10-03

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implementation command: `spec-kitty agent action implement WP04 --agent claude --mission nightly-reds-2026-10-03-01M42RR1`

## Subtasks & Detailed Guidance

### Subtask T011 – Write the failing test first (commit it separately)

- **Purpose**: the nightly performance job checks out one commit (no `fetch-depth`). `default_source_snapshot_builder` runs `git init` + `git -c uploadpack.allowAnySHA1InWant=true fetch -q --no-tags <source> <sha>` + `git checkout --detach`. Fetching from a shallow source without `--update-shallow` makes git refuse to record the shallow boundary while still exiting 0, so the snapshot has commits whose parents are missing and no `.git/shallow`. Every project cloned from it has truncated history, and `git log` fails with "Could not read <sha> / Failed to traverse parents". Since `5b5699e500` the product walks the coordination branch history (`coord_branch_is_post_fix`, `src/specify_cli/coordination/coord_seed.py`), which fails closed with `COORD_SEED_GIT_PROBE_FAILED`, so all 20 params of the e2e test exit rc=1 on the nightly.
- **Steps**:
  1. Create `tests/_support/test_shared_build_artifacts.py`. Follow the conventions of the sibling `tests/_support/test_run_basetemp.py` (markers, imports, style).
  2. Fixture: in `tmp_path` create a small origin repository with at least three commits (set `user.name`/`user.email` locally, disable signing), then `git clone --depth 1 file://<origin> <shallow>`. A plain path clone is not shallow; the `file://` URL is required. Assert `git rev-parse --is-shallow-repository` prints `true` in the fixture so the test cannot pass vacuously.
  3. Test 1 (shallow source): call `default_source_snapshot_builder(shallow, tmp_path / "snap")`, then assert in the snapshot: `git log --format=%H HEAD` exits 0; `git rev-parse --is-shallow-repository` prints `true`; `git fsck --connectivity-only` exits 0 (or the closest check that proves no missing parent). Then `git clone -q <snap> <clone>` (as the consumers do) and assert `git log` exits 0 there too.
  4. Test 2 (positive control, full source): build a snapshot from the full origin and assert HEAD equals the origin HEAD, `git log` lists all commits and the snapshot is **not** shallow. This must pass both before and after the fix.
  5. Run the new file: test 1 fails, test 2 passes. Commit this as its own commit (`test(support): reproduce truncated snapshot from a shallow source`) with the failing summary in the body.
- **Files**: `tests/_support/test_shared_build_artifacts.py` (new)

### Subtask T012 – Fix the builder

- **Steps**:
  1. Add `--update-shallow` to the fetch command in `default_source_snapshot_builder` (near line 231).
  2. Extend the docstring with one or two sentences on why (a shallow source would otherwise leave missing parents with no shallow marker).
  3. Nothing else in the module changes.
- **Files**: `tests/_support/shared_build_artifacts.py`
- **Validation**: the new file passes (2 passed). Commit (`fix(support): record the shallow boundary in the source snapshot`).

### Subtask T013 – Prove the consumer still works on a full clone

- **Steps**: run exactly one param of the e2e consumer, foreground, serial:
  `PWHEADLESS=1 <repo>/.venv/bin/python -m pytest -p no:cacheprovider -q -n0 "tests/e2e/test_worktree_owned_root_concurrency.py::test_installed_cli_keeps_two_owned_worktrees_isolated[0]"`
  It takes about a minute. If the test is excluded by default markers, add the marker option the file's `pytestmark` needs (read the file header) rather than skipping this step. Record the result. Do not run all 20 params.

### Subtask T014 – Check other callers of the builder

- **Steps**: `grep -rn "default_source_snapshot_builder\|ensure_run_stable_source_snapshot" tests` and confirm no caller depends on the snapshot being non-shallow. Note the finding in the commit body.

## Risks & Mitigations

- A local path clone silently ignores `--depth`; use `file://`.
- Older git versions accept `--update-shallow` (git >= 1.9), so no version guard is needed.

## Review Guidance

- The red-first commit exists before the fix commit and its test fails on it for the stated reason.
- The shallow fixture asserts it is shallow; the positive control passes on both commits.
- The only production-side change is the one flag plus the docstring.
- No `fetch-depth` change in any workflow file (that would mask the builder defect).

## Activity Log

- 2026-10-04T06:16:20Z – system – Prompt created.
