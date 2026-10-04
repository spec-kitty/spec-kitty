# Design decisions — charter-test-cwd-isolation

- 2026-10-04 — Do not re-point the guard at the resolved project root. Repository-root resolution follows a linked worktree to the repository root checkout, so the guard has to probe the process working directory; honouring a patched root would hide the condition it exists to catch.
- 2026-10-04 — Do not stub the guard in tests. Isolation moves the process into the test tmp project so the real guard still runs.
- 2026-10-04 — Opt-in, not suite-wide: `test_charter_json_error_contract.py` has tests that need the invoking checkout's working directory.
- 2026-10-04 — Dry-run smoke test: test-only remedy, guard unchanged (decision `01M43CMN0GADTHK0Q378QYK2WE`, resolved by the orchestrator on the operator's delegation; reversible at pull-request review).
- 2026-10-04 — #5317's acceptance-test half is recorded as verified with no work: not reproducible on current `main` or at the issue's base commit.
- 2026-10-04 — Recurrence check is a runtime tripwire (autouse call-through wrapper on the guard, failure at teardown), not a static census. The post-spec review showed five patch/invoke spellings, 21 files using the seam and mixed files; a per-file static check is evadable. No exemption mechanism.
- 2026-10-04 — Shared support goes in `tests/_support/` (existing `pytest_plugins` home), not in the 2,300-line `tests/conftest.py`.
- 2026-10-04 — Tripwire self-tests use a plain pytest subprocess (the `test_p0_repro.py` pattern), not `pytester`, which the repository deliberately does not enable.
- 2026-10-04 — The tripwire plugin must not import `specify_cli` at top level: plugin modules load before the isolated HOME is set. It wraps already-imported command modules and catches later imports.
- 2026-10-04 — Chdir-only, no-mock tests are left alone; the shared fixture is for tests that patch `find_repo_root`.
- 2026-10-04 — Late imports are caught with a per-test `sys.meta_path` finder that wraps the three command modules right after the charter package executes. Patching the guard at its source would not work (the command modules import the name), and checking `sys.modules` at teardown would be too late.
- 2026-10-04 — The plain helper behind the fixture is private (`_point_charter_commands_at`), so test files cannot bypass the fixture.
- 2026-10-04 — Pre-PR fold: the tripwire watches every caller of the guard, including `activate`/`deactivate`. The spec had put those outside the pattern; the violation rule is on the probed path, so watching them is correct for every call shape and closes the same leak there.
- 2026-10-04 — Pre-PR fold: the two new test files live in `tests/charter/` because `tests/specify_cli/cli/commands/charter/` is outside the per-PR test matrix; the tripwire's own proof should run on every PR.
- 2026-10-04 — Pre-PR fold: the tripwire owns a private `MonkeyPatch`, re-wraps on reload, and a suite check reserves its fixture name, after review showed three ways a test could silently defeat it.
