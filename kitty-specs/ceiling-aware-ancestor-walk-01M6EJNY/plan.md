# Implementation Plan: One ceiling-aware ancestor walker

**Branch**: `issue-7056-ceiling-aware-ancestor-walk` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/ceiling-aware-ancestor-walk-01M6EJNY/spec.md`
**Input**: Mission specification from `kitty-specs/ceiling-aware-ancestor-walk-01M6EJNY/spec.md`; discovery findings in `research.md`

## Summary

Move every repo/project-root ancestor walk in `src/` onto one ceiling-aware walk
primitive at the `kernel` floor, so `GIT_CEILING_DIRECTORIES` bounds discovery for all
of them and not just the three walks #7022 fixed. Then add an architectural gate that
rejects a newly hand-rolled `[p, *p.parents]` walk outside the primitive, with a
shrink-only exemption list for the walks that are not root walks. Item 2 of the issue
(exact git ceiling semantics) is settled as the primitive's documented contract plus
tests; items 3/4 are reduced to the one provably safe fixture removal, with the rest
named in the PR's `## Deferred` section and a follow-up issue.

## Technical Context

**Language/Version**: Python 3.11 (repo `requires-python`), stdlib only for the new module
**Primary Dependencies**: none new; `pathlib`, `os` only in `kernel.ancestor_walk`
**Storage**: N/A (filesystem walks only)
**Testing**: pytest; unit tests per walker plus a new architecture gate under `tests/architectural/`
**Target Platform**: all platforms the CLI ships for (POSIX + Windows; `os.pathsep`, `Path.resolve`)
**Project Type**: single Python package stack under `src/` (`kernel` ← `charter` ← `runtime`/`mission_runtime` ← `specify_cli`)
**Performance Goals**: one environment read and at most one `resolve()` per walk; no new subprocess
**Constraints**: no upward import from `kernel`; ceiling read per call (monkeypatchable); zero behaviour change with the variable unset; shipped ceiling reading kept (item 2)
**Scale/Scope**: 18 root walks migrated, 1 new module, 1 new gate, 1 new test module per concern

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the walk becomes the one authority; `git_ceiling_dirs` keeps its name as a delegating shim rather than being duplicated.
- **Architectural alignment / layer rules** — the primitive lives in `kernel`; no upward imports (`tests/architectural/test_layer_rules.py`). PASS.
- **ATDD-first / red-first** — a red test per walker lands before the migration commit that fixes it.
- **Change-apply-smallest-viable-diff / locality of change** — one primitive plus mechanical per-walker edits; no signature changes beyond delegation; nothing frozen (no `services/`, no `contracts/`) is touched.
- **Canonical sources** — templates for spec/plan/tasks come from the pack, not from an older mission.
- **Architectural gate discipline** — the new gate is a real negative invariant with a positive control and a shrink-only allowlist (no vacuous pass).
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — run the affected unit suites and the architectural gate only; CI owns the full sweep.
- **TDD/red-first, DIRECTIVE_034** — each defect gets its failing test through the pre-existing entry point before the fix.
- **Glossary** — "root walk" and "ceiling" are defined in the spec, matching `tests/_support/git_ceiling.py`'s existing vocabulary.

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ceiling-aware-ancestor-walk-01M6EJNY/
├── plan.md              # this file
├── research.md          # discovery findings (D-1 … D-7)
├── spec.md              # the specification
├── contracts/
│   └── kernel-ancestor-walk.md   # the primitive's public contract
├── tasks.md             # work packages
└── traces/              # approach, design-decisions, tooling-friction
```

### Source Code (repository root)

```
src/kernel/ancestor_walk.py                      # NEW — the primitive + the one env read
src/specify_cli/core/paths.py                    # locate_project_root / resolve_canonical_root /
                                                 #   get_status_read_root / is_worktree_context delegate
src/specify_cli/task_utils/support.py            # find_repo_root fallback delegates
src/specify_cli/core/checkout_identity.py        # .git walk
src/specify_cli/core/ledger_posture.py           # .kittify-only walk
src/specify_cli/context/middleware.py            # .kittify-only walk
src/specify_cli/mission_metadata.py              # _has_no_git_anchor
src/specify_cli/migration/legacy_charter_gate.py # find_checkout_root
src/specify_cli/coordination/legacy_resolution.py# worktree walk
src/specify_cli/gitignore_manager.py             # _has_git_control_path
src/specify_cli/bootstrap/env_file.py            # _find_repo_root
src/specify_cli/charter_runtime/lint/checks/org_layer.py
src/specify_cli/cli/commands/regen.py            # dev-checkout root
src/charter/activation/context_renderers/catalog_diagnosis.py
src/charter/activation/neutrality/lint.py        # pyproject root walk
src/runtime/next/_internal_runtime/planner.py    # _infer_project_root

tests/kernel/test_ancestor_walk.py               # primitive contract (FR-001/002/006)
tests/specify_cli/core/test_paths.py             # existing ceiling tests extended
tests/architectural/test_no_hand_rolled_root_walks.py       # the gate (FR-007/008)
tests/architectural/_hand_rolled_root_walk_scan.py          # scanner + exemption list
tests/unit/workspace/test_root_resolver.py       # fixture removal (FR-009)
```

**Structure Decision**: single project; the new module joins the existing `kernel`
floor next to `kernel/paths.py` and `kernel/git_topology.py`, which host the other
cross-package path/environment primitives for the same reason (both `charter` and
`runtime` need them and may not import `specify_cli`).

## Design decisions

- **DD-1 — Primitive API.** `iter_ancestors(start, *, ceilings=None)` yields the
  resolved start and each parent, stopping *after* the first ceiling entry it yields;
  `find_ancestor(start, predicate, *, ceilings=None)` returns the first candidate the
  predicate accepts (or `None`); `git_ceiling_dirs(environ=None)` is the single reader.
  Callers keep their own marker predicates; only the walk and the ceiling reading are
  shared. This is the smallest shape that removes all duplications without changing any
  caller's decision logic.
- **DD-2 — Ceiling semantics (issue item 2).** A ceiling directory is itself examined
  and the walk stops after it; relative entries are ignored; absolute entries are
  resolved. Pinned by `tests/kernel/test_ancestor_walk.py`. Matching git exactly would
  change `resolve_canonical_root`'s shipped behaviour and needs its own mission (C-002).
- **DD-3 — Env read per call.** No `lru_cache`, no module constant: the harness and
  tests set the variable at runtime, and a cached read would make the ceiling
  order-dependent across the suite (NFR-002).
- **DD-4 — `env_file.py` stays stdlib-narrow.** It keeps its own predicate and error
  behaviour; it imports the primitive (stdlib-only) and nothing from `specify_cli.core`.
  Import purity is already gated by `test_bootstrap_import_purity.py`.
- **DD-5 — Gate shape.** AST scan for `*<expr>.parents` inside a list/tuple and
  `[x] + list(x.parents)`, file+function keyed exemption list, fail on a stale
  exemption. A synthetic positive control keeps it non-vacuous.
- **DD-6 — Harness.** Remove `no_git_ancestry_inside_tmp_path` only if its protection is
  already supplied by the harness ceiling (proved by a control test); the `stop=`
  parameter and `TMPDIR`-under-basetemp are deferred with a follow-up issue.

## Complexity Tracking

No charter violations. No new dependency, no new abstraction layer beyond one module,
no signature change to a public function (only internal delegation).

## Implementation Concern Map

### IC-01 — The primitive and the ceiling contract

- **Purpose**: one stdlib-only, per-call-read, ceiling-aware walk at the `kernel` floor, with its contract written down and tested.
- **Relevant requirements**: FR-001, FR-002, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-003
- **Affected surfaces**: `src/kernel/ancestor_walk.py` (new), `src/specify_cli/core/paths.py` (`git_ceiling_dirs` delegates), `tests/kernel/test_ancestor_walk.py` (new), `kitty-specs/.../contracts/kernel-ancestor-walk.md`
- **Sequencing/depends-on**: none — every other concern imports it
- **Risks**: the contract must stay decision-free (predicate at the call site), or the migration turns into a behaviour rewrite

### IC-02 — Migrate the root walks

- **Purpose**: replace every root walk's inline ancestor loop with the primitive, red-first per walker, so the ceiling actually bounds each one.
- **Relevant requirements**: FR-003, FR-004, FR-005, NFR-004, SC-001, SC-003
- **Affected surfaces**: the 18 files listed in "Source Code" plus each walker's existing unit test module
- **Sequencing/depends-on**: IC-01
- **Risks**: `env_file.py` import purity; `mission_metadata` fail-closed `_GitRefuses` semantics; `resolve_canonical_root`'s submodule boundary; `charter`/`runtime` must import `kernel` only

### IC-03 — The gate and the harness cleanup

- **Purpose**: keep the defect from returning, and retire the one hermeticity mechanism the ceiling makes redundant.
- **Relevant requirements**: FR-007, FR-008, FR-009, SC-002, SC-004, C-004, C-005
- **Affected surfaces**: `tests/architectural/_hand_rolled_root_walk_scan.py` (new), `tests/architectural/test_no_hand_rolled_root_walks.py` (new), `tests/unit/workspace/test_root_resolver.py`
- **Sequencing/depends-on**: IC-02 (the census is only honest once the migrations are in)
- **Risks**: a gate that passes vacuously or an allowlist that is not shrink-only; the fixture may turn out not to be redundant, in which case it stays and the finding is recorded
