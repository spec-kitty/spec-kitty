---
work_package_id: WP01
title: The primitive and the ceiling contract
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-003
planning_base_branch: issue-7056-ceiling-aware-ancestor-walk
merge_target_branch: issue-7056-ceiling-aware-ancestor-walk
branch_strategy: Planning artifacts for this mission were generated on issue-7056-ceiling-aware-ancestor-walk. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7056-ceiling-aware-ancestor-walk unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundational
history:
- at: '2026-11-02T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/
create_intent:
- src/kernel/ancestor_walk.py
- tests/kernel/test_ancestor_walk.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/ancestor_walk.py
- src/specify_cli/core/paths.py
- tests/kernel/test_ancestor_walk.py
- tests/specify_cli/core/test_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The primitive and the ceiling contract

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

- `kernel.ancestor_walk` exists with `GIT_CEILING_ENV`, `git_ceiling_dirs`,
  `iter_ancestors` and `find_ancestor`, exactly as
  `kitty-specs/ceiling-aware-ancestor-walk-01M6EJNY/contracts/kernel-ancestor-walk.md`
  states.
- The ceiling is read on every call (no module constant, no `lru_cache`).
- A ceiling directory is examined and the walk stops after it; relative entries are
  ignored; the start and the ceiling entries are resolved before comparison.
- `specify_cli.core.paths.git_ceiling_dirs` still exists, still returns the same value,
  and its body is a delegation to the kernel reader.

## Context & Constraints

- Read `kitty-specs/ceiling-aware-ancestor-walk-01M6EJNY/research.md` (D-3, D-5) and
  `contracts/kernel-ancestor-walk.md` first.
- The module lives at the `kernel` floor because `charter` and `runtime` need it and
  may not import `specify_cli` (`tests/architectural/test_layer_rules.py`; landscape
  `docs/architecture/00_landscape/README.md`).
- `kernel/paths.py` sets the precedent: an environment variable read at the floor so
  neither package imports the other.
- `specify_cli/bootstrap/env_file.py` will import this module at bare-import time, so
  it must be stdlib-only, side-effect free, and emit no stderr.

## Branch Strategy

- **Strategy**: the mission's lane worktree, branched from the mission branch.
- **Planning base branch**: `issue-7056-ceiling-aware-ancestor-walk`
- **Merge target branch**: `main` (the operator merges; this mission never pushes it)

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first contract test

- **Purpose**: pin the contract before the implementation exists; the test is the
  specification a reviewer can read.
- **Steps**: create `tests/kernel/test_ancestor_walk.py`, import the planned names from
  `kernel.ancestor_walk`, and assert:
  1. no ceiling → the walk reaches the filesystem root (start plus every parent);
  2. a ceiling ancestor → that ancestor is yielded and nothing above it is;
  3. the start itself is a ceiling → yielded, then the walk stops;
  4. a relative `GIT_CEILING_DIRECTORIES` entry is ignored;
  5. a monkeypatched env value takes effect on the next call (per-call read);
  6. `find_ancestor` returns the first accepted candidate and `None` when none is;
  7. a resolved comparison: a ceiling given with a symlinked prefix still matches.
- **Files**: `tests/kernel/test_ancestor_walk.py`
- **Parallel?**: no — it drives T002.
- **Notes**: run it and record the failure (module absent) in the commit message body.

### Subtask T002 – The primitive

- **Purpose**: one walk, one env read, no decisions.
- **Steps**: implement the four names with docstrings that state the ceiling contract
  table from the contract file (including the deliberate deviation from git for a
  ceiling directory that is an ancestor). Use `os.pathsep`, `Path.is_absolute`,
  `Path.resolve`. `iter_ancestors` yields `start.resolve()` first; `find_ancestor`
  short-circuits on the first true predicate.
- **Files**: `src/kernel/ancestor_walk.py`
- **Parallel?**: no.
- **Notes**: no `functools.lru_cache`, no module-level `frozenset()` of parsed entries.
  Keep the module under ~120 lines: it is a walk, not a framework.

### Subtask T003 – `paths.git_ceiling_dirs` delegates

- **Purpose**: keep #7022's public name and its docstring while removing the second
  reading.
- **Steps**: replace the body with `return kernel_ancestor_walk.git_ceiling_dirs()` and
  keep the docstring's contract sentence, adding a pointer to the kernel primitive as
  the single reader. Keep the name in `__all__`.
- **Files**: `src/specify_cli/core/paths.py`
- **Parallel?**: no — same file as nothing else in this WP.
- **Notes**: the four walks in that file are migrated in WP02, not here; do not mix.

### Subtask T004 – Pin the delegation

- **Purpose**: prove the shim is a shim.
- **Steps**: in `tests/specify_cli/core/test_paths.py` add a test that the paths-level
  reader equals `kernel.ancestor_walk.git_ceiling_dirs()` under a monkeypatched
  environment (absolute, relative and empty entries), and one that a `kernel`-level
  patch of the env is visible through the paths-level reader on the next call.
- **Files**: `tests/specify_cli/core/test_paths.py`
- **Parallel?**: no.
- **Notes**: do not restate the #7022 ceiling tests; they already exist in that module.

### Subtask T005 – Layer rule

- **Purpose**: keep the floor honest.
- **Steps**: add a test in the new module that parses
  `src/kernel/ancestor_walk.py`'s imports and asserts none of them starts with
  `charter`, `runtime`, `mission_runtime` or `specify_cli`.
- **Files**: `tests/kernel/test_ancestor_walk.py`
- **Parallel?**: yes — disjoint from T002–T004.
- **Notes**: `tests/architectural/test_layer_rules.py` covers the package graph; this is
  the local, fast assertion that fails closest to the mistake.

## Test Strategy

```bash
uv run --frozen pytest tests/kernel/test_ancestor_walk.py tests/specify_cli/core/test_paths.py -q
uv run --frozen pytest tests/architectural/test_layer_rules.py -q
uv run --frozen mypy src/kernel/ancestor_walk.py
uv run --frozen ruff check src/kernel/ancestor_walk.py src/specify_cli/core/paths.py test
```

- Red first: T001 must fail before T002 exists; the commit that adds T002 must make it
  pass (two commits, red then green).
- No full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Risks & Mitigations

- Caching the env → T001 case 5 fails loudly.
- Accidentally changing `locate_project_root` here → out of scope; WP02 owns it.
- Import cost in `env_file` → keep the module stdlib-only; run
  `tests/architectural/test_bootstrap_import_purity.py`.

## Review Guidance

- Compare the module against `contracts/kernel-ancestor-walk.md` line by line.
- Confirm no predicate/marker knowledge leaked into the primitive.
- Confirm the delegation keeps `git_ceiling_dirs` importable and docstring-accurate.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
