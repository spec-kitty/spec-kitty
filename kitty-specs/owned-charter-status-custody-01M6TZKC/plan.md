# Implementation Plan: Owned Mission coordination status charter custody

**Branch**: `issue-6788-owned-charter-status-custody` | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/owned-charter-status-custody-01M6TZKC/spec.md`

## Summary

Keep `charter_scope_for_owned` as the single custody door. Its resolved primary-directory equality stays the fast path. Only when the supplied directory differs, resolve this validated owned Mission through `mission_context_for(owned.repository_root, owned.mission_slug, owned=owned, tolerate_unmaterialized_coord=True)` and accept only exact resolved equality with `MissionArtifactKind.STATUS_STATE.read_dir`. Every other unequal path keeps `MISSION_CONTEXT_CONFLICT`; `CharterScope.resolve(owned.owned_root, owned.mission_dir)` remains unchanged.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: existing `mission_runtime` placement and `charter.activation.api`; no dependency changes  
**Storage**: existing Mission directories; no schema or migration  
**Testing**: focused pytest integration plus one installed-CLI performance reproduction; ATDD red-first  
**Target Platform**: Linux, macOS, and Windows CLI behavior  
**Project Type**: single Python CLI project  
**Performance Goals**: zero additional placement-resolution calls on the primary same-path arm  
**Constraints**: no hardcoded worktree paths, no foreign-path weakening, no runtime-signature widening, no full heavy suite  
**Scale/Scope**: one production module, one existing integration test module, one changelog fragment, one WP

## Engineering Alignment

The comprehensive binding brief confirmed this exact seam and validation surface. Decision `01M6V1K7Q713B99959ZN7CDD9B` records alignment. The architect lens prefers the existing canonical placement facade over new path derivation or broader runtime data threading. No unresolved planning questions or dependency/security decisions remain.

## Charter Check

- **Canonical authority**: reuse `mission_context_for` and `STATUS_STATE.read_dir`; do not create another coordination-path authority.
- **Architecture**: keep the change in `specify_cli`, consuming `mission_runtime`; layer direction is unchanged.
- **ATDD**: commit focused failing integration coverage before the production edit; reproduce installed-CLI `[0]` red first.
- **Custody**: pair canonical-status success with foreign-path refusal on the same valid `lanes_with_coord` fixture.
- **Small diff/locality**: no campsite refactor is warranted in the 25-line guard or neighboring tests; preserve unrelated assertions byte-for-byte.
- **Testing**: run only the two owned integration surfaces, the exact e2e node, formatting/lint/type checks, and `make test-fast`; no full heavy suite.
- **Honest closeout**: nightly owns all 20 parameters and the umbrella startup row remains separate.

Post-design re-check: no new boundary, dependency, migration, allowlist, or architectural gate is introduced, so no additional gate file is implicated.

## Project Structure

### Documentation (this mission)

```
kitty-specs/owned-charter-status-custody-01M6TZKC/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── traces/
└── tasks.md + tasks/WP01-*.md  (/spec-kitty.tasks output)
```

`meta.json` records `contracts: none` because this Mission changes no external interface.

### Source Code (repository root)

```
src/specify_cli/core/owned_charter.py       # custody validation only
src/mission_runtime/resolution.py          # existing canonical placement facade; unchanged

tests/integration/test_owned_prompt_charter_scope.py  # positive + negative integration coverage
tests/integration/test_owned_next_runtime.py          # owning runtime blast radius; unchanged
tests/e2e/test_worktree_owned_root_concurrency.py     # installed-CLI reproduction; unchanged

docs/changelog/unreleased/6788.fixed.md
```

**Structure Decision**: modify only the existing custody projector and its owned prompt integration test. The runtime's selection of the materialized status directory is correct and remains untouched.

## Implementation Concern Map

### IC-01 — Same-Mission canonical status custody

- **Purpose**: admit a valid coordination status directory without turning status placement into a custody bypass.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, C-001, C-002; SC-001, SC-002, SC-003
- **Affected surfaces**: `src/specify_cli/core/owned_charter.py`, `tests/integration/test_owned_prompt_charter_scope.py`, `docs/changelog/unreleased/6788.fixed.md`
- **Sequencing/depends-on**: none
- **Risks**: accidental resolver invocation on the fast path, accepting another Mission's status path, or moving charter reads to coordination. Exact resolved equality, same-fixture negative coverage, owned marker assertions, and primary snapshots mitigate each.

## Validation Strategy

1. Run the existing installed-CLI parameter `[0]` before edits and record its `MISSION_CONTEXT_CONFLICT` failure.
2. Add a real `lanes_with_coord` prompt test whose canonical `STATUS_STATE.read_dir` differs from `owned.mission_dir`; commit it while red, with a same-fixture foreign-path negative.
3. Implement only the unequal-arm canonical status comparison and rerun the focused integration file.
4. Run `tests/integration/test_owned_next_runtime.py`, the installed-CLI `[0]` reproduction, and `make test-fast`.
5. Run scoped ruff, format, and mypy checks. Record exact counts and leave full-matrix/nightly verification explicitly pending.
