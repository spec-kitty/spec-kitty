---
work_package_id: WP01
title: The harness temp root
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-002
- NFR-003
- NFR-004
- C-004
- SC-001
- SC-002
planning_base_branch: issue-7076-test-harness-temp-ceiling
merge_target_branch: issue-7076-test-harness-temp-ceiling
branch_strategy: Planning artifacts for this mission were generated on issue-7076-test-harness-temp-ceiling. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7076-test-harness-temp-ceiling unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-harness-temp-ceiling-01M6G9V8
base_commit: 4b9dd1d844dc8503a2ce0dc7df27d9cdbff31d61
created_at: '2026-11-03T08:58:17.142384+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundational
history:
- at: '2026-11-03T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/_support/
create_intent:
- tests/_support/temp_root.py
- tests/_support/test_temp_root.py
- tests/unit/test_harness_temp_root.py
execution_mode: code_change
model: ''
owned_files:
- tests/_support/temp_root.py
- tests/_support/test_temp_root.py
- tests/unit/test_harness_temp_root.py
- tests/conftest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The harness temp root

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

- `tempfile.gettempdir()` is a directory below the run's basetemp in every process the harness
  configures (controller and each xdist worker), and `tempfile.tempdir` is reset so the stdlib
  re-reads the environment instead of its cached value.
- The installed root survives pytest's lazy basetemp reset: after
  `tmp_path_factory.getbasetemp()` has resolved (and removed and recreated a given basetemp), the
  root exists again before any test body runs.
- A `tempfile`-made directory under a *hostile* temp root — one that sits inside a repository —
  resolves to no project root, and the same fixture proves the walk would find that repository
  with the ceiling removed (non-vacuity).
- No second cleanup mechanism: the root lives under the basetemp so `run_basetemp`'s per-run wipe
  and outcome-gated reap govern it.

## Context & Constraints

- Read `kitty-specs/test-harness-temp-ceiling-01M6G9V8/research.md` first: it records the live
  reproduction, the pytest 9.0.3 `TempPathFactory.getbasetemp` source that removes a given
  basetemp, and the decision on Windows `TEMP`.
- `tests/_support/git_ceiling.py` owns the ceiling; this WP owns the temp root that must fall
  inside it. Do not re-derive ceiling entries here.
- `tests/conftest.py::pytest_configure` already calls, in this order: `install_run_basetemp`
  (which sets `config.option.basetemp`), then `install_git_ceilings(harness_git_ceilings(config,
  _worker_home_base(config)), os.environ)`. The temp root install goes **after** both:
  `_worker_home_base` reads `tempfile.gettempdir()`, and it must keep resolving under the platform
  temp root.
- `tests/conftest.py` is under `tests/architectural/test_home_owner_behaviour.py`'s frozen
  definition-order snapshot: it permits exactly one new top-level definition beyond the
  merge-base snapshot, and an *imported call* is not an AST-visible `FunctionDef`. So do the
  work in `tests/_support/temp_root.py` and keep `tests/conftest.py` edits to imported calls plus
  the one autouse hook that the frozen snapshot requires.
- Do not add a per-test fixture. The install is one `mkdir` per process (NFR-002).

## Branch Strategy

- **Strategy**: the mission's lane worktree, branched from the mission branch.
- **Planning base branch**: `issue-7076-test-harness-temp-ceiling`
- **Merge target branch**: `issue-7076-test-harness-temp-ceiling` (the operator merges; this
  mission never pushes `main`)

## Subtasks & Detailed Guidance

### T001 — Red first: `tempfile` escapes the ceiling

Create `tests/unit/test_harness_temp_root.py`. It must be a fast, `unit`-marked module with no
subprocess, and it must be RED before T002/T003 land.

Two tests, minimum:

1. `test_tempfile_root_is_below_the_run_basetemp` — `Path(tempfile.gettempdir())` is
   `tmp_path_factory.getbasetemp()` or a descendant, and a directory made with
   `tempfile.mkdtemp()` inside it is created there. On `main` this fails with `/tmp` vs the run's
   basetemp: that is the defect.
2. `test_a_tempfile_dir_under_a_hostile_temp_root_resolves_no_project` — the non-vacuous proof.
   Build the hostile host *in the test's own tree*: an ambient `.git`/`.kittify` repository with a
   "basetemp" directory inside it, install the harness against that basetemp (the helper from
   T002 plus `install_git_ceilings`), make a directory with `tempfile`, and assert
   `locate_project_root(child)` is `None`. Then remove the ceiling entry and assert the same walk
   returns the ambient repository. Use `monkeypatch.setenv` for the ceiling so the ambient
   harness value is restored at teardown.

Do **not** touch `/tmp`: the test must be correct on a clean host and on this one.

### T002 — `tests/_support/temp_root.py`

Module docstring: what the temp root is, why it must be below the basetemp (ceiling + cleanup),
and the wipe-ordering rule. Then:

- `TEMP_ROOT_VARS = ("TMPDIR", "TEMP", "TMP")` with a comment that `tempfile` reads `TMPDIR`
  first on every platform while Windows child tools read `TEMP`/`TMP`.
- `temp_root_dir(config) -> Path | None`: `<basetemp>/tmp`, or `None` when
  `config.option.basetemp` is unset. Resolve nothing eagerly (the path may not exist yet).
- `install_temp_root(config, environ) -> Path | None`: set the three variables to the root,
  create it (`mkdir(parents=True, exist_ok=True)`), set `tempfile.tempdir = None`, and return the
  root. Idempotent.
- `ensure_temp_root(path) -> Path`: `mkdir(parents=True, exist_ok=True)` and return it — the hook
  T003 calls after the wipe.
- `harness_env(environ=os.environ) -> dict[str, str]`: the subset a from-scratch child must
  inherit — `GIT_CEILING_DIRECTORIES` (`git_ceiling.GIT_CEILING_ENV`) and the three temp
  variables, each only when present in *environ*. WP02 consumes it.

### T003 — Wire it in

In `tests/conftest.py::pytest_configure`, after `install_git_ceilings(...)`, call
`install_temp_root(config, os.environ)` with a comment naming #7076 and the ordering reason.

Then add the one autouse session hook that closes the wipe window:

```python
@pytest.fixture(scope="session", autouse=True)
def _reinstall_temp_root_after_basetemp_reset(tmp_path_factory: pytest.TempPathFactory) -> None:
    """pytest removes and recreates a given basetemp on first use (#7076)."""
    ensure_temp_root(tmp_path_factory.getbasetemp() / "tmp")
```

Fixture placement matters: this hook must run before any test body, so it must be a
`scope="session"`, `autouse=True` fixture in `tests/conftest.py`. Check
`tests/architectural/test_home_owner_behaviour.py` still passes after the edit; if it forbids the
new `FunctionDef`, look at how `tests/_support/` modules are imported there and follow the same
pattern (it must not be argued away — the gate is frozen on purpose).

### T004 — Unit tests for the install

`tests/_support/test_temp_root.py` (fast, `unit`):

- no `basetemp` option → `install_temp_root` returns `None` and leaves `environ` untouched;
- the three variables and `tempfile.tempdir` are set/reset (restore the process state, or use a
  dict passed in as `environ` plus `monkeypatch.setattr(tempfile, "tempdir", ...)`);
- `ensure_temp_root` is idempotent;
- `harness_env` returns only the variables present in the passed mapping.

## Review Guidance

- Is the install really after `install_run_basetemp` and `_worker_home_base`?
- Does any code path call `tempfile` before the eager `mkdir`? (collection/import time)
- Is the wipe window actually closed — i.e. does the hook call `getbasetemp()` itself?
- Does the hostile-temp-root test fail if the install is removed (verify by commenting it out)?

## Definition of Done

- T001's tests were red before T002/T003 and are green after; the red output is quoted in the
  commit message or review notes.
- `uv run pytest tests/unit/test_harness_temp_root.py tests/_support/test_temp_root.py -q` green.
- `uv run pytest tests/architectural/test_home_owner_behaviour.py -q` green.
- No per-test fixture added; no second reaper added.
