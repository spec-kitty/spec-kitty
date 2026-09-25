# Implementation Plan: Merge resume primary-site staged-deletion integrity

**Branch**: `fix/4997-resume-primary-staged-deletion-integrity` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/resume-primary-staged-deletion-integrity-01M3CCH9/spec.md`

## Summary

Close the two coupled defects behind #4997 so a `spec-kitty merge --strategy merge
--resume` over a primary checkout that lags its own HEAD (after an interrupted terminus)
either **recovers and lands all approved code** or **refuses fail-closed** — never
silently strands the merge and never lands the target missing the mission's content while
stamping WPs `done`:

1. **Phantom-only resume recovery (FR-001/FR-002).** At the pre-mutation primary dirty
   guard's refusal handler, on a `--resume`, classify the dirty state. When it is a
   *provably pure* behind-own-HEAD lag — the primary's working tree AND index are
   byte-identical to the persisted `pre_mutation_target_sha` and HEAD is its descendant —
   run `git reset --hard HEAD` and continue. Any deviation (genuine edit, intentional
   non-mission deletion, missing base, index.lock) → REFUSE, never reset.
2. **Merge-strategy no-op adjudication (FR-003).** Make `_merge_branch_into` report a
   merge-strategy "Already up to date" as `changed=False` (→ `already_applied=True`), so
   the (strategy-agnostic) zero-diff adjudication refuses when the target tree diverges
   from the mission tree, before any WP is stamped `done` / any teardown.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git (plumbing), typer, rich; internal `merge/`, `lanes/`, `git/` modules
**Storage**: `MergeState` (`.kittify/merge-state.json`) — reads persisted `pre_mutation_target_sha`
**Testing**: pytest; real-CLI terminus fixtures (`tests/terminus/conftest.py`), no subprocess mocking
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single (library/CLI)
**Performance Goals**: recovery decision is O(1) git probes (ancestry + two `diff --quiet`)
**Constraints**: fail-closed on any ambiguity; no new dirty-guard authority (INV-3); complexity ≤15; no new suppressions
**Scale/Scope**: 3 source files + 3 tests; no schema/ADR change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority**: reuses `classify_resume_dirty_remedy` + `pre_mutation_target_sha`; no parallel dirty predicate (PASS — NFR-001/C-001).
- **Architectural alignment**: all changes inside the merge seam (`merge/`, `lanes/merge.py`, `git/`); downward-only imports preserved (PASS — C-003).
- **DDD tiered rigour**: core merge-integrity logic → maximum rigour, focused unit tests on every new branch (PASS — NFR-003).
- **ATDD-first / red-first**: each defect lands an issue-pinned red test through the real entry point before the fix (PASS — FR-004, US1 AC2, US2).
- **Terminology**: "Mission", canonical `status commit`; no forbidden terms (PASS).

## Project Structure

### Documentation (this mission)

```
kitty-specs/resume-primary-staged-deletion-integrity-01M3CCH9/
├── spec.md
├── plan.md              # this file
├── tasks.md             # /spec-kitty.tasks output
├── tasks/               # per-WP files
└── trace/               # 3 tracer files (grounding/squad, seam map, decisions)
```

### Source Code (repository root)

```
src/specify_cli/
├── merge/
│   ├── executor.py      # FR-001/002 recovery at the DestructiveOpRefused handler; FR-003 guard rename
│   └── preflight.py     # phantom-only proof helper + BEHIND_OWN_HEAD wiring
├── lanes/
│   └── merge.py         # FR-003: merge no-op → changed=False
└── git/
    └── (destructive_guard.py / ref_advance.py consulted; likely unchanged)

tests/terminus/
├── test_repro_4997.py           # FR-004: correct the fixture to the real window; remove xfail
├── test_repro_4982.py           # regression guard (must stay green)
└── test_resume_phantom_only_*.py # US1 AC2 safety + US2 merge no-op refusal (new)
```

**Structure Decision**: Single-project library/CLI. Changes are confined to the merge seam.

## Complexity Tracking

*No Constitution violations.* The recovery helper is extracted as a small pure-ish predicate
(`is_pure_behind_head_lag`) to keep the handler and preflight functions ≤15 complexity and
directly unit-testable.

## Parallel Work Analysis

### Dependency Graph

```
WP01 (Defect A: phantom-only recovery + corrected repro + safety test)
   └── shares executor.py write-scope with →
WP02 (Defect B: merge no-op adjudication + red-first test + rename)
```

Both WPs touch `merge/executor.py`, so they collapse into a **single lane** (sequential),
not parallel streams — WP01 first (the P0 data-integrity recovery), WP02 second.

### Work Distribution

- **Sequential**: WP01 then WP02 (shared `executor.py`); one lane.
- **Parallel streams**: none (shared write scope).
- **Agent assignments**: implementer (sonnet, profile-loaded) per WP; reviewer-renata (opus) reviews each.

### Coordination Points

- **Integration tests**: full `tests/terminus/` + merge subsystem dirs run by the orchestrator before push (per blast-radius steer; #5027 lesson).
- **Fail-closed verification**: the reconciliation gate remains the teardown backstop; C-002 residual noted.
