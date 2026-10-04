---
work_package_id: WP01
title: One owner for the charter working-directory isolation
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- FR-010
planning_base_branch: issue-5317-charter-test-cwd-isolation
merge_target_branch: issue-5317-charter-test-cwd-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5317-charter-test-cwd-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5317-charter-test-cwd-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-test-cwd-isolation-01M43CM3
base_commit: f0f8ccdbf21812bbe5891c94e210d3b5a89136d7
created_at: '2026-10-04T12:21:57.867066+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-10-04T12:11:55Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/_support/
create_intent:
- tests/_support/charter_cwd.py
- tests/specify_cli/cli/commands/charter/test_charter_cwd_isolation.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/_support/charter_cwd.py
- tests/conftest.py
- tests/specify_cli/cli/commands/charter/test_charter_cwd_isolation.py
- tests/specify_cli/cli/commands/test_charter_resynthesize.py
- tests/agent/cli/commands/test_charter_resynthesize_cli.py
- tests/cli/commands/test_charter_json_error_contract.py
- tests/release/pinning_rule_inventory.json
- scripts/ci/derive_pinning_inventory.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – One owner for the charter working-directory isolation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

Witness the defect honestly, introduce the single shared isolation fixture, and remove the three per-file copies.

Done when:

1. A reproduction test builds a real linked worktree in tmp and shows the command's own refusal message through `runner.invoke` (FR-002).
2. `charter_cwd_isolation` exists once, in `tests/_support/charter_cwd.py`, registered through `pytest_plugins` in `tests/conftest.py` (FR-001, C-004).
3. With the fixture, the same start succeeds and the charter is written under the test tmp project (FR-001).
4. With the fixture active, moving into the linked worktree is still refused (FR-008).
5. The three copies of `_isolate_cwd_from_worktree_guard` are gone and their files pass using the shared fixture (FR-003).
6. `tests/release/test_pinning_inventory_fresh.py` passes with the re-derived inventory (FR-010).
7. The guard's own test files are untouched: zero diff on `tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py` and `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py`.

Requirement refs: FR-001, FR-002, FR-003, FR-008, FR-010. This WP also clears the pre-existing stale inventory reported in #5660.

## Context & Constraints

Read before coding: `.kittify/charter/charter.md`, `kitty-specs/charter-test-cwd-isolation-01M43CM3/spec.md`, `kitty-specs/charter-test-cwd-isolation-01M43CM3/plan.md` (Design section), `kitty-specs/charter-test-cwd-isolation-01M43CM3/research.md`, `kitty-specs/charter-test-cwd-isolation-01M43CM3/contracts/test-isolation-contract.md`. Load action doctrine with `spec-kitty charter context --action implement`.

The defect in one paragraph: the charter commands `generate`, `synthesize` and `resynthesize` call `resolve_charter_write_root(Path.cwd())` (`src/specify_cli/cli/commands/charter/generate.py:438`, `synthesize.py:212`, `resynthesize.py:103`). The guard refuses when the **process working directory** is a linked worktree. Many tests point the command at a **test tmp project** by patching `specify_cli.cli.commands.charter.find_repo_root`, but never change directory, so the guard sees the **invoking checkout**. When pytest starts in a lane worktree (a linked worktree) those tests fail with `Refusing charter write from linked git worktree`.

Hard constraints (reviewers reject on any breach):

- **C-001** No change under `src/`. `git diff --stat issue-5317-charter-test-cwd-isolation -- src/` must stay empty.
- **C-002** Never patch, stub or replace `resolve_charter_write_root` to change its result. The real guard must run.
- **C-003** The isolation fixture is opt-in.
- **C-004** Exactly one definition of the isolation fixture in `tests/`.
- **C-006** Run only the named test files below. No directory runs, no `make test-fast`, no `tests/architectural/` sweep.
- No `# noqa`, `# type: ignore`, `skip` or `xfail` added. New code passes `ruff check`, `ruff format --check --force-exclude <files>` and `mypy` clean.
- Keep the four terms distinct in docstrings and messages: process working directory / repository root checkout / linked worktree / test tmp project. Say "Mission", never "feature".

You work in a lane worktree, which is itself a linked worktree. That is useful: the affected tests are red here before the fix and green after. Run tests with the lane's own sources (`PYTHONPATH=$PWD/src <repo-root>/.venv/bin/python -m pytest ...` if the lane has no `.venv`; do not use a bare `uv run`).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5317-charter-test-cwd-isolation; completed changes must merge back into issue-5317-charter-test-cwd-isolation.
- **Planning base branch**: issue-5317-charter-test-cwd-isolation
- **Merge target branch**: issue-5317-charter-test-cwd-isolation

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path `spec-kitty agent action implement` gives you, never a reconstructed one.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first reproduction through the existing entry point

- **Purpose**: Pin the defect so it is red from any checkout, with the product's refusal message as the witnessed failure. A missing-fixture or import error is NOT an acceptable red.
- **Files**: `tests/specify_cli/cli/commands/charter/test_charter_cwd_isolation.py` (new).
- **Steps**:
  1. Read `tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py` for the existing pattern: `fresh_repo`, the linked-worktree fixture, `clear_caches()` from `kernel.git_topology`, and the markers (`non_sandbox`, `git_repo`). Build the same shape locally: a tmp git repository with one commit and a linked worktree added with `git worktree add`. Do not import fixtures from that file and do not edit it.
  2. Build a separate **test tmp project** (a directory outside both the tmp repository and its linked worktree) with whatever `charter generate` needs to succeed. Take the working setup from `tests/agent/cli/commands/test_charter_cli.py::test_generate_command_success` (lines 225-243): it creates `tmp_path / "repo"` inside the test body, runs the file's `_git_init` helper on it, and invokes `generate` with `--no-from-interview`. `generate` requires a git working tree (`generate.py:446`), so the test tmp project must be its own `git init` repository — a normal one, not a linked worktree.
  3. Write two tests in this first commit:
     - `test_unisolated_generate_from_linked_worktree_is_refused`: `monkeypatch.chdir(linked_worktree)`, patch `specify_cli.cli.commands.charter.find_repo_root` to return the test tmp project, invoke `charter generate` through `CliRunner` on `specify_cli.cli.commands.charter.app`. Assert exit code is non-zero AND the output contains `Refusing charter write from linked git worktree`. This test is green now and stays forever: it is the permanent statement of what happens without the helper.
     - `test_isolated_generate_from_linked_worktree_succeeds`: same start and same patch, asserting exit code 0 and that the charter file exists under the test tmp project. In this first commit it does NOT use any helper, so it fails on its assertion with the refusal text in the failure output. That is the honest red.
  3b. Markers: follow the sibling `test_charter_write_root_4785.py:43` (`non_sandbox`, `git_repo`, and the tier marker it uses) so the file is collected in the same lanes.
  4. Run the file; confirm 1 passed, 1 failed, and that the failure output contains the refusal message. Commit as a separate commit (`test(charter): reproduce the linked-worktree charter write refusal in tests (#5317)`). Record the red output for the PR.
- **Notes**: Call `clear_caches()` in an autouse fixture in this file, as the guard tests do, so a cached topology probe from another test cannot leak in. Use `subprocess.run([...], check=True, capture_output=True)` with explicit `git -c user.name=... -c user.email=...` for the commit, so the test does not depend on the developer's git config.

### Subtask T002 – The shared fixture, registered once

- **Purpose**: One owner for the isolation (FR-001, C-003, C-004).
- **Files**: `tests/_support/charter_cwd.py` (new), `tests/conftest.py` (one entry added to the existing `pytest_plugins` list at line 53), the reproduction file from T001.
- **Steps**:
  1. Look at `tests/_support/p0_repro.py` and how `tests/conftest.py` registers it, and follow that shape.
  2. Implement per `kitty-specs/charter-test-cwd-isolation-01M43CM3/contracts/test-isolation-contract.md`:

     ```python
     @pytest.fixture
     def charter_cwd_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Path]:
         def isolate(project_root: Path | None = None) -> Path:
             root = tmp_path if project_root is None else project_root
             monkeypatch.chdir(root)
             monkeypatch.setattr("specify_cli.cli.commands.charter.find_repo_root", lambda *args, **kwargs: root)
             return root
         return isolate
     ```

     Verify the real signature of `find_repo_root` (`specify_cli.task_utils.find_repo_root`) and how the command modules look it up (`_charter_pkg.find_repo_root()`), and make the replacement accept the same call shapes. A test's own later `patch(...)` of the same name must still win, so tests that keep their `with patch(...)` block continue to work.
  3. Docstring: say what it does, why the guard probes the process working directory, that it is opt-in, and that the real guard still runs. Use the four terms from the spec. **Do not write the literal `make test-fast` in this module** — that literal is what made the old copy a pinned rule in the release inventory (see research.md R-04).
  4. Full type annotations; `.venv/bin/python -m mypy --strict tests/_support/charter_cwd.py` clean.
  5. In the reproduction file, change `test_isolated_generate_from_linked_worktree_succeeds` to start in the linked worktree and then call `charter_cwd_isolation(project)` instead of patching by hand. It turns green.
  6. Add `test_guard_still_refuses_after_helper_when_cwd_returns_to_linked_worktree` (FR-008): request the fixture, call it, then `monkeypatch.chdir(linked_worktree)` and invoke `generate` → non-zero exit and the refusal message. A fixture that stubbed the guard would fail this test.
  7. Add a small test that the fixture defaults to `tmp_path` and returns the root it used, and one that the real invoking working directory is restored after the test (compare `Path.cwd()` in a module-level check or a finalizer-ordered fixture; keep it simple).
- **Notes**: Do not make the fixture autouse. Do not touch `resolve_charter_write_root`.

### Subtask T003 – Retire the three copies

- **Purpose**: Exactly one definition (FR-003).
- **Files**: `tests/specify_cli/cli/commands/test_charter_resynthesize.py` (copy near line 22), `tests/agent/cli/commands/test_charter_resynthesize_cli.py` (near line 33), `tests/cli/commands/test_charter_json_error_contract.py` (near line 25).
- **Steps**:
  1. Known shapes (verify): the copies in `tests/specify_cli/cli/commands/test_charter_resynthesize.py:21` and `tests/agent/cli/commands/test_charter_resynthesize_cli.py:32` are autouse; the one in `tests/cli/commands/test_charter_json_error_contract.py:25` is opt-in and requested by three tests. A test's own `patch(..., side_effect=...)` of `find_repo_root` still wins over the shared fixture's replacement.
  2. Delete the local definition. Replace it with the shared fixture while preserving behaviour exactly:
     - where the copy was autouse for the whole file, add a small autouse fixture in that file that requests `charter_cwd_isolation` and calls it for the directory the old copy used (`tmp_path`), **only if** the tests' own `find_repo_root` patches are unaffected. If the shared fixture's `find_repo_root` replacement changes a test's outcome (a test that expects the real resolver), keep that test out of the autouse path. Prefer explicit per-test requests where the file is small.
     - where the copy was opt-in (`test_charter_json_error_contract.py`), switch each requesting test to `charter_cwd_isolation` and call it at the top of the test. Leave tests that need the invoking checkout's working directory alone (for example `test_non_json_error_preserves_bracketed_tokens`).
  3. A local autouse wrapper that only *requests and calls* the shared fixture is not a second definition of the isolation; a function that calls `monkeypatch.chdir` itself is. After this subtask `grep -rn "_isolate_cwd_from_worktree_guard" tests/` returns nothing.
  4. Run the three files; all tests pass with the same counts as before the change (record before and after counts).

### Subtask T004 – Re-derive the pinning inventory

- **Purpose**: The retired copy is recorded in `tests/release/pinning_rule_inventory.json` (rule `tests/cli/commands/test_charter_json_error_contract.py::_isolate_cwd_from_worktree_guard`). `tests/release/test_pinning_inventory_fresh.py` requires the file to equal its derivation (FR-010).
- **Files**: `tests/release/pinning_rule_inventory.json`, and `scripts/ci/derive_pinning_inventory.py` only if the derivation demands it.
- **Steps**:
  1. Commands (script header lines 84-91): `python scripts/ci/derive_pinning_inventory.py` regenerates the file; `--check` verifies; `--stdout` previews. Do not hand-edit the JSON.
  2. **Known pre-existing red**: the inventory is already stale on the base branch, before this mission (reported as #5660). `--check` exits non-zero and `tests/release/test_pinning_inventory_fresh.py::test_inventory_is_reproducible_by_rerunning_the_derivation` fails on the unmodified base, because a fresh derivation adds the rule `tests/_support/p0_repro.py::<module-docstring>`. Confirm this at the start of the WP (before T001) and record the output; it is not yours, and regenerating here fixes it.
  3. Regenerate after T003. The expected diff is exactly: the rule `tests/cli/commands/test_charter_json_error_contract.py::_isolate_cwd_from_worktree_guard` removed, and the rule `tests/_support/p0_repro.py::<module-docstring>` added. If any other entry changes, stop and report. If a NEW rule appears for `tests/_support/charter_cwd.py` or a local wrapper, a docstring or comment of yours mentions a pinned subject (the `make test-fast` literal); remove the mention rather than adding a disposition.
  4. The removed rule has no hand-authored disposition in the script, so `scripts/ci/derive_pinning_inventory.py` should need no edit. If the new `p0_repro` rule requires a disposition the derivation cannot produce by itself, stop and report instead of inventing one.
  5. Run `tests/release/test_pinning_inventory_fresh.py`; green (5 passed).

### Subtask T005 – Verify and hand over

- **Steps**:
  1. Run, from the lane worktree:

     ```bash
     pytest tests/specify_cli/cli/commands/charter/test_charter_cwd_isolation.py \
            tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py \
            tests/specify_cli/cli/commands/test_charter_resynthesize.py \
            tests/agent/cli/commands/test_charter_resynthesize_cli.py \
            tests/cli/commands/test_charter_json_error_contract.py \
            tests/release/test_pinning_inventory_fresh.py -q
     ```
  2. `ruff check` and `ruff format --check --force-exclude` on every file you touched; `.venv/bin/python -m mypy --strict` on `tests/_support/charter_cwd.py` and the new test file (there is no configured mypy invocation for `tests/`; this one passes on the sibling `tests/_support/p0_repro.py`).
  3. `git diff --stat issue-5317-charter-test-cwd-isolation -- src/` is empty. `git diff --stat issue-5317-charter-test-cwd-isolation -- tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` is empty.
  4. Report in the Activity Log: commands, passed/failed counts, the red-first output from T001, and any friction (the orchestrator copies friction into the mission tracer files; do not edit `kitty-specs/` from the lane).

## Test Strategy

Tests are the deliverable. Red-first order is mandatory: T001's commit precedes the fixture commit. The named files in T005 are the complete targeted surface for this WP.

## Risks & Mitigations

- **`generate` needs more project setup than expected** → copy the minimal arrangement from an existing passing generate test rather than inventing one.
- **The shared fixture's `find_repo_root` replacement changes a test that relied on the real resolver** → keep such tests off the fixture; the fixture is opt-in.
- **Inventory regeneration changes entries beyond the two expected ones** (one removed, the pre-existing `p0_repro` one added, #5660) → stop and report; do not commit an unexplained inventory diff.
- **Topology probe caching** → `clear_caches()` around tests that build repositories.

## Review Guidance

- Check out T001's commit alone and run the reproduction file: the isolated-arm failure must show the refusal message, not a fixture/import error.
- Confirm no test or fixture patches `resolve_charter_write_root`; `grep -rn "resolve_charter_write_root" tests/_support/` shows no patching.
- Confirm one definition: `grep -rn "def charter_cwd_isolation\|_isolate_cwd_from_worktree_guard" tests/`.
- Confirm the with-helper refusal control exists and would fail under a stubbed guard.
- Confirm the inventory diff is exactly the removed rule plus the pre-existing `p0_repro` rule (#5660).
- Confirm `ruff`, format and `mypy` were run on the touched files.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last). Append at the end, format `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`, UTC.

- 2026-10-04T12:11:55Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status. Record subtask completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.
