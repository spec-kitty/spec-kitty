# Tracer: Tooling Friction

Seeded at planning; appended during implementation.

- 2026-09-26 (specify): `spec-kitty agent mission create --target-branch main` while standing
  on a feature branch bound the mission's planning/merge target to `main` (protected), so
  `spec-commit` refused ("target_branch is protected") even though I was on a non-protected
  feature branch. Fix: recreate WITHOUT `--target-branch` so the target derives from the
  current branch (`branch-context` resolves current→planning→merge all to the feature branch).
  Friction: `--target-branch` conflates "merge destination" with "planning home"; a mission
  created on a feature branch with `--target-branch main` is un-committable without churning
  the mission. Worth an upstream note — the create-time flag combination is a footgun.
- 2026-09-26 (WP01 implement): `plain git push origin <branch>:<branch>` updates the local
  `refs/remotes/origin/<branch>` tracking ref by default (long-standing git behavior, confirmed
  on git 2.43). A first attempt at a "remote-only, pruned local branch" T001 fixture
  (push + `git branch -D <coord>`) therefore did NOT reproduce #4979 — the already-fixed #2614
  `refs/remotes/` scan still found the branch and the test passed even against the OLD
  (unfixed) probe, silently failing to be RED. Fix: the fixture must ALSO
  `git update-ref -d refs/remotes/origin/<coord>` to actually simulate a pruned/stale
  remote-tracking cache. Worth flagging for anyone writing a similar "branch exists only on
  remote" fixture — a bare push+delete is not enough.
- 2026-09-26 (WP01 implement): this worktree has no `.venv` of its own — `.venv/bin/spec-kitty`
  / `.venv/bin/python` resolve to the MAIN repo's shared venv, whose editable install's `.pth`
  points at the main repo's `src/`, not this worktree's. Every pytest/mypy/ruff invocation here
  needed an explicit `PYTHONPATH=<this-worktree>/src` override (verified via
  `python -c "import specify_cli; print(specify_cli.__file__)"`) to exercise the code actually
  being edited rather than the main checkout's copy. `make test-fast` also silently created a
  brand-new, incomplete `.venv` INSIDE the worktree (missing `pytestarch` etc., since it shells
  out to `uv run --frozen` from the worktree cwd) rather than reusing the shared one — removed
  it and ran the equivalent `pytest` invocation directly against the shared `.venv` with the
  `PYTHONPATH` override instead. Worth an upstream note: `make test-fast`/`test-full` are not
  worktree-aware when no per-worktree `.venv` exists.
- 2026-09-26 (WP01 implement): `src/specify_cli/cli/commands/mission_type.py` is listed in
  `pyproject.toml`'s `[tool.ruff.format].exclude` (pre-existing, unrelated to this WP). A plain
  `ruff format --check` on it after my edit reports "would reformat" — this is EXPECTED (the
  whole file has never been ruff-format-clean) and must NOT be "fixed" by running
  `ruff format` on it in this WP: doing so would produce a large unrelated diff and, per the
  local memory note on the ruff-format-exclude ratchet, removing a file from that exclude list
  requires a companion architectural-gate re-run in the SAME commit. Left the file's formatting
  as-is; only ran `ruff check` (lint) + `mypy` on it.
- 2026-09-26 (WP03 implement): a real end-to-end integration test of a flat/legacy mission's
  (`meta.json` with no `coordination_branch`) planning-artifact auto-commit through the actual
  `BookkeepingTransaction.acquire()` machinery still requires a genuinely-existing
  `kitty/mission-<slug>-<mid8>`-shaped branch in the test repo, even though the mission is not
  coordination-topology and the console output prints "legacy path -- mission has no
  coordination_branch". Without that branch, `CoordinationWorktreeUnmaterialized`'s
  `git worktree add` fails outright (exit 128, no ref to check out). With it pre-created, the
  commit silently lands ON that coordination-shaped branch instead of on the passed
  `planning_branch` — i.e. the "legacy path" label in the log line does not mean "commits
  straight to `planning_branch`" the way the WP02/write-path-integrity docstrings imply; a
  scratch coordination worktree is apparently still consulted regardless of the meta.json
  field. This is pre-existing `BookkeepingTransaction`/`CoordinationWorkspace` behavior,
  orthogonal to WP03's demotion guard — worked around by testing the "already-flat-at-HEAD is
  not a demotion" branch directly against the pure `_meta_json_demotion_refusal` helper instead
  of through the full real-commit integration path (see `test_implement_demotion_guard_4979.py
  ::TestMetaJsonDemotionRefusalHelper`). Worth an upstream note for whoever next writes a
  real-commit integration test against a genuinely-flat mission.
- 2026-09-26 (WP02 implement): `_coordination_doctor.py` is ALSO in `[tool.ruff.format].exclude`
  (same pre-existing pattern as WP01's `mission_type.py` note above) — ran `ruff check` + `mypy`
  on it but never `ruff format`. The NEW test file
  (`test_doctor_flatten_remote_reverify_4979.py`) is NOT excluded, so it does need
  `ruff format --check`; my first draft failed that check (long single-line asserts) and
  `ruff format` reflowed them — ran it once before the GREEN commit, not after, to keep the
  diff clean.
- 2026-09-26 (WP02 implement): `make test-fast` reproduces WP01's exact worktree-`.venv`
  footgun (shells out to `uv run --frozen` from the worktree cwd, builds an incomplete
  in-worktree `.venv` missing `pytestarch`, fails on `tests/architectural/conftest.py`'s
  import). Same workaround: ran the equivalent `pytest` invocation directly against the shared
  main-repo `.venv` with `PYTHONPATH=<worktree>/src` instead of `make test-fast` itself.
- 2026-09-26 (WP02 implement): the fastest RED-first fixture for "coordination branch present
  on a remote" is a REAL local bare-repo `origin` (`git init --bare`) + a genuine
  `git push origin <coord-branch>`, then `git branch -D <coord-branch>` + `git update-ref -d
  refs/remotes/origin/<coord-branch>` to strip the local/tracking refs — mirrors WP01's fixture
  note above (a bare push+delete alone is not enough) and runs in well under a second per test
  (no mocking needed, `remote_branch_lookup`'s own subprocess boundary is exercised for real).
- 2026-09-26 (WP02 implement): a blast-radius run over
  `tests/specify_cli/test_meta_fail_closed_full_census_contract.py` surfaced two PRE-EXISTING
  failures (`test_no_unaccounted_load_meta_call_sites`,
  `test_wp09_owned_files_retain_only_silent_sites`) pointing at
  `src/specify_cli/merge/ordering.py::_bake_mission_number_on_primary_tree` — a file WP02 never
  opens. Reproduced identically on the branch tip with no WP02 diff involved, so these are not
  mine to fix. Filed per the charter's binding Pre-existing Failure Reporting Rule:
  https://github.com/spec-kitty/spec-kitty/issues/5135. Separately, the same run showed 3
  pre-existing failures in `tests/cli/commands/test_charter_json_error_contract.py`
  ("Refusing charter write from linked git worktree ... use a repository-root checkout") —
  a worktree-execution-environment artifact (the test assumes a repo-root checkout), not a
  product defect, so no issue filed for that one; noted here instead per the baseline-red
  gotcha's CI-environment-failure category.
