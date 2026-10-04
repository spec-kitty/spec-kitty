# Mission Specification: Consolidation god-module decomposition

**Mission Branch**: `issue-2026-consolidation-decomposition`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator brief (2026-10-04): deliver epic #2026 (re-scoped 2026-10-04), #2600 and #3457 as a tidy-first, behaviour-preserving structural change.
**Grounding**: [`research/code-grounding.md`](research/code-grounding.md)

## Intent Summary

- **Primary actor:** a maintainer or agent who has to change consolidation behaviour (first in line: whoever lands the #5613 P0 fix, PR #5633).
- **Trigger:** today every such change lands in `consolidation/executor.py` (4,603 LOC, 93 commits in 90 days, 57 of them fixes), in `ordering.py` where merge ordering is fused with the mission_number bake cluster, or in a 19-parameter `consolidate()` whose direct-call tests enumerate every keyword.
- **Outcome:** the same code lives in cohesive modules cut along the consolidation phases, the bake cluster has its own home, and `consolidate()` takes a parameter object for direct callers. Nothing an operator can observe changes.
- **Rule that always holds:** the consolidation invariants (single rollback authority, one rollback door, CAS ref advance, pre-mutation snapshot and per-phase post tips, claim refusal before the first mutation, projection teardown gate, squash content axis, closed world, protected-target preflight, lock) keep the same enforcement and the same pins. No gate is loosened; a gate that would go vacuous after a move is widened to follow the code.
- **Bulk edit:** yes. This mission moves functions out of `specify_cli.consolidation.executor` and `specify_cli.consolidation.ordering` into new modules, and re-points every import, monkeypatch target and gate entry that names the old module (`change_mode: bulk_edit`, `occurrence_map.yaml` in plan).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Change one consolidation phase without opening a 4,600-line file (Priority: P1)

A maintainer fixing a resume-recovery gap (#5613 gap 3) opens the module that owns resume recovery, reads ~330 lines, changes them, and runs that module's unit tests. The orchestration (phase order, rollback door, lock) is in a separate, small driver they do not need to touch.

**Why this priority**: it is the epic's purpose and the next P0 fix depends on it.

**Independent Test**: after the split, every consolidation unit/seam test passes unchanged in meaning, the rollback-door and phase-order pins still read the driver, and each new module is a single phase concern.

**Acceptance Scenarios**:

1. **Given** the split executor, **When** the consolidation, terminus, lanes and orchestrator-api tests run, **Then** they pass with the same counts as on `origin/main` (modulo re-pointed imports and patch targets).
2. **Given** a test that patched `executor.<name>`, **When** the name moved, **Then** the test patches every module that now looks `<name>` up, so it intercepts exactly the calls it intercepted before.

---

### User Story 2 - Find the mission_number bake logic under mission_number (Priority: P2)

A maintainer looking for how `mission_number` is assigned, baked and verified finds it under `consolidation/mission_number/`, and `ordering.py` contains only merge ordering. The merge-driver body module still imports a stdlib-only predicate.

**Why this priority**: #2600; small, independent.

**Independent Test**: `ordering.py` defines only `MergeOrderError`, `has_dependency_info` and `get_merge_order`; the bake tests and every gate that keyed on `ordering.py` pass against the new module.

**Acceptance Scenarios**:

1. **Given** the move, **When** `specify_cli.consolidation.mission_number` is imported, **Then** it imports nothing outside the standard library.
2. **Given** the move, **When** `tests/consolidation/test_ordering_bake_seam.py` and the census/audit gates run, **Then** they pass against the new module path.

---

### User Story 3 - Add a `consolidate` option without breaking direct-call tests (Priority: P2)

A maintainer adds a CLI option to `consolidate`. Direct-call tests build one options object with real defaults, so the new field takes its default there instead of leaking a `typer.OptionInfo` sentinel.

**Why this priority**: #3457 (P1 label); the failure mode already happened once (#3456 landing pass).

**Independent Test**: a test that builds the options object with no arguments gets real defaults for every field (no `OptionInfo`), and the Typer command's 19 CLI options are unchanged.

**Acceptance Scenarios**:

1. **Given** `ConsolidateOptions()`, **When** inspected, **Then** no field holds a `typer.models.OptionInfo`.
2. **Given** the CLI, **When** `spec-kitty consolidate --help` runs, **Then** it lists the same options as before.

### Edge Cases

- A name patched on `executor` is looked up by two or more new modules: the patch is applied to each of them.
- A test reads an attribute through the `executor` module that no longer lives there: the test imports it from its new home (no alias kept only for tests).
- A gate scoped to a fixed file list (revert-argv scan, status-bearing modules, churn surface, write-dir consumers, fail-closed census, seam import targets) would stop scanning moved code: the list is extended to the receiving modules.
- An import cycle between the new modules: modules form a DAG with `run_state` at the root and `executor` at the top.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Split executor along phase boundaries | As a maintainer, I want `executor.py`'s phase helpers moved verbatim into cohesive phase modules so that a phase change touches one small module. | High | Done | [build] | no — `executor.py` must shrink to the driver, door, lock entry and attestation recording, and each phase module must exist |
| FR-002 | Thin orchestrating executor | As a maintainer, I want `executor.py` to keep the locked driver with the inline rollback door, `_report_rollback` and the locked entry so that the door and phase-order pins keep reading the same code. | High | Done | [ratchet] | yes — paired with FR-001 (a do-nothing change keeps them too, but fails FR-001) |
| FR-003 | Bake cluster under mission_number | As a maintainer, I want the mission_number bake cluster moved out of `ordering.py` into `consolidation/mission_number/bake.py`, with the stdlib-only predicate kept in `consolidation/mission_number/__init__.py`, so that each module has one concern. | Medium | Done | [build] | no — `ordering.py` must lose the cluster |
| FR-004 | Parameter object for consolidate() | As a maintainer, I want a `ConsolidateOptions` parameter object with real defaults that the Typer command builds and passes to the command body, so that direct callers construct one object instead of enumerating 19 keywords. | High | Done | [build] | no — a test asserting no `OptionInfo` default fails without it |
| FR-005 | Direct-call tests use the parameter object | As a maintainer, I want the 8 direct-call test sites to build `ConsolidateOptions` so that adding an option cannot leak a sentinel into them. | Medium | Done | [build] | no |
| FR-006 | Monkeypatch interception preserved | As a maintainer, I want every test patch that named a moved function's collaborator re-pointed to every module that now looks it up so that each test intercepts exactly what it intercepted before. | High | Done | [ratchet] | no — an AST audit compares old and new interception sets |
| FR-007 | Gates re-pointed, never loosened | As a reviewer, I want every path/qualname-keyed gate and ledger re-pointed and every fixed-scope gate widened to the receiving modules so that no invariant pin goes vacuous. | High | Done | [ratchet] | no — each re-pointed entry names a file that exists and contains the pinned code |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behaviour preservation | Moved function bodies are byte-identical to `origin/main` (checked by an AST/source comparison of every moved top-level definition). | Reliability | High | Done |
| NFR-002 | Test parity | The targeted suites (`tests/consolidation/`, `tests/specify_cli/consolidation/`, `tests/terminus/`, `tests/lanes/`, `tests/orchestrator_api/`, `make test-fast`, the named architectural gates) have no new failure versus `origin/main`. | Reliability | High | Done |
| NFR-003 | Static quality | `ruff check`, `ruff format --check --force-exclude` and `mypy` report zero new issues on changed files; C901 stays at or below 15. | Maintainability | High | Done |
| NFR-004 | Cohesion | No module produced by the split exceeds ~900 LOC, and `executor.py` drops below ~800 LOC. Guidance for review, not a new gate. | Maintainability | Medium | Done |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No behaviour change | No refusal text, exit code, state file, ref operation or ordering changes. | Technical | High | Done |
| C-002 | #5613 out of scope | Do not fix #5613 and do not touch `p0_repro`-marked reproductions. | Business | High | Done |
| C-003 | No new size gates | Do not add a module-length or ratchet gate (operator ruling). | Technical | High | Done |
| C-004 | Single rollback authority | `rollback_to_snapshot` keeps exactly its two allowed callers; the door stays one `try` in the driver. | Technical | High | Done |
| C-005 | Move before callers | Each slice moves code first, then adjusts callers; no logic edit while moving. | Technical | High | Done |
| C-006 | CLI surface stable | `consolidate`'s Typer options (names, flags, help, defaults) are unchanged. | Technical | High | Done |

### Key Entities

- **Phase module**: a module under `consolidation/` holding the helpers of one consolidation phase (claim, advance, bookkeeping, gate, teardown, finalize), or one cross-phase concern (run state, coord strand, entry preflight, resume recovery).
- **`ConsolidateOptions`**: frozen dataclass with one field per `consolidate` CLI option and real (non-Typer) defaults.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `executor.py` shrinks from 4,603 LOC to below ~800 LOC, and the largest phase module stays below ~900 LOC. — [build] · no-op passable: no
- **SC-002**: The targeted suites report the same pass count as `origin/main` plus any newly added tests, with no new failures. — [ratchet] · no-op passable: yes — paired with SC-001 on the same tree
- **SC-003**: Every gate listed in code-grounding §3 passes, and none has fewer entries, a lower floor or a narrower scan scope than on `origin/main`. — [ratchet] · no-op passable: yes — paired with SC-001
- **SC-004**: `ordering.py` is below ~150 LOC and `consolidation/mission_number/__init__.py` imports only the standard library. — [build] · no-op passable: no
- **SC-005**: No direct-call test enumerates `consolidate()` keywords. — [build] · no-op passable: no
