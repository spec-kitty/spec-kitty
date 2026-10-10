# Implementation Plan: Destructive ops never delete the only copy

**Branch**: `fix/5965-5966-destructive-residue-context` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`

## Summary

The destructive guard (`src/specify_cli/git/destructive_guard.py`) and the ref-advance resync (`src/specify_cli/git/ref_advance.py`) accept a caller-supplied `is_residue` predicate, and callers pass the topology-blind `is_toolchain_generated_churn`. Two bugs follow: coordination teardown force-removes the coordination worktree over its only copies of review feedback (#5965), and the rollback resync `reset --hard`s another Mission's uncommitted edits (#5966).

The fix moves the decision into the guard. Destructive entry points take a required `ResidueContext` (Mission slug, stored topology, checkout role) and decide disposability through one new function, `is_disposable_residue`, built on the existing classifier plus checkout-role rules. A refused coordination teardown stops being swallowed and fails the run without undoing a verified landing. Every remaining destructive operation in `src/` (git argv and recursive deletion of a checkout) is routed through the guard, and the existing routing gate (`tests/architectural/test_destructive_op_routing.py`) is widened to the full operation set with its allowlist drained to empty, per ADR `2026-09-30-1-allowlist-ratchets-are-priced-debt`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); git ≥ 2.38 on the host; no new dependency
**Storage**: git refs and working trees; `.kittify/runtime/merge/<mission_id>/state.json` (unchanged schema)
**Testing**: pytest with ATDD red-first `@pytest.mark.regression` + `p0_repro(issue=N)` reproductions through the real `consolidate` / `consolidate --abort` / `orchestrator-api consolidate-mission` entry points; focused unit tests for the classifier and the guard; the AST routing gate in `tests/architectural/test_destructive_op_routing.py`
**Target Platform**: Linux, macOS, Windows (the guard already carries the Windows read-only retry shim in `asset_preservation/guard.py`)
**Project Type**: single (CLI)
**Performance Goals**: no measurable change; the guard adds at most one `git status` per destructive op, which the existing guard already runs
**Constraints**: cyclomatic complexity ≤ 15; ruff, ruff format and mypy clean; diff coverage ≥ 90%; no new rollback path (C-005); fail closed (C-002)
**Scale/Scope**: about 22 allowlisted git sites, about 10 unguarded git sites, and about 6 recursive-deletion sites that target a git checkout; about 50 recursive deletions of tool-owned temp or managed-asset trees are classified and routed through one helper

## Charter Check

- **Single canonical authority**: one disposability decision (`is_disposable_residue` in `coordination/coherence.py`, next to the partition rule) and one module that runs destructive operations (`git/destructive_guard.py`). PASS.
- **Architectural alignment**: the enforced layer chain is unchanged; all changes stay in `specify_cli`. PASS.
- **ATDD-first / red-first (ADR 2026-07-17-1)**: reproductions land first and are red through the pre-existing entry points. PASS.
- **Architectural gate discipline / ADR 2026-09-30-1**: the routing gate closes with an empty allowlist; scratch removals go through a guard helper that proves the path is tool-owned, rather than an allowlist row. PASS.
- **Terminology**: Mission, consolidate, coordination worktree, repository root checkout; no "feature", no bare "primary" or "merge". PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/destructive-residue-context-01M4KBPS/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/refusal-codes.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/
├── coordination/coherence.py        # is_disposable_residue, ResidueContext, CheckoutRole
├── coordination/workspace.py        # teardown passes a coordination-role context; stale-registration prune via guard
├── coordination/teardown.py         # stop swallowing DestructiveOpRefused; skip branch delete
├── coordination/coord_seed.py       # recursive delete via guard
├── git/destructive_guard.py         # required context; guarded reset / branch delete / prune / tree delete / scratch removal
├── git/ref_advance.py               # resync/restore/advance take a context, not a predicate
├── consolidation/rollback.py        # pass this run's context
├── consolidation/phase_teardown.py  # propagate the teardown refusal; resume path
├── consolidation/{resume_recovery,git_probes,workspace,mission_number/bake}.py
├── lanes/{worktree_allocator,consolidation}.py
├── core/{vcs/git,mission_creation_rollback,worktree}.py, missions/_create.py, cli/commands/{mission_type,agent/mission_create}.py
├── orchestrator_api/consolidation.py
├── status/doctor_husks.py, review/baseline.py, charter_packs/sources/git_source.py
tests/
├── architectural/test_destructive_op_routing.py   # widened patterns, empty allowlist
├── consolidation/, coordination/, git/, specify_cli/git/   # reproductions and unit tests
```

**Structure Decision**: single project; no new module. The guard grows new entry points; the classifier grows one context-taking function.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Red-first reproductions

- **Purpose**: prove both reported data losses through the real entry points before any fix.
- **Relevant requirements**: FR-008, SC-001, SC-002
- **Affected surfaces**: `tests/consolidation/` (new reproduction files), coordination Mission and two-Mission fixtures from `tests/_factories/`
- **Sequencing/depends-on**: none
- **Risks**: the #5965 path must run the real `move-task --to planned --no-auto-commit`, not plant files; the reproductions must be red on `main` for the reported reason, not on a fixture error.

### IC-02 — Context-aware disposability and the guard API

- **Purpose**: make the residue decision require Mission, topology and checkout role, and move it inside the guard.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-009, C-001, C-002
- **Affected surfaces**: `coordination/coherence.py`, `git/destructive_guard.py`, `git/ref_advance.py` (`resync_checkouts_to_tip`, `restore_branch_ref`, `advance_branch_ref`, `_dirty_entries`)
- **Sequencing/depends-on**: IC-01
- **Risks**: `is_toolchain_generated_churn` has about 44 callers, most of them non-destructive gates; changing its signature would be a whack-a-field. It stays as is; only destructive entry points switch to the context-taking function. `advance_branch_ref` callers must keep today's residue behaviour on the normal path (NFR-001).

### IC-03 — Consolidate, abort and teardown wiring

- **Purpose**: pass this run's context at every consolidation destructive site and make a refused teardown fail the run safely.
- **Relevant requirements**: FR-004, FR-005a, FR-005b, C-004, C-005
- **Affected surfaces**: `consolidation/rollback.py`, `coordination/workspace.py`, `coordination/teardown.py`, `consolidation/phase_teardown.py`, `orchestrator_api/consolidation.py`
- **Sequencing/depends-on**: IC-02
- **Risks**: the refusal happens after the landing passed reconciliation. It must not enter the rollback door, must skip the coordination branch delete, and `--resume` must re-anchor the teardown gate's compare-and-swap expectation to the coordination tip the operator committed (see research D4).

### IC-04 — Route the remaining destructive operations

- **Purpose**: every destructive git operation and every recursive deletion of a git checkout outside the guard moves behind it.
- **Relevant requirements**: FR-007, FR-009
- **Affected surfaces**: the sites listed in research D6
- **Sequencing/depends-on**: IC-02
- **Risks**: behaviour change at sites that today force through dirty state (lane allocation retry, charter pack source refresh); each needs a test showing the clean path unchanged and the dirty path refused. Tool-owned scratch removals use a guard helper that asserts the path is under `.kittify/runtime/` or a tool-created temp root.

### IC-05 — Widen and drain the routing gate

- **Purpose**: the existing routing gate covers the full destructive set and closes with an empty allowlist.
- **Relevant requirements**: FR-006, SC-003
- **Affected surfaces**: `tests/architectural/test_destructive_op_routing.py`, `tests/architectural/_destructive_op_census.py`
- **Sequencing/depends-on**: IC-03, IC-04
- **Risks**: the recursive-deletion check must tell a checkout path from a temp tree statically; research D7 resolves this by forbidding a bare `shutil.rmtree` outside two helpers rather than by guessing at paths.
