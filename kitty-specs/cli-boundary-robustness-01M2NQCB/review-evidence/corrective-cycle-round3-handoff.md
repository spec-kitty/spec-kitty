# Stale-Mock Exhaustive Sweep — Handoff

Mission: Spec Kitty "CLI Boundary Robustness", PR #4674, branch
`issue-4600-cli-boundary-robustness`. Third occurrence of the
`get_project_root_or_exit(..., *, json_output: bool = False)` stale-mock
defect (zero-arg `lambda:` monkeypatches breaking once a real call site
passes `json_output=`). This sweep was tasked to be exhaustive so there is
no fourth round.

## Search methodology (what was actually done, in order)

1. **Confirmed the production signature.** Read
   `src/specify_cli/cli/helpers.py` in the core checkout:
   `get_project_root_or_exit(start: Path | None = None, *, json_output: bool
   = False) -> Path` (line 426).

2. **Found every sibling function in `helpers.py` carrying a comparable new
   keyword-only parameter added by this mission.** Only one sibling exists:
   `exit_git_resolution_failure(exc, project_root, *, json_output: bool =
   False)` (line 464). `git_resolution_failure_message` and
   `check_version_compatibility` take no such keyword.

3. **Located every test file in both checkouts that references
   `get_project_root_or_exit`** via
   `grep -rln "get_project_root_or_exit" tests/` in both `spec-kitty`
   (core) and `review-pr`. Both checkouts produced the *same 14 files*
   (order differed only). For every occurrence in every file, read the
   surrounding code and classified the mock mechanism:
   - `patch(..., return_value=X)` / `patch(...) as m; m.return_value = X`
     → **safe**: `unittest.mock.MagicMock` accepts arbitrary
     positional/keyword arguments regardless of the patched function's
     real signature, so these never break on a new keyword.
   - Named function with an explicit signature (e.g.
     `def fake_project_root(*, json_output: bool = False) -> Path: ...`)
     → **safe**, this is the established fix pattern from
     `tests/agent/test_commands.py` (commit `0e9068060` / `0e906806015e`)
     and `tests/dashboard/test_duplicate_prefix_rendering.py` (commit
     `264f566d7` / `21a5aabec`).
   - Bare zero-arg `lambda: X` → **broken**, raises `TypeError` the moment
     the real call site passes `json_output=`.
   - Direct calls to the real function in `tests/specify_cli/cli/test_helpers.py`
     and `tests/specify_cli/cli/commands/test_cli_boundary_json_seam.py`
     (testing the real function/kwarg contract itself, not mocks) → not
     applicable.

4. **Searched for zero-arg lambdas mocking `exit_git_resolution_failure` /
   `git_resolution_failure_message`** — none found in either checkout;
   both are only exercised via direct calls in `test_helpers.py` and
   `test_cli_boundary_json_seam.py`.

5. **Searched for zero-arg lambdas mocking sibling *path-resolution*
   functions more broadly** (`locate_project_root` and friends), to check
   whether the defect pattern had spread beyond `get_project_root_or_exit`.
   Found several `lambda: X` / `lambda cwd: X` mocks of `locate_project_root`
   across `tests/next/`, `tests/specify_cli/`, `tests/cli/commands/`,
   `tests/audit/`, `tests/architectural/`. Checked `locate_project_root`'s
   three definitions in the source tree
   (`specify_cli/__init__.py`, `specify_cli/core/paths.py`,
   `specify_cli/core/project_resolver.py`) — **none of them gained a
   `json_output` (or any other) new keyword-only parameter as part of this
   mission**; their signatures are `(start=None)` / `(start=None, *,
   stop=None)`, unchanged by the CLI-boundary-robustness work. Out of
   scope for this defect class.

6. **Ran every test file that references `get_project_root_or_exit`** in
   both checkouts (14 files, 197 tests each) to catch any remaining
   `TypeError` before declaring done.

## Sites found (all instances of the defect across the mission's history)

| # | File | Round fixed | Commit (core) | Commit (review-pr) |
|---|------|-------------|----------------|---------------------|
| 1 | `tests/agent/test_commands.py` (3 sites) | 1st | mirrored via `21a5aabec` | `0e9068060` |
| 2 | `tests/dashboard/test_duplicate_prefix_rendering.py` (2 sites) | 2nd | `21a5aabec` | `264f566d7` |
| 3 | `tests/test_dashboard/test_dashboard_preflight.py` lines 212 and 359 | **3rd — this sweep** | `41287f5c6` | `4b991e31c` |

No further broken sites were found in either checkout.

## New fix applied (this sweep)

`tests/test_dashboard/test_dashboard_preflight.py`:

- `test_dashboard_command_persists_passed_advisory_warning` (was line 212):
  replaced `monkeypatch.setattr(dashboard_mod, "get_project_root_or_exit",
  lambda: tmp_path)` with a named `fake_project_root(*, json_output: bool =
  False) -> Path` that appends to a `json_modes` list and returns
  `tmp_path`; added `assert json_modes == [False]`.
- `test_dashboard_command_non_git_project_exits_1_with_git_init_advice`
  (was line 359): same pattern; added `assert json_modes == [False]`
  alongside the existing `assert excinfo.value.exit_code == 1`.

Applied identically in both checkouts (files were byte-identical before
the fix).

## Red/Green evidence

**Core (`spec-kitty`, branch `fix/cli-boundary-robustness`)**

- RED (before fix), both tests:
  ```
  FAILED tests/test_dashboard/test_dashboard_preflight.py::test_dashboard_command_persists_passed_advisory_warning
  FAILED tests/test_dashboard/test_dashboard_preflight.py::test_dashboard_command_non_git_project_exits_1_with_git_init_advice
  E   TypeError: ...<locals>.<lambda>() got an unexpected keyword argument 'json_output'
  2 failed, 10 deselected
  ```
- GREEN (after fix), full file: `12 passed in 30.17s`
- GREEN, all 14 affected test files (197 tests total):
  `197 passed, 1 warning in 350.93s`
- Commit: `41287f5c6` — "test(dashboard): fix stale zero-arg mocks of
  get_project_root_or_exit"

**review-pr (`review-pr`, branch `issue-4600-cli-boundary-robustness`,
backs GitHub PR #4674)**

- RED reproduced independently (stashed the fix, re-ran, restored via
  `git stash pop`):
  ```
  FAILED tests/test_dashboard/test_dashboard_preflight.py::test_dashboard_command_persists_passed_advisory_warning
  FAILED tests/test_dashboard/test_dashboard_preflight.py::test_dashboard_command_non_git_project_exits_1_with_git_init_advice
  E   TypeError: ...<locals>.<lambda>() got an unexpected keyword argument 'json_output'
  2 failed, 10 deselected
  ```
- GREEN (after fix), full file: `12 passed in 29.88s`
- GREEN, all 14 affected test files (197 tests total):
  `197 passed, 1 warning in 346.46s`
- Commit: `4b991e31c` — "test(dashboard): fix stale zero-arg mocks of
  get_project_root_or_exit"

No production code was touched in either checkout. `SPEC_KITTY_ENABLE_SAAS_SYNC`
was not touched. The `review-evidence/` directory and addendum commit
`42757f0ad` in `review-pr` were left untouched — `git log` in `review-pr`
confirms the new commit `4b991e31c` sits on top of `42757f0ad` without
altering it.

## Confidence this is now exhaustive

High, for the following concrete reasons:

1. Every one of the 14 test files in both checkouts that references
   `get_project_root_or_exit` by name was individually read and
   classified (not just grepped for a keyword like `json_output`), so
   mock sites that don't mention `json_output` textually (e.g. the bare
   `lambda: tmp_path` sites) were still caught.
2. The full 197-test run across those 14 files is green in both
   checkouts post-fix — this is the concrete, executable proof, not just
   static classification.
3. The `patch(..., return_value=...)` sites (the majority of the
   remaining sites) are categorically immune to this defect class:
   `MagicMock` accepts any call signature, so no future keyword addition
   to `get_project_root_or_exit` can break them. This means the
   remaining risk surface for *this specific function* is now zero
   (every mock is either a `MagicMock` or a signature-matching named
   function).
4. The only sibling function sharing the new `*, json_output` keyword-only
   parameter (`exit_git_resolution_failure`) was checked and has no lambda
   mocks anywhere in tests/ in either checkout — only direct real-function
   calls.
5. `locate_project_root` and other proximate "project root" resolvers
   were checked for lambda mocks (several exist) but confirmed to not
   have gained any new keyword-only parameter as part of this mission,
   so they are not instances of this defect class — this was verified by
   reading all three `locate_project_root` definitions in the source
   tree, not assumed.

Residual (out-of-scope) risk: if a *future* commit adds a new
keyword-only parameter to some other CLI-boundary function that is
*also* mocked with a bare lambda somewhere in tests/, that would be a
new instance of the general anti-pattern, not a missed instance of this
specific `get_project_root_or_exit` defect. The general anti-pattern
(bare lambdas mocking functions with evolving signatures) is a testing
hygiene issue beyond this task's scope, which was explicitly restricted
to `get_project_root_or_exit` and its `json_output`-shaped siblings.
