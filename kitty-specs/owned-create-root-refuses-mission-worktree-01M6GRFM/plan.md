# Implementation Plan: Owned create root refuses a Mission worktree

**Branch**: `kitty/mission-owned-create-root-refuses-mission-worktree-01M6GRFM` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/owned-create-root-refuses-mission-worktree-01M6GRFM/spec.md`
**Input**: Mission specification from `kitty-specs/owned-create-root-refuses-mission-worktree-01M6GRFM/spec.md`
**Research**: `kitty-specs/owned-create-root-refuses-mission-worktree-01M6GRFM/research.md`

## Summary

`resolve_owned_create_root` is the one create-level owned-claim minter, and it validates
only the ownership claim, so it admits a registered coordination worktree and a
registered lane worktree. `agent mission create --owned-checkout` therefore scaffolds a
Mission inside another Mission's coordination surface, and the leaf's refusal arrives
only afterwards. This Mission adds the two Mission-worktree legs to the create claim,
reusing the leaf's own coordination predicate and the canonical slug-free lane-worktree
directory grammar, with the leaf's own `OWNED_CHECKOUT_IS_MISSION_WORKTREE` code — one
seam, one code, no new resolver. The startup-gate selector and the Op record commands
inherit it because they consume the same minter; the two docstrings that documented the
residual are retired.

## Technical Context

**Language/Version**: Python 3.11+ (project floor; mission runs on 3.12)
**Primary Dependencies**: typer (CLI), pytest; no new dependency. The work sits inside
`mission_runtime` / `coordination` / `lanes` seams that already exist.
**Storage**: git checkouts, the git worktree registry (`git worktree list --porcelain`),
`kitty-specs/<slug>/meta.json`. No database.
**Testing**: targeted pytest fast suites — `tests/core/test_owned_mission_minter.py`,
`tests/specify_cli/cli/commands/agent/test_mission_create_phases.py`, plus a new
CLI-level red-first module driving the real `agent mission create --owned-checkout`
entry point on a real-worktree fixture; architectural gates
(`test_owned_checkout_single_authority.py`, `test_mission_runtime_surface.py`).
**Target Platform**: CLI on Linux/macOS developer hosts and CI.
**Project Type**: single project (Python package `specify_cli` over the `mission_runtime`
and `coordination` seams).
**Performance Goals**: at most ONE worktree-registry read per minted claim — the budget
the coordination predicate already spends, shared by both legs (NFR-001).
**Constraints**: no new refusal code; no second predicate owner; the leaf
(`resolve_owned_mission` / `_require_not_mission_worktree`) is not modified; the
`test_owned_checkout_single_authority` allowlist stays empty; the create seam still makes
no topology or write-branch decision (C-003).
**Scale/Scope**: two production modules (`core/owned_mission.py`,
`cli/commands/_owned_checkout.py`) plus one new test module; roughly 60 lines of
production change.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The coordination leg reuses `_is_coordination_worktree`; the lane leg reuses `parse_lane_worktree_dir` (the lane-worktree grammar's only owner); the code is `checkout_ownership.OWNED_CHECKOUT_IS_MISSION_WORKTREE`. No new predicate, no new code, no second registry reader. |
| Architectural alignment | The change lands in the create-level minter (`core/owned_mission.py`) and in one docstring of the CLI edge module; no new module, no new public CLI flag, no change to `resolve_owned_mission`. |
| ATDD-first / DIRECTIVE_034 | A CLI-level failing test drives the real `agent mission create --owned-checkout <coord-worktree>` entry point before the refusal exists, asserting the typed code and that nothing is scaffolded. |
| Acceptance-criteria non-vacuity | Every refusal assertion is paired, on the same fixture, with a positive control: an ordinary linked owned checkout (and one that merely lives under `.worktrees/`) still creates. Compound fix proved half by half: reverting the coordination leg and reverting the lane leg each turn a distinct test red. |
| Terminology canon | "owned checkout", "coordination worktree", "lane worktree", "repository root checkout", "Mission worktree" — as defined in `docs/context/topology.md`; no retired naming. |
| DIRECTIVE_024 locality | Edits stay at the create seam's mint and the two docstrings that claim the residual; no opportunistic refactor of the leaf, adoption, or the create command. |
| Standing order 5 (no shrink-only allowlist) | Zero new exclusions in `test_owned_checkout_single_authority.py`; it stays empty. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Validation is the targeted fast suites plus the architectural gates; CI owns the full matrix. |

No violations; `Complexity Tracking` stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/owned-create-root-refuses-mission-worktree-01M6GRFM/
├── spec.md              # What and why (this mission)
├── research.md          # Grounding evidence and the four decisions
├── plan.md              # This file
├── tasks.md             # Work packages
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/specify_cli/
├── core/
│   ├── owned_mission.py            # the create mint gains the two Mission-worktree legs;
│   │                               # _require_not_mission_worktree shares the one classification read
│   └── checkout_ownership.py       # unchanged: the one owner of OWNED_CHECKOUT_IS_MISSION_WORKTREE
├── coordination/surface_resolver.py  # unchanged: classify_worktree_topology owns registry truth
└── cli/commands/
    ├── _owned_checkout.py          # docstring only: retire the "known residual" prose
    └── agent/mission_create.py     # unchanged: already mints before any git operation

tests/
├── core/test_owned_mission_minter.py                          # extend: create-root refusals + positive control
└── specify_cli/cli/commands/agent/test_mission_create_owned_worktree_refusal.py  # new: CLI red-first proof
```

**Structure Decision**: single project. The refusal belongs to the minter that already
owns every create-level claim decision, so the CLI command and the startup selector need
no edit; they inherit it by construction.

## Implementation Concern Map

### IC-01 — One classification read, two Mission-worktree legs at the create claim

- **Purpose**: Make `resolve_owned_create_root` refuse a registered coordination
  worktree and a registered lane worktree with the leaf's typed code, before
  `OwnedCreateRoot` is minted and therefore before any scaffold decision.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003,
  C-001, C-003
- **Affected surfaces**: `src/specify_cli/core/owned_mission.py`
  (`resolve_owned_create_root`, a shared classification helper,
  `_require_not_mission_worktree` re-pointed at that helper, one new refusal-text constant)
- **Sequencing/depends-on**: none
- **Risks**: a second classification read would double the git cost on the startup path
  (mitigated by the shared helper); a lane leg keyed on `WorktreeTopology.LANE_WORKTREE`
  alone would refuse a legitimate owned checkout under `.worktrees/` (mitigated by also
  requiring the directory-name grammar, pinned by the positive control); an unreadable
  registry must refuse rather than admit (NFR-002).
- **Half-by-half proof**: reverting the coordination leg alone turns the coordination
  test red; reverting the lane leg alone turns the lane test red.

### IC-02 — Retire the documented residual and keep the contract prose true

- **Purpose**: The create-level contract as described in the two modules must match what
  the code now does, so the next reader does not re-file this issue.
- **Relevant requirements**: FR-006, SC-003, C-002
- **Affected surfaces**: `resolve_owned_create_root` docstring,
  `resolve_owned_op_record_root` docstring in `src/specify_cli/cli/commands/_owned_checkout.py`
- **Sequencing/depends-on**: IC-01 (the prose describes the behaviour IC-01 delivers)
- **Risks**: over-claiming. The Op commands still validate no Mission, topology or write
  branch; only the Mission-worktree legs are now shared. The docstring must say exactly
  that.

### IC-03 — Red-first proof and regression pins

- **Purpose**: Prove the defect through the production entry point, and pin the admitted
  shapes so the fix cannot regress into a false refusal.
- **Relevant requirements**: FR-005, NFR-004, SC-001, SC-002, SC-003
- **Affected surfaces**:
  `tests/specify_cli/cli/commands/agent/test_mission_create_owned_worktree_refusal.py`
  (new), `tests/core/test_owned_mission_minter.py` (extended)
- **Sequencing/depends-on**: IC-01 (the tests are written first and must be seen red)
- **Risks**: a fixture that materialises a coordination worktree without registering it
  would test nothing (the registry disposes); a lane-worktree fixture named outside the
  lane grammar would silently exercise the wrong leg.

## Complexity Tracking

*No Charter Check violations — this section is intentionally empty.*
