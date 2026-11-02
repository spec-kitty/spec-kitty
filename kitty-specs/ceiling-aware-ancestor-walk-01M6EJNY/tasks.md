# Work Packages: One ceiling-aware ancestor walker

**Inputs**: Design documents from `kitty-specs/ceiling-aware-ancestor-walk-01M6EJNY/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, contracts/kernel-ancestor-walk.md

**Tests**: red-first is required by the charter (ATDD-first, DIRECTIVE_034): a failing
test through the pre-existing entry point lands before the migration that fixes it.

**Organization**: three work packages — the primitive, the migration, the gate. The
migration is one package because every edit is the same mechanical transformation and
splitting it would multiply review overhead without reducing risk; the gate depends on
the migration because its census is only honest once the walks are migrated.

## Path Conventions

- Single project: `src/`, `tests/` (repo-root relative).

---

## Work Package WP01: The primitive and the ceiling contract (Priority: P1)

**Goal**: Add `kernel.ancestor_walk` — one ceiling-aware ancestor walk, one reading of
`GIT_CEILING_DIRECTORIES`, read per call — and make
`specify_cli.core.paths.git_ceiling_dirs` delegate to it.
**Independent Test**: `tests/kernel/test_ancestor_walk.py` proves the contract with no
product caller involved: ceiling examined then stop, per-call env read, relative
entries ignored, resolved comparison, no ceiling = full walk.
**Prompt**: `/tasks/WP01-kernel-ancestor-walk-primitive.md`
**Requirement Refs**: FR-001, FR-002, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-003

### Included Subtasks

T001 Write the red-first contract test `tests/kernel/test_ancestor_walk.py` against the planned API; it fails because the module does not exist.
T002 Implement `src/kernel/ancestor_walk.py` (`GIT_CEILING_ENV`, `git_ceiling_dirs`, `iter_ancestors`, `find_ancestor`) with no upward import and no caching.
T003 Replace `specify_cli.core.paths.git_ceiling_dirs`'s body with a delegate and keep the name importable.
T004 Extend `tests/specify_cli/core/test_paths.py` to pin the delegation (same value, same relative/absolute rules) and the per-call read.
T005 [P] Pin the layer rule: `kernel.ancestor_walk` imports nothing above `kernel` (the existing layer gate already covers it; add the explicit assertion in the new test module).

### Implementation Notes

- The predicate stays at the call site; the primitive must not know what `.git`,
  `.kittify` or `pyproject.toml` are.
- `ceilings=` injection is for tests; production callers omit it.
- Keep the module importable at bare `import specify_cli` time: stdlib only, no side
  effects, no stderr.

### Parallel Opportunities

- T005 runs alongside T002–T004 (separate file, no shared surface).

### Dependencies

- None (starting package). WP02 imports this module.

### Risks & Mitigations

- Contract drift toward decision logic → review the API against
  `contracts/kernel-ancestor-walk.md`; the contract is the review checklist.
- Cached environment breaking the suite's monkeypatching → T001 pins per-call reads.

---

## Work Package WP02: Migrate the root walks (Priority: P1)

**Goal**: Every repo/project-root ancestor walk in `src/` uses the primitive, with a
red-first test per walker proving an ambient repository above the ceiling is no longer
adopted.
**Independent Test**: the per-walker tests in
`tests/specify_cli/core/test_ceiling_root_walks.py`, `tests/charter/…`,
`tests/runtime/…` and each walker's existing module: with
`GIT_CEILING_DIRECTORIES=<tmp>` and `<tmp>/outer/.git`, each entry point behaves as if
the ambient repo did not exist, and still finds a repo below the ceiling.
**Prompt**: `/tasks/WP02-migrate-the-root-walks.md`
**Requirement Refs**: FR-003, FR-004, FR-005, NFR-004, SC-001, SC-003

### Included Subtasks

T006 Red-first: one parametrized ceiling test covering the `.git` walks (`locate_project_root`, `resolve_canonical_root`, `get_status_read_root`, `is_worktree_context`, `find_repo_root`, `checkout_identity`, `mission_metadata._has_no_git_anchor`, `legacy_charter_gate`, `coordination.legacy_resolution`, `gitignore_manager`, `bootstrap.env_file`) — all fail before the change.
T007 Red-first: the `.kittify`-only and semantic walks (`ledger_posture`, `context.middleware`, `org_layer`, `planner._infer_project_root`, `catalog_diagnosis`, `neutrality.lint`, `regen`) in a second test module.
T008 Migrate `specify_cli/core/paths.py`'s four walks and `task_utils/support.py` onto `find_ancestor`/`iter_ancestors`.
T009 Migrate the `.git`/`.kittify` walks of `checkout_identity`, `mission_metadata`, `legacy_charter_gate`, `coordination.legacy_resolution`, `gitignore_manager`, `bootstrap/env_file`, `ledger_posture`, `context/middleware`, `org_layer`.
T010 [P] Migrate the `charter` and `runtime` walks (`catalog_diagnosis`, `neutrality/lint`, `runtime.next._internal_runtime.planner`) and `cli/commands/regen.py`.
T011 Run each migrated walker's existing unit module and the new ceiling modules; confirm zero behaviour change with the variable unset.

### Implementation Notes

- `bootstrap/env_file.py` must not gain a `specify_cli.core` import; import the kernel
  module only (its own docstring explains why).
- `mission_metadata._has_no_git_anchor` keeps its `_GitRefuses` contract: the change is
  only that the walk stops at the ceiling, so an ambient `.git` above it no longer
  makes git's refusal look like a real anchor.
- `resolve_canonical_root` keeps its submodule/`.kittify` boundary and worktree
  pointer-following exactly; only the candidate iteration changes.
- Do not touch the frozen upgrade migrations (see research D-2).

### Parallel Opportunities

- T010 is a disjoint file set from T008/T009 and can proceed concurrently.

### Dependencies

- WP01 (the primitive must exist).

### Risks & Mitigations

- Silent behaviour change with no ceiling → NFR-004 test pass per walker, run with the
  variable unset.
- Import-cycle / layer violation in `charter`/`runtime` → T010 runs
  `tests/architectural/test_layer_rules.py` and `test_charter_no_specify_cli_import.py`.

---

## Work Package WP03: The gate and the harness cleanup (Priority: P2)

**Goal**: An architectural gate that rejects a newly hand-rolled ancestor walk under
`src/`, with a shrink-only, reason-bearing exemption census; and retire the one
hermeticity fixture the ceiling makes redundant, if it truly is.
**Independent Test**: the gate reports zero unlisted hits on the migrated corpus, flags
a synthetic `[start, *start.parents]` walk, and fails on a stale exemption; the
root-resolver tests pass without the removed fixture.
**Prompt**: `/tasks/WP03-hand-rolled-root-walk-gate.md`
**Requirement Refs**: FR-007, FR-008, FR-009, SC-002, SC-004, C-004, C-005

### Included Subtasks

T012 Add `tests/architectural/_hand_rolled_root_walk_scan.py`: fail-closed AST scan for `*<expr>.parents` in list/tuple and `[x] + list(x.parents)`, plus the file+function exemption census with reasons.
T013 Add `tests/architectural/test_no_hand_rolled_root_walks.py`: zero unlisted hits, positive control, stale-exemption failure, non-empty corpus guard.
T014 Evaluate `no_git_ancestry_inside_tmp_path` in `tests/unit/workspace/test_root_resolver.py`; remove it only if the tests still pass and a control shows the harness ceiling provides the protection, and record the finding either way.
T015 File the follow-up issue for the deferred harness items (the `stop=` parameter and `TMPDIR`-under-basetemp) so the PR's `## Deferred` section can cite it.

### Implementation Notes

- Each exemption is `(file, function, reason)`; the scan must be able to say which
  exemption no longer matches (that is the failure mode that keeps the list honest).
- The gate scans `src/` only; `tests/` hand-rolled walks are out of scope (they are not
  product root discovery, and the gate must not become a test-style rule).

### Parallel Opportunities

- T015 is independent of the scan work.

### Dependencies

- WP02 (the census is only honest once the walks are migrated).

### Risks & Mitigations

- Vacuous gate (scans nothing) → explicit non-empty corpus assertion plus the positive
  control.
- Exemption list becoming a dumping ground → shrink-only failure and a reason per entry.
