---
work_package_id: WP03
title: Recurrence tripwire for charter working-directory leaks
dependencies:
- WP02
requirement_refs:
- FR-005
- FR-006
- FR-009
planning_base_branch: issue-5317-charter-test-cwd-isolation
merge_target_branch: issue-5317-charter-test-cwd-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5317-charter-test-cwd-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5317-charter-test-cwd-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-test-cwd-isolation-01M43CM3
base_commit: f0f8ccdbf21812bbe5891c94e210d3b5a89136d7
created_at: '2026-10-04T12:51:35.871642+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 3 - Guard
history:
- at: '2026-10-04T12:11:55Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/_support/
create_intent:
- tests/_support/charter_cwd_tripwire.py
- tests/specify_cli/cli/commands/charter/test_charter_cwd_tripwire.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/_support/charter_cwd_tripwire.py
- tests/specify_cli/cli/commands/charter/test_charter_cwd_tripwire.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Recurrence tripwire for charter working-directory leaks

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

Any test that reaches a guarded charter write command while its process working directory is in the invoking checkout fails, in every kind of checkout, with a message naming the test and `charter_cwd_isolation`. There are no exemptions.

Done when:

1. An autouse tripwire in `tests/_support/charter_cwd_tripwire.py` watches the guard at every charter command module that probes the process working directory, always calls through, and fails the offending test at teardown (FR-005, C-002).
2. Self-mutation tests plant one offender per shape and each is caught; a clean test is not (FR-005).
3. A coverage test fails if a cwd-probing guard call site is not watched (FR-005).
4. No exemption marker or allowlist exists, and a test asserts that (FR-006).
5. The bounded straggler run is clean (C-005).
6. The mission's issue matrix can record both issues as fixed (FR-009 — the orchestrator writes the matrix; this WP supplies the evidence in its Activity Log).

Requirement refs: FR-005, FR-006, FR-009.

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

Ownership note: this WP adds one entry to the `pytest_plugins` list in `tests/conftest.py`, which WP01 owns. WP01 is complete before this WP starts (sequential dependency), so there is no parallel collision. Record the out-of-map edit in the Activity Log with that one-line rationale. Straggler fixes in T014 may likewise touch test files outside `owned_files`; record each.

Why a runtime tripwire and not a static check: see `kitty-specs/charter-test-cwd-isolation-01M43CM3/research.md` R-03. The leaking tests patch and invoke in at least five spellings across 21 files, and some files mix leaking and isolated tests.

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first self-mutation tests

- **Purpose**: Prove the tripwire catches offenders before it exists (ATDD), and keep proving it afterwards.
- **Files**: `tests/specify_cli/cli/commands/charter/test_charter_cwd_tripwire.py` (new).
- **Design**: run the planted tests in their own pytest subprocess, so their failures cannot trip the outer test. `pytester` is deliberately NOT enabled in this repository (`tests/_support/test_p0_repro.py:7`, `tests/ci/test_battery_partition_plugin.py:8`). Copy the established pattern from `tests/_support/test_p0_repro.py:56-78`: plain `subprocess.run` of `sys.executable -m pytest`, `-c os.devnull`, `--rootdir <tmp>`, `-p tests._support.charter_cwd_tripwire -p tests._support.charter_cwd`, `PYTEST_ADDOPTS` stripped from the environment, `cwd=_REPO_ROOT`.
- **Steps**:
  1. One inner session, one planted test file written under `tmp_path`, to keep the cost to a single subprocess. `PYTHONPATH` must carry both the repository root (for `tests._support`) and `src` (the `pythonpath = src` setting in `pytest.ini` is not applied under `-c os.devnull`).
  2. `cwd=_REPO_ROOT` (the invoking checkout) recreates the leak by itself; the planted offenders need no `os.chdir`. The tripwire defines "invoking checkout" from its own module location (see T012). Planted offenders patch `find_repo_root` with `side_effect=TaskCliError(...)` (from `specify_cli.task_utils`), so the command stops right after the guard and can never write anything into the invoking checkout.
  3. Planted cases, each a separate inner test:
     - `direct`: `with patch("specify_cli.cli.commands.charter.find_repo_root") as m: m.return_value = project` then `runner.invoke(app, ["generate", ...])`. Expect: caught.
     - `via_helper`: the invoke is inside a module-level helper function, arguments held in a variable. Expect: caught.
     - `setattr_spelling`: `monkeypatch.setattr("specify_cli.cli.commands.charter.find_repo_root", lambda *a, **k: project)`. Expect: caught.
     - `isolated_neighbour`: same file, uses `charter_cwd_isolation(project)`. Expect: passes. This is the positive control beside the offenders (a file-level check would have let the offenders through).
     - `synthesize` or `resynthesize` offender, so more than one watched command is exercised. Expect: caught.
     - `no_guard`: a test that never reaches the guard. Expect: passes.
     - `late_import`: a test that imports `specify_cli.cli.commands.charter` inside its body (the package not yet imported in that session before the test) and then invokes a guarded command. Expect: caught. Order the planted file or use a separate inner invocation so this case really runs before the package is imported; say in a comment how that is ensured.
     The planted tests only need the command to *reach* the guard; they do not need the command to succeed afterwards. Keep their project setup minimal.
  4. Outer assertions: outcome counts (offenders reported as errors or failures at teardown, the two clean tests passed), and for each offender the output contains its node id and the string `charter_cwd_isolation` in one message (NFR-004).
  5. Commit this file first, red: the plugin module does not exist yet, so the inner session cannot load it and the outer assertions on outcome counts fail. Say so in the commit message. Then T012 turns it green.
  5b. Markers: follow `tests/_support/test_p0_repro.py` and the sibling charter test files for the tier and `non_sandbox` markers.
  6. Mark the test honestly for its tier: a subprocess session is not `fast`. Look at how `tests/specify_cli/cli/commands/charter/` marks its tests and at the markers the repository requires (`pytest.ini`), and pick the tier that matches the measured run time. Record the measured time; target under 5 seconds on a developer machine (NFR-002), and report it if it is slower rather than hiding it.

### Subtask T012 – The tripwire plugin

- **Files**: `tests/_support/charter_cwd_tripwire.py` (new); one entry in `pytest_plugins` in `tests/conftest.py` (out-of-map, see ownership note).
- **Behaviour** (contract: `kitty-specs/charter-test-cwd-isolation-01M43CM3/contracts/test-isolation-contract.md`):
  1. `INVOKING_CHECKOUT = Path(__file__).resolve().parents[2]` — the checkout that contains this `tests/` tree.
  2. `WATCHED_MODULES`: the charter command modules that call the guard with the process working directory — today `specify_cli.cli.commands.charter.generate`, `.synthesize`, `.resynthesize`. They import the guard by name, so the wrapper must be set on each module's `resolve_charter_write_root` attribute.
  3. Autouse function-scoped fixture:
     - For each watched module **already imported** (`sys.modules`), `monkeypatch.setattr(module, "resolve_charter_write_root", wrapper)`. Do not import the command modules from the fixture for every test in the suite: that would add import cost to thousands of unrelated tests (NFR-003). But a module imported *later in the same test* must also be covered. Solve this properly — for example, wrap at the source: every watched module imports the name from `specify_cli.cli.commands.charter._charter_write_root`; importing that one small module once per session and checking, at teardown, any watched module that appeared in `sys.modules` during the test is not enough because the call already happened unwatched. Evaluate these options and pick the one that is correct and cheap, documenting the choice in the module docstring:
       **Never import `specify_cli` at the plugin module's top level.** `pytest_plugins` modules are imported while `tests/conftest.py` loads, which is BEFORE `pytest_configure` (`tests/conftest.py:219`) sets the isolated HOME (see the comment at `tests/conftest.py:55-66`). `specify_cli.core.tool_checker.CLAUDE_LOCAL_PATH` and similar module-level values bind HOME at import, so an eager import would bind the developer's real home and defeat per-worker HOME isolation.
       The cost of importing the three command modules is about 0.38 s and 712 modules, and after `tests.conftest` loads, `specify_cli` is not yet in `sys.modules` — so importing them for every session is also an NFR-003 cost for sessions that never touch the charter commands.
       Required design: wrap only what is already imported, and catch later imports. The charter package `__init__.py` imports all three command modules, so "is `specify_cli.cli.commands.charter` in `sys.modules`" is all-or-nothing. In the autouse fixture: if the package is in `sys.modules`, wrap the three modules now. If it is not, the test has not imported the charter commands yet; install a cheap hook for the duration of the test that wraps them as soon as they are imported (for example a `sys.meta_path` finder or a post-import check that fires on `specify_cli.cli.commands.charter`), or an equivalent mechanism you can show is correct. A test that imports the package inside its body and then invokes a guarded command must still be caught; the planted `late_import` case in T011 proves exactly that. Document the mechanism in the module docstring and record the measured per-test overhead.
     - The wrapper: `def wrapper(start: Path) -> Path:` compute `resolved = Path(start).resolve()`; if `resolved == INVOKING_CHECKOUT or INVOKING_CHECKOUT in resolved.parents`, append a violation (the probed path) to the per-test list; then `return real(start)` — always call through, propagate the real result or exception unchanged.
     - After `yield`, if violations were recorded, `pytest.fail(...)` with ONE message:
       `"<nodeid> reached the charter write guard with the process working directory inside the invoking checkout (<path>). The test passes from a repository root checkout and fails from a linked worktree. Request the `charter_cwd_isolation` fixture and call it with the test tmp project before invoking generate/synthesize/resynthesize."`
  3b. Failing at teardown is deliberate: raising inside the wrapper would be swallowed by `CliRunner` into `result.exception` and surface as a confusing exit-code assertion.
  4. No marker, environment variable or list that turns the tripwire off for a test. The legitimate tests that run a guarded command from a real linked worktree build it under tmp, outside `INVOKING_CHECKOUT`, so they never trip it. Edge: if pytest's base temp directory is configured inside the checkout, tmp paths would count as "inside"; exclude the session's base temp (`tmp_path_factory.getbasetemp()`) from the inside-check and add a unit test for that predicate.
  5. Extract the predicate (`_is_inside_invoking_checkout(path, basetemp) -> bool`) and the message builder as small pure functions and unit-test them directly in the tripwire test file (cheap, fast-tier), separately from the subprocess session.
  6. Full annotations, `.venv/bin/python -m mypy --strict tests/_support/charter_cwd_tripwire.py` clean, complexity well under 15. Do not write the literal `make test-fast` anywhere in this module or its test file: that literal mints a new rule in the release pinning inventory (research.md R-04).
  7. Register the plugin in `tests/conftest.py`. T011's tests turn green.

### Subtask T013 – Coverage test: every cwd-probing guard call site is watched

- **Purpose**: A fourth guarded command added later must not escape the tripwire silently (non-vacuity: the tripwire's floor).
- **Files**: the tripwire test file.
- **Steps**:
  1. Parse every module under `src/specify_cli/cli/commands/charter/` with `ast`. Collect modules containing a call to `resolve_charter_write_root` whose argument is `Path.cwd()` (attribute call `cwd` on name `Path`, no arguments).
  2. Assert that set equals `WATCHED_MODULES` (as module names) and that it is non-empty with at least the three known modules — a concrete floor, so an AST pattern that silently matches nothing fails.
  3. Self-mutation for this check: run the collector function over a synthetic source string that contains such a call in a fake module and assert it is found; and over one that calls the guard with another argument (as `activate.py` does with a resolved root) and assert it is not.
  4. Also assert at runtime that, inside a test, each watched module's `resolve_charter_write_root` attribute is the tripwire wrapper (not the original).

### Subtask T014 – Bounded straggler run

- **Purpose**: The known offender list came from two issues and one linked-worktree run. With the tripwire on, the same set is visible from any checkout; find what was missed (C-005).
- **Steps**:
  1. Build the file list once: `grep -rlE "commands\.charter|charter_app|charter\.app|charter import app" tests --include="test_*.py"`. This is a named-file run, permitted by C-006; it is not a directory sweep. Expect about 110 files and a few minutes with `-n 4 --dist loadfile`. Check machine load first and lower `-n` if the machine is busy. Likely stragglers found by reading, not by running: `tests/integration/test_quickstart_end_to_end.py:139-155` (slow), `tests/specify_cli/cli/commands/charter/test_activate_preserve.py:302`, `tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py:244`. `tests/e2e/test_charter_epic_golden_path.py` uses a subprocess, which the tripwire cannot see.
  2. Run it once with the tripwire on. Collect every tripwire failure.
  3. For each straggler: adopt `charter_cwd_isolation` (same pattern as WP02), re-run only that file. Record each file in the Activity Log as an out-of-map edit with the rationale "straggler found by the tripwire".
  4. Failures that are not tripwire failures: classify per the baseline-red rule (does it fail on `issue-5317-charter-test-cwd-isolation` without your change? is it a venv artefact of the lane, like `test_interview_mapping_mission_alias`?). Do not fix unrelated reds; report them.
  5. Do not repeat the wide run after fixing; re-run only the files you changed.

### Subtask T015 – No-exemption assertion, verification, hand over

- **Steps**:
  1. Add a test that the tripwire module exposes no opt-out: assert the module source registers no pytest marker and reads no environment variable (a simple AST or text check on `tests/_support/charter_cwd_tripwire.py` for `os.environ`, `getenv`, `iter_markers`, `get_closest_marker`), with a self-mutation case showing the check fires on a synthetic source that does contain one. FR-006.
  2. Final targeted run from the lane:

     ```bash
     pytest tests/specify_cli/cli/commands/charter/test_charter_cwd_tripwire.py \
            tests/specify_cli/cli/commands/charter/test_charter_cwd_isolation.py \
            tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py \
            tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py \
            tests/agent/cli/commands/test_charter_cli.py \
            tests/consolidation/test_profile_charter_e2e.py \
            tests/release/test_pinning_inventory_fresh.py -q
     ```
  3. `ruff check`, `ruff format --check --force-exclude`, `.venv/bin/python -m mypy --strict` on the two new files. `python scripts/ci/derive_pinning_inventory.py --check` exits 0 (no new inventory rule minted).
  4. `git diff --stat issue-5317-charter-test-cwd-isolation -- src/` empty.
  5. Activity Log: measured import cost and self-test run time, the straggler list, out-of-map edits with rationale, commands and counts.

## Test Strategy

Red-first: T011's file is committed before the plugin. The tripwire's proof is the inner subprocess session (offenders caught, clean neighbours pass), the pure-function unit tests, the coverage test with its floor and self-mutation, and the clean straggler run.

## Risks & Mitigations

- **Tripwire turns unrelated tests red across the suite** → that is the point for real leaks; T014 finds them before the PR does. Anything else means the inside-check is wrong (base temp inside the checkout, symlinked paths): fix the predicate, never add an exemption.
- **Import-time side effects** → no `specify_cli` import at plugin top level (HOME isolation); wrap lazily; measure and record per-test overhead.
- **Inner subprocess session is slow** → keep to one inner session; if it cannot be made to work cleanly, stop and report the obstacle rather than replacing it with an in-process trick that needs an opt-out.
- **Tests that legitimately run from a real linked worktree** (`test_charter_write_root_4785.py`, `test_synthesize_freshgate_4785.py`, WP01's reproduction) → they build under tmp; confirm they stay green with zero diff.
- **Windows path semantics** → compare resolved `Path` objects, not strings.

## Review Guidance

- Check out T011's commit alone: the outer test is red on outcome counts.
- Mutate the tripwire locally (make the predicate always `False`): the self-mutation tests must go red. Remove one module from `WATCHED_MODULES`: the coverage test must go red. Revert both.
- Confirm the wrapper always calls through and returns/raises the real result (read the code; C-002).
- Confirm there is no opt-out of any kind.
- Confirm the straggler run was done once, its output is summarised, and unrelated reds are classified, not fixed.
- Confirm the measured import cost and self-test time are recorded.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last). Append at the end, format `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`, UTC.

- 2026-10-04T12:11:55Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status. Record subtask completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.
