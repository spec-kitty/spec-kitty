# Implementation Plan: Terminus-Safety Invariant

**Branch**: `issue-4764-terminus-safety-invariant` | **Date**: 2026-09-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/terminus-safety-invariant-01M2XFT7/spec.md`
**Final PR target**: `main` (the mission branch opens a PR to `main`; the operator merges).

## Summary

Establish one **terminus-safety invariant** — every completion command (`merge`, `accept`, `mission close`) *gate-then-mutate(-with-rollback)*. Technical approach: (1) a behavior-preserving **tidy-first enabler** that adds a single shared aggregate reader `mission_terminal_acceptability` to the orchestration-free `status_lanes` module and reroutes the three `specify_cli` terminus commands onto it; (2) an **unconditional merge-ready precondition** in the merge phase caller, hoisted out of the mode-softened evidence gate, that refuses before lane consolidation; (3) a fail-closed **`is_mission_merged` guard** in `mission close` before teardown; (4) a **topology-aware `mission_number` bake** (closing #4474's merge-ready fail-open); (5) a unified **transactional coord-mutation** primitive that rolls consolidation+bake back on a post-mutation failure; (6) direct-on-target **safety + completion affordance** (`merge --skip-lanes`); (7) `mission close` **orphan-branch robustness** (`--json`, doubled-slug fix). Each defect ships with an issue-pinned red-first regression test.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (existing); internal modules only — `specify_cli.merge` (`executor`, `ordering`, `done_bookkeeping`), `specify_cli.policy` (`config`, `merge_gates`), `specify_cli.cli.commands` (`mission_type`, `accept`, `merge`), `specify_cli.coordination` (`teardown`), `specify_cli.status` (facade: `is_mission_merged`, `is_mission_completed`), `specify_cli.status_lanes` (aggregate home), `specify_cli.lanes`. **No new third-party dependency** ⇒ supply-chain-install-safety (DIR-051) is N/A for this plan.
**Storage**: git refs (coordination/lane/target branches) + append-only `status.events.jsonl` + `meta.json`; no database.
**Testing**: pytest — `tests/merge/`, `tests/integration/test_mission_close.py`, `tests/specify_cli/cli/commands/`, `tests/status/`, plus the acceptance suites. Full `tests/architectural/` only for the cross-cutting re-pin companions.
**Target Platform**: Linux / macOS / Windows CLI.
**Project Type**: single (CLI library).
**Performance Goals**: added precondition negligible; `merge`/`close` stay within the < 2 s typical-CLI budget (NFR-004).
**Constraints**: facade-only status imports (battery gate `test_status_module_boundary`); do NOT grow the shrink-only `runtime → specify_cli` layer ledger (aggregate adoption scoped to `specify_cli`); raise `typer.Exit(1)` in-executor (no new uncaught error type — `merge.py:545-554` translates a fixed set); C901 ≤ 15 (extract helpers); ATDD red-first per defect.
**Scale/Scope**: ~8 source files, ~7 work packages, 4 issues closed (#4764, #4765, #4474, #2745).

## Constitution / Charter Check

*GATE: pass before Phase 0; re-check after Phase 1.*

- **Single canonical authority (DIRECTIVE_044).** ✅ The plan adds exactly ONE aggregate reader on top of the already-canonical `status_lanes.is_acceptable_ending`; it retires duplicate terminal-set copies rather than adding a 6th definition. It unifies (not forks) the coord-rollback machinery.
- **Architectural alignment (DIRECTIVE_001).** ✅ All touched modules are top-layer `specify_cli`; the new aggregate lives in the dependency-light `status_lanes`; adoption scoped to protect the shrink-only runtime ledger.
- **ATDD-first (C-011).** ✅ Each WP leads with an issue-pinned `@pytest.mark.regression` red-first test through the pre-existing CLI entry point.
- **Tidy-first / Boy Scout (DIRECTIVE_025) + Locality (DIRECTIVE_024) + Reconcile (RECONCILE_CHANGE_SCOPE_TENSIONS).** ✅ WP01 is a behavior-preserving enabler landed BEFORE the functional preconditions consume it. Campsite scope limited to the terminal-readiness surface.
- **Prefer durable fixes (DIRECTIVE_052 — this mission's own new directive).** ✅ Structural remediation of the class, not four point-fixes; operator-gated fold-vs-defer for #2745 affordances (D6) and the #2745 rollback tail (D5).
- **Close defect classes by construction (DIRECTIVE_043).** ✅ The unconditional precondition makes the wedge unreachable; the red-first tests are the non-vacuous floor.
- **Terminology canon.** ✅ Mission (not feature); no `--feature` flags added; the new `merge --skip-lanes` flag uses canonical vocabulary.
- **No version prescription (C-005).** ✅ `[Unreleased]` CHANGELOG only.

No violations ⇒ Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/terminus-safety-invariant-01M2XFT7/
├── plan.md              # This file
├── research.md          # Phase 0 — root-cause + adversarial-evidence dispositions
├── data-model.md        # Phase 1 — terminal-readiness authority, coord checkpoint, predicates
├── contracts/           # Phase 1 — the behavioral invariant contract
│   └── terminus-safety-contract.md
├── quickstart.md        # Phase 1 — how to exercise the reproductions
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root) — files this mission touches

```
src/specify_cli/
├── status_lanes.py                 # ADD mission_terminal_acceptability aggregate (WP01)
├── status/lifecycle.py             # is_mission_merged / is_mission_completed (readers; consumed via facade)
├── status/doctor.py                # RETIRE duplicate _TERMINAL_LANES / inline terminal set (WP01)
├── policy/merge_gates.py           # de-conflate terminal-lane invariant from evidence-quality gate (WP02)
├── policy/config.py                # MergeGateConfig.mode (warn semantics — read only)
├── merge/executor.py               # merge-ready precondition + coord-transaction rollback (WP02, WP05, WP06)
├── merge/ordering.py               # topology-aware mission_number bake write-back (WP04)
├── merge/done_bookkeeping.py       # post-merge backstop interplay with rollback (WP05)
├── cli/commands/merge.py           # --skip-lanes/--no-lanes flag surface + error translation (WP06)
├── cli/commands/mission_type.py    # close_cmd is_mission_merged guard (WP03); orphan/--json/doubled-slug (WP07)
├── cli/commands/accept.py          # reroute terminal-readiness onto aggregate (WP01); guidance liveness (WP07)
└── coordination/teardown.py        # teardown ordering vs rollback (WP05, read/verify)

tests/
├── merge/test_issue_4764_*.py                 # WP02 red-first
├── merge/test_issue_4474_*.py                 # WP04 red-first
├── merge/ (rollback + resume-coherence)        # WP05
├── integration/test_mission_close.py           # WP03 + WP07 red-first
├── specify_cli/cli/commands/                    # close guard + merge flag CLI tests
└── status/ + unit                               # WP01 aggregate truth-table
```

**Structure Decision**: single-project CLI library; changes are surgical edits to existing modules plus one new pure helper in `status_lanes.py`. No new packages or directories.

## Implementation Concern Map

*(/spec-kitty.tasks translates these concerns into work packages; the mapping below is the intended decomposition.)*

| Concern | FRs | Primary files | Depends on |
|---------|-----|---------------|------------|
| IC-1 Shared terminal-readiness authority (tidy-first enabler, behavior-preserving) | FR-009 | `status_lanes.py`, reroute `merge_gates`/`accept`/`done_bookkeeping`; retire `doctor.py` dup | — |
| IC-2 Merge unconditional merge-ready precondition (warn-hard) | FR-001/002/003/006 | `merge/executor.py` (`_phase_gates_and_state`, extract `_assert_mission_terminal_ready`), `policy/merge_gates.py` | IC-1 |
| IC-3 Mission-close merged guard | FR-004/005 | `cli/commands/mission_type.py` (`close_cmd` non-discard) | IC-1 |
| IC-4 Topology-aware mission_number bake (#4474 merge-ready fail-open) | FR-011 | `merge/ordering.py` | IC-1 |
| IC-5 Transactional coord-mutation rollback (unify existing machinery) | FR-007/008 | `merge/executor.py` (checkpoint API), `done_bookkeeping.py`, `coordination/teardown.py` | IC-2 |
| IC-6 Direct-on-target safety + completion affordance | FR-010/012 | `merge/executor.py`, `cli/commands/merge.py` | IC-2 |
| IC-7 Mission-close orphan robustness + accept-guidance liveness | FR-013/014 | `cli/commands/mission_type.py`, `cli/commands/accept.py` | IC-1 |

## Parallel Work Analysis

### Dependency graph

```
IC-1 (enabler, tidy-first)  ──►  IC-2  ──►  IC-5   (rollback)
        │                         └──►  IC-6   (direct-on-target + --skip-lanes)
        ├──►  IC-3  (close guard)
        ├──►  IC-4  (bake topology)
        └──►  IC-7  (close orphan + accept guidance)
```

- **Sequential (must be first)**: IC-1 — the shared aggregate + rerouting is behavior-preserving and every functional concern consumes it. Landing it first honors DIRECTIVE_025 tidy-first (enabler before functional change).
- **Parallelizable after IC-1**: IC-3, IC-4, IC-7 (distinct files/surfaces); IC-2 also starts after IC-1.
- **Sequential after IC-2**: IC-5 (rollback builds on the precondition path), IC-6 (direct-on-target reuses the precondition).
- **D5 note**: IC-6's *rollback-after-target-advance* is the harder sub-seam; if it balloons, ship the refuse-before-advance guard (US3-3) and defer the target-ref rollback as a tracked #3897 follow-up (interim state provably safe).

### Coordination points (single-branch execution)

Per the operator's execution directive, WPs are implemented by subagents **directly on the single mission branch `issue-4764-terminus-safety-invariant`** (NOT lane worktrees). Sequencing follows the graph above; the integrated diff gets a pre-PR adversarial squad before the PR opens. Each WP commits its red-first test as a distinct preceding commit.

## Complexity Tracking

*No Constitution Check violations — none to justify.*
