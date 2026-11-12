---
work_package_id: WP01
title: Lane test invocation and probe
dependencies: []
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-010
- NFR-001
- NFR-004
- C-002
- C-007
planning_base_branch: fix/7547-lane-code-verification
merge_target_branch: fix/7547-lane-code-verification
branch_strategy: Planning artifacts for this mission were generated on fix/7547-lane-code-verification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7547-lane-code-verification unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-11-12T05:35:56Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/lane_invocation.py
create_intent:
- src/specify_cli/lanes/lane_invocation.py
- tests/lanes/test_lane_invocation.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/lane_invocation.py
- tests/lanes/test_lane_invocation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Lane test invocation and probe

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load `spec-kitty charter context --action implement` and read `CLAUDE.md` and `.kittify/charter/charter.md`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission lane-code-verification-01M76AC0`).
- Address every feedback item; record progress with `spec-kitty agent tasks add-history WP01 --mission lane-code-verification-01M76AC0 --note "..."`.

## Review Feedback

*[Filled from the status event log when this WP returns from review.]*

---

## Objectives & Success Criteria

Create the leaf module `src/specify_cli/lanes/lane_invocation.py`, the single authority that:

1. builds a **lane test invocation** (`cwd`, `command`, `env_set`, `env_unset`) for a lane
   or write checkout;
2. **probes** it: a child process started with exactly that `cwd` and environment reports
   where each git-tracked regular package under `<root>/src` would load from →
   `verified` / `foreign` / `unverified`;
3. captures an **evidence tree** (path, HEAD, dirty, probe) through `kernel.git`;
4. decides containment portably (`origin_inside`).

Done when: all subtasks' tests pass, the module has `__all__`, ruff/format/mypy clean,
every function complexity ≤ 15, and the planted-change and lane-venv tests (T001) went
red before the implementation and green after.

Requirements: FR-002, FR-003, FR-004, FR-010, NFR-001, NFR-004, C-002, C-007.

## Context & Constraints

- Spec: `kitty-specs/lane-code-verification-01M76AC0/spec.md`; plan: `plan.md` §Design (read
  the "invocation and probe" bullets carefully: they are the result of a post-plan squad);
  `data-model.md` (`LaneTestInvocation`, `ProbeResult`, `EvidenceTree`); `research.md`
  D1–D3 and the squad dispositions table; `contracts/lane-test-invocation.md` for the
  `to_dict()` shape.
- **Leaf module**: it must not import from `specify_cli.review`, `specify_cli.status`,
  `specify_cli.cli` or any heavy module. Allowed: stdlib, `kernel.git`, `kernel.paths`,
  `specify_cli.lanes.lane_env`. The test command is passed **in** by callers (a string or
  `None`); never read config here (avoids a `lanes`→`review.baseline` import loop).
- Git reads only through `kernel.git` (`tracked_paths`, `status_entries`, `run_git`):
  `tests/architectural/test_git_path_listing_owner.py` has an empty allowlist.
- OS detection only through `kernel.paths.is_windows()` (`tests/architectural/test_os_detection_ban.py`).
- Every public name needs a production caller (dead-symbol gate). WP02/WP03/WP04 add
  the callers; within this WP list in `__all__` only the names those WPs will import:
  `INTERPRETER_REDIRECT_KEYS`, `LaneTestInvocation`, `ProbeStatus`, `ProbeResult`,
  `EvidenceTree`, `build_lane_test_invocation`, `probe_lane_imports`,
  `capture_evidence_tree`, `origin_inside`, `run_environment`. (If the dead-symbol gate
  runs before the callers land, it is expected to flag them; WP02–WP04 resolve it. Do not
  add allowlist entries.)
- Do not edit `pre_review_gate.py` here (WP03 owns it); WP03 moves its strip list onto
  `INTERPRETER_REDIRECT_KEYS`.

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `fix/7547-lane-code-verification`
- **Merge target branch**: `fix/7547-lane-code-verification`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with:

```bash
spec-kitty agent action implement WP01 --agent claude --mission lane-code-verification-01M76AC0
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red tests first (commit before any implementation)

- **Purpose**: pin the user-observable behaviour (C-006, ATDD-first). Commit as its own
  commit, e.g. `test(lanes): pin the lane test invocation and probe (red)`.
- **File**: `tests/lanes/test_lane_invocation.py` (mark `pytest.mark.fast` where cheap;
  child-process tests can stay unmarked/integration as the directory's conventions say —
  check neighbouring tests in `tests/lanes/`).
- **Fixture `scratch_project(tmp_path)`** (realistic, cheap, does NOT use this repo's own `.venv`):
  1. `root/` = `git init`, a commit containing `src/pkg/__init__.py` with `V = 1` and
     `src/pkg/mod.py`; also a loose `src/loose/foo.py` with no `__init__.py`.
  2. `lane/` = `git worktree add` of `root` (a real linked worktree), then plant
     `V = 2` in `lane/src/pkg/__init__.py` (uncommitted is fine).
  3. `root/.venv` = `python -m venv --without-pip root/.venv` (≈0.05 s) plus a `.pth`
     file in its site-packages containing the absolute `root/src` (this is exactly what an
     editable install does). Find site-packages by running the venv interpreter with
     `-c "import sysconfig;print(sysconfig.get_path('purelib'))"`.
- **Tests (all through the public functions, no mocks of the probe internals)**:
  1. *Planted change (SC-001, FR-003)*: `inv = build_lane_test_invocation(lane, command="pytest -q", mission_slug="m-01ABCDEF", lane_id="lane-a")`;
     run `[root/.venv python, "-c", "import pkg; print(pkg.V)"]` with
     `cwd=inv.cwd, env=run_environment(inv, base_env)` → prints `2`; spawn a grandchild from
     that child (`subprocess.run([sys.executable, "-c", "import pkg;print(pkg.V)"])` inside the
     child script) → also `2`. **Same fixture, negative control**: the bare root venv
     interpreter with the inherited environment from `cwd=lane` prints `1`.
  2. *Probe verified*: `probe_lane_imports(inv)` → `status == "verified"`, `origins["pkg"]`
     inside `lane/src`, `"loose"` not probed.
  3. *Probe foreign / verified pair (FR-002, the #1907 case)*: create `lane/.venv` the same
     way with a `.pth` pointing at `root/src`; rebuild the invocation (now no `PYTHONPATH`
     is added because the lane has a venv); probe → `foreign`, `foreign == ["pkg"]`,
     origin under `root/src`. Rewrite the `.pth` to `lane/src` → `verified`. Same fixture.
  4. *Lane-venv copy is foreign (squad T3)*: a `.pth` pointing at a copy of the package in
     `lane/.venv/lib/.../site-packages/pkg` (copy the dir) → `foreign` (containment is
     against `lane/src`, not the lane root).
  5. *Redirect stripping (FR-004, half by half)*: with base env `PYTHONPATH=root/src`,
     `VIRTUAL_ENV=root/.venv`, `UV_PROJECT_ENVIRONMENT=root/.venv`: `run_environment(...)`
     lacks `VIRTUAL_ENV` and `UV_PROJECT_ENVIRONMENT`, has `SPEC_KITTY_TEST_DB_NAME`; and with
     the lane-venv fixture (no `PYTHONPATH` injected) the inherited `PYTHONPATH=root/src` is
     **gone** (assert key absent) and the probe is `verified` — reverting the strip makes it
     `foreign`, so the PYTHONPATH half is not hidden by `env_set`.
  6. *Unverified, never raises (FR-010)*: a project with no `src/` → `unverified` with reason;
     an interpreter path that does not exist → `unverified`; an interpreter stub script that
     sleeps 10 s with `timeout=0.5` → `unverified` with "timed out" in reason (inject the
     timeout, no wall-clock assertion).
  7. *`origin_inside` (NFR-004)*: parametrize `pathmod` over `posixpath` and `ntpath`:
     inside, outside, sibling-prefix trap (`/a/src2` vs `/a/src`), case-insensitive drive on
     `ntpath` (`C:\\Lane\\src\\pkg` vs `c:\\lane\\src`), separators mixed.
  8. *Evidence tree*: `capture_evidence_tree(lane, probe, repo_root=root)` → `head` equals
     `git -C lane rev-parse HEAD`, `dirty is True` (planted change), `path ==
     os.path.relpath(lane, root)` style relative form when under root; absolute when not.
  9. *`to_dict()` shape* matches `contracts/lane-test-invocation.md` keys exactly.

### Subtask T002 – `LaneTestInvocation`, `build_lane_test_invocation`, `run_environment`

- **Steps**:
  1. `INTERPRETER_REDIRECT_KEYS: Final[tuple[str, ...]] = ("PYTHONPATH", "UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV")`
     with a comment citing #2803/#7554 (moved here from `pre_review_gate._UV_ENV_LEAK_KEYS` by WP03).
  2. `@dataclass(frozen=True) class LaneTestInvocation`: `cwd: Path`, `command: str | None`,
     `env_set: Mapping[str, str]` (store as a `types.MappingProxyType` or a sorted tuple of
     pairs to stay hashable/frozen), `env_unset: tuple[str, ...]`, `probe: ProbeResult | None = None`.
     Method `with_probe(probe) -> LaneTestInvocation` (`dataclasses.replace`), `to_dict()`.
  3. `def build_lane_test_invocation(root: Path, *, command: str | None, mission_slug: str | None = None, lane_id: str | None = None) -> LaneTestInvocation`:
     - `env_set` starts with `lane_test_env(mission_slug, lane_id)` when both are non-empty
       (catch the `ValueError` it raises on empty slugs → skip).
     - add `PYTHONPATH=str(root / "src")` when `_source_packages(root)` is non-empty AND
       `_lane_interpreter(root)` is `None` (no venv of its own).
     - `env_unset = INTERPRETER_REDIRECT_KEYS`.
  4. `def run_environment(invocation, base: Mapping[str, str]) -> dict[str, str]`: copy
     `base`, drop `env_unset`, apply `env_set`. This is what the gate passes as `run_env`.
- **Notes**: `command` is a template string (it may contain `{output_file}`); never
  substitute or parse it here.

### Subtask T003 – Probe

- **Steps**:
  1. `class ProbeStatus(StrEnum)`: `VERIFIED="verified"`, `FOREIGN="foreign"`, `UNVERIFIED="unverified"`.
  2. `@dataclass(frozen=True) class ProbeResult`: `status`, `origins: tuple[tuple[str, str], ...]`
     (or a frozen mapping), `foreign: tuple[str, ...]`, `reason: str | None`,
     `interpreter: str | None`; `to_dict()`.
  3. `_source_packages(root) -> tuple[str, ...]`: `kernel.git.tracked_paths(root, pathspecs=["src/*/__init__.py"], glob=True)`
     (check `GitPath`'s API in `src/kernel/git/paths.py`; use its string form), keep entries
     of exactly three segments `src/<name>/__init__.py`, sorted names. A `GitCommandError`
     (not a git checkout) → `()`.
  4. `_lane_interpreter(root) -> Path | None`: `root/.venv/Scripts/python.exe` when
     `kernel.paths.is_windows()` else `root/.venv/bin/python`; return it only if it exists.
  5. `probe_lane_imports(invocation, *, base_env: Mapping[str, str] | None = None, timeout: float = 5.0, runner=subprocess.run) -> ProbeResult`:
     - packages empty → `UNVERIFIED`, reason `"no tracked source-layout packages to probe"`.
     - interpreter = `_lane_interpreter(cwd)` or `Path(sys.executable)`.
     - argv `[interpreter, "-P", "-c", _PROBE_SCRIPT, *packages]` where the script prints
       `json.dumps({name: origin_or_None})` using `importlib.util.find_spec(name)`; for a spec
       with `origin is None` use the first `submodule_search_locations` entry (defensive), and
       catch exceptions per name → `None`.
     - env = `run_environment(invocation, base_env if base_env is not None else os.environ)`,
       `cwd=invocation.cwd`, `capture_output=True, text=True, timeout=timeout`.
     - `TimeoutExpired` / `OSError` / non-zero exit / bad JSON → `UNVERIFIED` with a bounded
       reason (≤ 200 chars) — **never raise**.
     - any name with `None` origin → `UNVERIFIED` ("<name> not importable from the lane
       environment") unless another is foreign (foreign wins).
     - containment: `origin_inside(origin, cwd / "src")`.
- **Notes**: `-P` (Python ≥ 3.11) keeps the cwd off `sys.path`, matching a console-script
  pytest. The CLI's own interpreter is used when the lane has no venv, which is correct: the
  `PYTHONPATH` injected by the invocation is what makes it load the lane.

### Subtask T004 – `origin_inside`

- `def origin_inside(origin: str | os.PathLike[str], root: str | os.PathLike[str], *, pathmod: ModuleType = os.path) -> bool`:
  `a = pathmod.normcase(pathmod.realpath(str(origin)))` only when `pathmod is os.path`
  (realpath of a foreign-OS path is meaningless; for injected `ntpath`/`posixpath` use
  `pathmod.normpath` + `normcase`), same for root; return `a == r or a.startswith(r + pathmod.sep)`.
  Handle `altsep` by `normpath` first. Keep complexity low.

### Subtask T005 – `EvidenceTree`

- `@dataclass(frozen=True) class EvidenceTree`: `path: str`, `head: str | None`,
  `dirty: bool | None`, `probe: ProbeResult`; `to_dict()`.
- `capture_evidence_tree(root: Path, probe: ProbeResult, *, repo_root: Path | None = None) -> EvidenceTree`:
  - `head`: `kernel.git.run_git(root, "rev-parse", "HEAD", check=False)`; non-zero → `None`.
  - `dirty`: `bool(kernel.git.status_entries(root, untracked="normal", optional_locks=False))`;
    `GitCommandError` → `None`.
  - `path`: relative to `repo_root` (posix form) when `root` is under it, else `str(root)`.
  - Never raises.

## Test Strategy

Run (record counts in the WP handoff note):

```bash
uv run --frozen python -m pytest tests/lanes/test_lane_invocation.py tests/lanes/test_lane_db_isolation.py -q
uv run --frozen ruff check src/specify_cli/lanes/lane_invocation.py tests/lanes/test_lane_invocation.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/lanes/lane_invocation.py tests/lanes/test_lane_invocation.py
uv run --frozen mypy src/specify_cli/lanes/lane_invocation.py
uv run --frozen python -m pytest tests/architectural/test_os_detection_ban.py tests/architectural/test_git_path_listing_owner.py -q
```

Run pytest from inside the lane worktree with `PYTHONPATH=src` set explicitly until this
Mission lands (the friction this Mission fixes). Note in the tracer if anything else bites.

## Risks & Mitigations

- `venv` creation in tests on CI: `--without-pip` keeps it fast and offline.
- `tracked_paths` glob semantics: verify `src/*/__init__.py` does not match nested
  `src/a/b/__init__.py` with `glob=True`; filter by segment count anyway.
- Windows: no Windows CI locally; the `pathmod` injection covers NFR-004.

## Review Guidance

- Red-first: the test commit precedes the implementation commit; verify red on the base.
- Non-vacuity: every negative assertion has a same-fixture positive control (tests 1, 3, 5).
- Leaf discipline: `grep -n "^from\|^import" src/specify_cli/lanes/lane_invocation.py` shows
  no `specify_cli.review|status|cli` import.
- The probe never raises (tests 6).

## Activity Log

- 2026-11-12T05:35:56Z – system – Prompt generated via /spec-kitty.tasks
