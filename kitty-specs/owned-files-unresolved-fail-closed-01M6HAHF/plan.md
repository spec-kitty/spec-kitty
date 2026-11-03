# Implementation Plan: Owned files unresolved fail closed

**Branch**: `fix/7149-ownership-unresolved` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/owned-files-unresolved-fail-closed-01M6HAHF/spec.md`

## Summary

The shared evidence predicate (`src/specify_cli/consolidation/wp_evidence.py`) gains a verdict,
`OWNERSHIP_UNRESOLVED`. It fires for an approved work package whose ownership declaration could not
be read, and it is checked before the "no owned change" verdict, so `IMPLEMENTATION_MISSING` again
means only "ownership resolved, nothing owned changed". `--attest-no-implementation` refuses the new
verdict. Two same-class folds come with it: `accept --owned-checkout` reads the canceled-work-package
set from the owned checkout, and the owned review-ward `move-task` refusal says when a work package
declares no `owned_files`.

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; CI also runs 3.12 and 3.13)
**Primary Dependencies**: Existing in-repo modules only. No dependency is added, upgraded or removed, so there is no supply-chain decision (DIRECTIVE_051 does not apply).
**Storage**: Files only: Mission `tasks/*.md` frontmatter and `status.events.jsonl` (read-only for this change)
**Testing**: pytest. Red-first regression tests through the production entry points (`spec-kitty accept` CLI via the owned-checkout integration fixtures, and `mission_evidence_report`), each with a same-fixture positive control. Existing evidence suites are a ratchet.
**Target Platform**: The spec-kitty CLI on Linux, macOS and Windows
**Project Type**: single (Python CLI package under `src/`)
**Performance Goals**: No added git subprocess per work package (NFR-001); the verdict reuses the task-file read the gate already performs.
**Constraints**: One predicate decides the verdict (C-001); the #7099 owned read is reused, not rewritten (C-002); evidence windows unchanged (C-004).
**Scale/Scope**: About 6 source files and 6 test files; 2 work packages.

## Charter Check

- **Single canonical authority**: met. The verdict lives only in `wp_evidence`; `accept`, `consolidate` and `orchestrator-api` already consume it through `mission_evidence_report` / `evaluate_evidence`.
- **Architectural alignment / layer rules**: met. All changes stay in `specify_cli`; no new import direction.
- **ATDD-first and red-first (Standing Order 4, DIRECTIVE_041)**: met by NFR-002. Each behaviour change gets one focused regression test through the production path; existing tests are strengthened in place rather than duplicated.
- **Terminology**: met. "Mission" and "work package" are used throughout; touching `src/charter/offering/` (the operator skill contract reference) requires the terminology guard before push.
- **Fail closed**: the new verdict is fail-closed by design and cannot be lifted.

No violation needs justification.

## Project Structure

### Documentation (this mission)

```
kitty-specs/owned-files-unresolved-fail-closed-01M6HAHF/
├── spec.md
├── plan.md              # this file
├── research.md          # squad findings and decisions
├── data-model.md        # the verdict codes and their precedence
├── quickstart.md        # how to see the new refusal
├── contracts/
│   └── evidence-codes.md
└── tasks/               # created by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/consolidation/wp_evidence.py                 # verdict, codes, recovery text (WP01)
src/specify_cli/consolidation/no_implementation_attestation.py  # unliftable set (WP01)
src/specify_cli/orchestrator_api/envelope.py                 # code registry comment (WP01)
src/specify_cli/consolidation/done_bookkeeping.py            # owned-aware canceled read (WP02)
src/specify_cli/cli/commands/accept.py                       # pass owned to the canceled read (WP02)
src/specify_cli/cli/commands/agent/tasks_move_task.py        # empty-declaration refusal detail (WP02)
```

**Structure Decision**: Single project. Documentation registries (`docs/api/orchestrator-api.md`, the operator skill contract reference, the ADR `2026-10-04-5` amendment) and the changelog fragment are updated at closeout, after consolidation, with the PR.

## Complexity Tracking

None. No charter violation is introduced.

## Implementation Concern Map

### IC-01 — Unresolved-ownership verdict in the evidence predicate

- **Requirements**: FR-001, FR-002, FR-003, FR-005, FR-008, NFR-001, C-001, C-002
- **Where**: `wp_evidence.py`. The scan records the `tasks/` directory it read. `_judge` (shared by the lanes scan and the single_branch scan) emits `OWNERSHIP_UNRESOLVED` (or `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED`) when the work package is absent from the resolved ownership map, before the owned-change test. A recovery line is added to `_RECOVERY`, and the code joins `_NEUTRAL_CODES`, `_SINGLE_BRANCH_ALIASES` and the code-literal test.
- **Evidence**: red-first tests (task file absent, `tasks/` missing, unreadable task file) plus a positive control; `test_owned_acceptance_authority_6023.py::missing_owned_ownership` (authored `owned_files: []`) stays `IMPLEMENTATION_MISSING` as the FR-008 ratchet.

### IC-02 — Attestation refuses the unresolved verdict

- **Requirements**: FR-004
- **Where**: `no_implementation_attestation._UNLIFTABLE_VERDICTS` gains both new codes; the refusal text names the unresolved read.
- **Evidence**: attestation on an unresolved work package refuses and records nothing; attestation on a resolved `IMPLEMENTATION_MISSING` still succeeds (control).

### IC-03 — Owned accept reads canceled work packages from the owned checkout

- **Requirements**: FR-006
- **Where**: `done_bookkeeping.acceptably_canceled_wp_ids` takes the optional `owned` fact and resolves the status surface through it; `accept.py` passes `run.owned` at both call sites.
- **Evidence**: an owned-checkout Mission absent from the repository root, with an operator-canceled work package, is accepted with that work package excluded; the non-owned call is unchanged.

### IC-04 — Owned move-task names an empty declaration

- **Requirements**: FR-007
- **Where**: `tasks_move_task._mt_require_owned_implementation` splits its `not patterns` branch into its own message naming the task file; the code stays `OWNED_IMPLEMENTATION_MISSING`.
- **Evidence**: the existing move-task evidence-gate test is strengthened to assert both messages on one fixture.
