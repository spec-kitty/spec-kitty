---
work_package_id: WP02
title: Migrate the root walks
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- NFR-004
- SC-001
- SC-003
planning_base_branch: issue-7056-ceiling-aware-ancestor-walk
merge_target_branch: issue-7056-ceiling-aware-ancestor-walk
branch_strategy: Planning artifacts for this mission were generated on issue-7056-ceiling-aware-ancestor-walk. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7056-ceiling-aware-ancestor-walk unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 2 - Migration
history:
- at: '2026-11-02T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/specify_cli/core/test_ceiling_root_walks.py
- tests/charter/test_ceiling_root_walks.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/checkout_identity.py
- src/specify_cli/core/ledger_posture.py
- src/specify_cli/task_utils/support.py
- src/specify_cli/context/middleware.py
- src/specify_cli/mission_metadata.py
- src/specify_cli/migration/legacy_charter_gate.py
- src/specify_cli/coordination/legacy_resolution.py
- src/specify_cli/gitignore_manager.py
- src/specify_cli/bootstrap/env_file.py
- src/specify_cli/charter_runtime/lint/checks/org_layer.py
- src/specify_cli/cli/commands/regen.py
- src/charter/activation/context_renderers/catalog_diagnosis.py
- src/charter/activation/neutrality/lint.py
- src/runtime/next/_internal_runtime/planner.py
- tests/specify_cli/core/test_ceiling_root_walks.py
- tests/charter/test_ceiling_root_walks.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Migrate the root walks

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `specify_cli`'s `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

- Every root walk listed in the spec's FR-003/FR-004/FR-005 uses
  `kernel.ancestor_walk` and honours `GIT_CEILING_DIRECTORIES`.
- Each walk has a red-first test showing that an ambient repository above the ceiling
  is not adopted, and that a repository *below* the ceiling still is.
- With the variable unset, every walker's existing unit module is green: zero behaviour
  change on a normal host.

## Context & Constraints

- Source of truth for the census: `research.md` D-2 (the "Root walks — migrate" table)
  and the spec's FR-003/FR-004/FR-005.
- The primitive is `kernel.ancestor_walk` (WP01). Its contract is
  `contracts/kernel-ancestor-walk.md`.
- Do not touch the frozen upgrade migrations (`m_0_6_7`, `m_0_9_2`, `m_0_14_0`) — the
  gate exempts them and research D-2 says why.
- `specify_cli/core/paths.py`'s four walks are in WP01's file ownership but are
  migrated by this WP; coordinate by editing only the walk bodies, not the
  `git_ceiling_dirs` shim.

## Branch Strategy

- **Strategy**: the mission's lane worktree, branched from the mission branch.
- **Planning base branch**: `issue-7056-ceiling-aware-ancestor-walk`
- **Merge target branch**: `main` (the operator merges; this mission never pushes it)

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: the `.git` walks

- **Purpose**: prove each leak before fixing it.
- **Steps**: create `tests/specify_cli/core/test_ceiling_root_walks.py`. One fixture
  builds `<tmp>/outer/.git` (a real repo boundary: `HEAD` file) and `<tmp>/outer/work`,
  then sets `GIT_CEILING_DIRECTORIES=<tmp>` via `monkeypatch.setenv`. Parameterize over
  the entry points:
  `locate_project_root`, `resolve_canonical_root`, `get_status_read_root`,
  `is_worktree_context`, `task_utils.support.find_repo_root`,
  `core.checkout_identity.resolve_checkout_identity`,
  `mission_metadata._has_no_git_anchor`,
  `migration.legacy_charter_gate.find_checkout_root`,
  `coordination.legacy_resolution`'s worktree resolution (patch the subprocess seam),
  `gitignore_manager._has_git_control_path`, `bootstrap.env_file._find_repo_root`.
  Each case asserts the ambient repo above the ceiling is **not** returned/adopted, and
  a second case asserts a repo created *inside* the test tree below the ceiling is
  still found.
- **Files**: `tests/specify_cli/core/test_ceiling_root_walks.py`
- **Parallel?**: no — it is the red commit.
- **Notes**: `legacy_resolution` shells out to git; patch its `subprocess.check_output`
  seam rather than running git, and keep the test unit-fast.

### Subtask T002 – Red-first: the `.kittify`-only and semantic walks

- **Purpose**: same proof for the marker-only walks and the `charter`/`runtime` ones.
- **Steps**: create `tests/charter/test_ceiling_root_walks.py` covering
  `core.ledger_posture._walk_up_to_kittify_marker`,
  `context.middleware._find_repo_root` (monkeypatch `Path.cwd`),
  `charter_runtime.lint.checks.org_layer._find_repo_root_from_drg` (monkeypatch cwd),
  `runtime.next._internal_runtime.planner._infer_project_root`,
  `charter.activation.context_renderers.catalog_diagnosis`'s project-layer lookup,
  `charter.activation.neutrality.lint._find_repo_root`,
  `cli.commands.regen._repo_root`.
- **Files**: `tests/charter/test_ceiling_root_walks.py`
- **Parallel?**: no.
- **Notes**: where the walk is not importable without heavy context (regen's typer
  command), test the module-private helper directly — that is the entry point the
  product uses.

### Subtask T003 – `paths.py` and `support.py`

- **Steps**: `locate_project_root`, `resolve_canonical_root`, `get_status_read_root`
  and `is_worktree_context` iterate `iter_ancestors(...)`; remove their local
  `git_ceiling_dirs()` calls (the primitive reads it). `support.find_repo_root`'s
  fallback does the same. Preserve every existing break/continue rule and every
  docstring statement about the ceiling.
- **Files**: `src/specify_cli/core/paths.py`, `src/specify_cli/task_utils/support.py`
- **Parallel?**: no.
- **Notes**: `stop=` stays (C-005 defers its removal) — keep the boundary check.

### Subtask T004 – the `.git`/`.kittify` walks

- **Steps**: replace each inline loop with `find_ancestor(start, predicate)` (or
  `iter_ancestors` where the loop body has a `break` that is not "stop at the first
  hit"): `checkout_identity._resolve_invocation`, `mission_metadata._has_no_git_anchor`,
  `legacy_charter_gate.find_checkout_root`,
  `coordination.legacy_resolution`'s worktree walk, `gitignore_manager._has_git_control_path`,
  `bootstrap.env_file._find_repo_root`, `ledger_posture._walk_up_to_kittify_marker`,
  `context/middleware._find_repo_root`, `org_layer._find_repo_root_from_drg`.
- **Files**: the nine files above.
- **Parallel?**: partly — the files are disjoint, but keep it one commit for review.
- **Notes**: `env_file.py` imports `kernel.ancestor_walk` only (never
  `specify_cli.core.paths`); its docstring's "not importable here" note needs a small
  update to say the kernel walk is. `mission_metadata` keeps `_GitRefuses` untouched.

### Subtask T005 – `charter`, `runtime`, `regen`

- **Steps**: migrate `catalog_diagnosis`'s `next(...)` expression to
  `find_ancestor(project_dir, lambda p: (p / ".kittify").is_dir())`,
  `neutrality.lint._find_repo_root` to `find_ancestor(start, pyproject predicate)`,
  `planner._infer_project_root` to an ordered predicate walk (`.kittify` first, then
  the `kitty-specs` parent rule — keep both rules in one predicate so the order is
  preserved), and `regen._repo_root` to two bounded walks.
- **Files**: `src/charter/activation/context_renderers/catalog_diagnosis.py`,
  `src/charter/activation/neutrality/lint.py`,
  `src/runtime/next/_internal_runtime/planner.py`, `src/specify_cli/cli/commands/regen.py`
- **Parallel?**: yes — disjoint files from T004.
- **Notes**: `charter`/`runtime` may import `kernel` (layer rule); confirm with
  `tests/architectural/test_layer_rules.py` and
  `tests/architectural/test_charter_no_specify_cli_import.py`.

### Subtask T006 – Regression pass

- **Steps**: with `GIT_CEILING_DIRECTORIES` unset, run each migrated walker's existing
  unit module plus the two new ceiling modules; record the exact commands and results
  in the PR's `## Tests run`.
- **Files**: n/a (verification).
- **Parallel?**: no.
- **Notes**: no full heavy suite. If a module is slow, run the specific test ids.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/core/test_ceiling_root_walks.py \
  tests/charter/test_ceiling_root_walks.py -q
uv run --frozen pytest tests/specify_cli/core/test_paths.py \
  tests/specify_cli/test_paths.py tests/specify_cli/core/test_checkout_identity.py \
  tests/specify_cli/test_mission_metadata.py tests/specify_cli/migration \
  tests/specify_cli/test_gitignore_manager.py tests/specify_cli/bootstrap \
  tests/unit/test_ledger_posture.py tests/specify_cli/context -q
uv run --frozen pytest tests/architectural/test_layer_rules.py \
  tests/architectural/test_charter_no_specify_cli_import.py \
  tests/architectural/test_bootstrap_import_purity.py -q
uv run --frozen mypy src/kernel src/specify_cli/core src/charter/activation src/runtime/next
uv run --frozen ruff check src tests
```

(Adjust module paths to the real test locations; the repo has several and the plan
names the classes, not every file.)

## Risks & Mitigations

- Behaviour drift on a host with no ceiling → T006 regression pass.
- A walk whose loop body is not "first match wins" → use `iter_ancestors` and keep the
  body; the primitive does not force a predicate shape.
- `catalog_diagnosis` silently returning `None` earlier than before → keep the
  `project_dir` inclusion and test the below-ceiling case.

## Review Guidance

- For each migrated function, diff the *decision rules*: the marker, the break,
  the continue and the return value must be identical to before; only the candidate
  source changed.
- Confirm every test fails on the pre-migration parent commit (check the red commit).
- Confirm `git_ceiling_dirs()` is read nowhere in the migrated modules except through
  the primitive.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
