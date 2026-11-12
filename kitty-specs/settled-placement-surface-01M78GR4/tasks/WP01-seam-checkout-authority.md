---
work_package_id: WP01
title: One checkout authority in the seam (enabler)
dependencies: []
requirement_refs:
- FR-001
- C-001
- C-004
- C-005
- NFR-001
subtasks: [T001, T002, T003, T004]
agent: claude
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent:
- tests/kernel/test_git_topology_checkout_root.py
- tests/mission_runtime/test_write_dir_settled_surface_root.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/git_topology.py
- src/mission_runtime/resolution.py
- src/specify_cli/coordination/planning_commit.py
- tests/kernel/test_git_topology_checkout_root.py
- tests/mission_runtime/test_write_dir_settled_surface_root.py
role: implementer
---

# WP01 — One checkout authority in the seam (enabler)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Make `PlacementSeam.write_dir(kind).surface_root` name the checkout that actually contains
`write_dir(kind).path` for declared-PRIMARY kinds, so the seam is the single "which checkout"
authority every later WP delegates to (FR-001, decision `01M78GRZDX410TZ1V8H1ZVC1EM`).

## Context

- After `finalize-tasks` settles a default Mission to `lanes_with_coord`, the repository root checkout
  is back on `create_return_branch` and `.worktrees/<slug>-coord` holds the topic branch
  (`coordination_branch == mission_branch`). See `research/code-grounding.md` §1–§3.
- `src/mission_runtime/resolution.py` `PlacementSeam._declared_primary_write_dir` (≈ line 2642)
  returns `path=self.read_dir(kind)` — the coordination copy for a settled default Mission — but
  `surface_root=get_main_repo_root(self.repo_root)` — the repository root checkout. `path` is then not
  inside `surface_root`: an invariant break (data-model.md, invariant 1).
- COORD kinds are already correct (`establish_coord_write_location`).
- `src/specify_cli/coordination/planning_commit.py` has `_checkout_root_of(path)` (a pure walk up
  `path.parents` looking for `.git`) and `primary_partition_checkout`, which asks the seam's read side
  and walks to the containing checkout. That walk is the right primitive; it belongs in `kernel`
  (the root layer) so `mission_runtime` can use it without a new `mission_runtime → specify_cli` edge
  (the outbound ledger in `tests/architectural/test_layer_rules.py` / `_baselines.yaml` is shrink-only).

Implement with: `spec-kitty agent action implement WP01 --agent claude --mission settled-placement-surface-01M78GR4`

## Branch Strategy

Planning/base branch and final merge target: `fix/7546-settled-placement-surface`. This Mission is
`single_branch`: WPs run in sequence in the repository root checkout; there is no lane worktree.

### Subtask T001: Red — seam reports the wrong checkout for a settled Mission

**Purpose**: pin the defect before fixing it (C-007).

**Steps**:
1. Create `tests/mission_runtime/test_write_dir_settled_surface_root.py`. Reuse the real fixture:
   `from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import make_default_mission, run_finalize, THREE_LANES, _quiet_status_fanout` (import `_quiet_status_fanout` so the autouse fixture applies; it chdirs to the repo root and silences fan-out).
2. Test A (settled): `m = make_default_mission(tmp_path, THREE_LANES)`, `run_finalize(m)` → exit 0. For
   `kind in (SPEC, TASKS_INDEX, WORK_PACKAGE_TASK, PRIMARY_METADATA)`:
   `loc = placement_seam(m.root, m.slug).write_dir(kind)`; assert `loc.path.is_relative_to(loc.surface_root)`
   and `loc.surface_root.resolve() == m.coord_mission_dir.parents[1].resolve()` (the coordination worktree).
3. Test B (positive control, same fixture shape, explicit `single_branch` — `make_default_mission(tmp_path, ("src/one.py","src/two.py"))` settles single_branch): `surface_root` is the repository root checkout and `path` lies inside it.
4. Run it: it must FAIL on Test A and PASS on Test B. Commit the test alone:
   `test(mission_runtime): pin write_dir surface_root for a settled default Mission (#7546)`.

**Validation**: `pytest tests/mission_runtime/test_write_dir_settled_surface_root.py -q` → A red, B green.

### Subtask T002: Hoist the checkout walk into `kernel.git_topology`

**Purpose**: one pure primitive, usable by every layer (tidy-first, behaviour-preserving).

**Steps**:
1. In `src/kernel/git_topology.py` add a public `checkout_root_containing(path: Path) -> Path | None`
   with the exact semantics of `planning_commit._checkout_root_of` (walk `path` and its parents, return
   the first directory with a `.git` entry — file or dir — else `None`). No subprocess. Add it to
   `__all__` (charter C-007 convention for `src/kernel/`). Docstring: a linked worktree has a `.git`
   *file*, the repository root checkout a `.git` *directory*; both count.
2. Replace `planning_commit._checkout_root_of` with the kernel function (delete the private copy;
   update its call site(s)). Grep for other copies: `grep -rn "\.git\").exists()" src/ | head`
   — only converge exact duplicates you find inside files this WP owns; list others in the PR notes.
3. Create `tests/kernel/test_git_topology_checkout_root.py`: repository root checkout (real `git init`),
   a linked worktree (`git worktree add`), a nested subdirectory, and a path outside any checkout
   (`None`).

**Validation**: new kernel tests green; `pytest tests/coordination -q -k planning` green;
`tests/architectural/test_no_dead_symbols.py` (the `__all__` caller gate) green.

### Subtask T003: `_declared_primary_write_dir` returns the containing checkout

**Purpose**: fix the invariant (FR-001).

**Steps**:
1. In `PlacementSeam._declared_primary_write_dir`: keep `path = self.read_dir(kind)` unchanged
   (C-008: byte-identical to `read_dir`). Owned checkout: keep `surface_root = self.owned.owned_root`.
   Otherwise: `surface_root = checkout_root_containing(<nearest existing ancestor of path>)`, falling
   back to `get_main_repo_root(self.repo_root)` when the walk returns `None` (path not yet created and
   no ancestor is a checkout — keep today's answer).
   - `path` may not exist yet (a fresh Mission dir): walk from the nearest existing ancestor.
2. Update the docstring: `surface_root` is the checkout that contains `path` — the repository root
   checkout, an owned checkout, or (for a default Mission before its landing) the checkout holding its
   topic branch.
3. Do not touch the COORD or PUBLISHED arms. Do not read topology here.

**Validation**: T001 Test A now green; Test B still green;
`pytest tests/mission_runtime -q` green; `pytest tests/architectural/test_layer_rules.py tests/architectural/test_write_surface_placement_guard.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_single_mission_surface_resolver.py -q` green.

### Subtask T004: `primary_partition_checkout` delegates to the seam

**Purpose**: converge the existing holder probe on the one authority (C-001).

**Steps**:
1. `planning_commit.primary_partition_checkout(repo_root, slug)` becomes: `holder =
   placement_seam(repo_root, slug).write_dir(MissionArtifactKind.PRIMARY_METADATA).surface_root`;
   return `None` when it resolves to `repo_root` (same contract as today). `planning_checkout_root`
   keeps its "artifact dir must lie in the holder" rule.
2. Keep the docstring's contract (FR-061 / #7372) and say it now reads the seam's `surface_root`.

**Validation**: `pytest tests/coordination -q` (planning commit + transaction tests),
`pytest tests/specify_cli/cli/commands/test_implement_claim.py -q`,
`pytest tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py -q` green.

## Definition of Done

- T001 committed red before the fix; green after.
- `write_dir(kind).path` is inside `write_dir(kind).surface_root` for every kind on the settled fixture.
- No new `mission_runtime → specify_cli` import; `ruff check`, `ruff format --check --force-exclude`,
  `mypy` clean on changed files; complexity ≤ 15.
- Completion recorded with `spec-kitty agent tasks mark-status T001 T002 T003 T004 --status done --mission settled-placement-surface-01M78GR4`.
- Append a tracer line (`spec-kitty agent tracer-append --category approach …`) on anything surprising.

## Risks

- A caller that relied on `surface_root == repo root` for a PRIMARY kind: grep `surface_root` in
  `src/` and confirm every consumer (research found only COORD-kind consumers).
- Windows: `.git` file vs dir — the walk checks `exists()`, which covers both.

## Reviewer Guidance

Verify `path` is unchanged for every arm, that the owned arm is unchanged, that no topology inference
was added (`test_topology_inference_retired.py`), and that the T001 red commit precedes the fix.
