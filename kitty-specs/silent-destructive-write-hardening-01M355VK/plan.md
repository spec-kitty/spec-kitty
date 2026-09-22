# Implementation Plan: Silent Destructive-Write Hardening

**Branch**: `fix/silent-destructive-write-hardening` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/silent-destructive-write-hardening-01M355VK/spec.md`

## Summary

Three disjoint-seam bug fixes (#4908, #4897, #4894) under one acceptance bar: *no silent
data loss — read the SSOT / preserve-unless-proven-redundant, never exit-0/errors-0 on a
destructive rewrite.* Each is a bounded, seam-respecting correction with an issue-pinned
red-first regression test. No new dependencies; no cross-WP shared files → fully
parallelizable, `single_branch` topology.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, ruamel.yaml (charter YAML), pytest (no new dependency added)
**Storage**: files — `charter.yaml`, `status.events.jsonl`, `traces/*.md` (git-tracked)
**Testing**: pytest; each defect gets an issue-pinned `@pytest.mark.regression` test that is RED through the pre-existing entry point before the fix
**Target Platform**: Linux/macOS CLI (`spec-kitty`)
**Project Type**: single (CLI monorepo, `src/specify_cli/` + siblings)
**Performance Goals**: N/A (correctness fixes; no hot path changed)
**Constraints**: `ruff` + `ruff format --check` + `mypy` clean, zero new suppressions; touched-function complexity ≤15; do NOT route through the path-level `asset_preservation` guard (C-001)
**Scale/Scope**: 3 WPs, ~3 source seams + 1 new small registry module, ~3 regression tests + focused unit tests

## Constitution Check

*GATE: charter present — checked.*

- **Single canonical authority (SSOT).** WP01 reads the recorded mission type from its SSOT instead of fabricating a default; WP02 introduces ONE authoritative-non-lane-event-type registry both subsystems consult (rather than a second parallel list). ✅ aligned — this mission *increases* canonical-source compliance.
- **Architectural alignment / module seams.** Each fix stays within its owning seam (charter compile / status+migration / merge driver); WP02's registry lives with the status event-type authority (`status/lifecycle_events.py` or a sibling) and is imported, not duplicated. ✅
- **ATDD / red-first (DIRECTIVE_041, ADR 2026-07-17-1).** Each defect lands a red-first repro through the pre-existing entry point. ✅
- **Architectural gate discipline (DIRECTIVE_043).** WP02 optionally adds a non-vacuous test asserting the two consumers share one registry (prevents the whack-a-field class from reopening). ✅
- **Tiered rigour.** Core domain logic (event-type authority, catalog SSOT) gets more rigour than glue. ✅

No violations to justify in Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/silent-destructive-write-hardening-01M355VK/
├── plan.md              # This file
├── research.md          # Phase 0 — root-cause + option analysis (grounding-derived)
├── data-model.md        # Phase 1 — the artifacts/entities each seam owns
├── quickstart.md        # Phase 1 — how to reproduce + verify each fix
├── contracts/           # Phase 1 — the hardening contract each WP must satisfy
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
# WP01 (#4908) — charter recompile SSOT
src/specify_cli/cli/commands/charter/generate.py     # :249 fallback → read recorded mission
src/specify_cli/cli/commands/charter/activate.py     # :558-566 recompile call site
src/specify_cli/cli/commands/charter/pack.py         # :208-217 pack apply --compile (same shape)
tests/specify_cli/cli/commands/charter/              # + red-first regression test

# WP02 (#4897) — authoritative non-lane event-type registry
src/specify_cli/status/lifecycle_events.py           # home of / sibling to the new registry
src/specify_cli/status/store.py                      # :597 is_non_lane_event → consult registry
src/specify_cli/migration/mission_state.py           # :1919-1972 _is_preserved_non_lane_row → consult registry; :1671-1691 honest status
tests/status/ , tests/migration/ (or mirror)         # + red-first regression test + registry-sharing gate

# WP03 (#4894) — traces merge driver granularity
src/specify_cli/cli/commands/merge_driver.py         # :304-325 union_trace_texts, :328-338 merge_driver_traces
src/specify_cli/lanes/merge.py                       # :88-92 driver spec (reference only)
tests/specify_cli/cli/commands/ , tests/merge/       # + red-first regression test
```

**Structure Decision**: Single-project CLI monorepo. Each WP edits one owning seam; the only
*new* surface is WP02's small registry (a set/frozenset of authoritative non-lane `event_type`s
plus a predicate), placed with the existing status event-type authority and imported by both
consumers.

## Parallel Work Analysis

### Dependency Graph

```
WP01 (#4908 charter)   ─┐
WP02 (#4897 registry)  ─┼─  all independent, no edges → fully parallel
WP03 (#4894 traces)    ─┘
```

### Work Distribution

- **Sequential work**: none.
- **Parallel streams**: WP01 / WP02 / WP03 touch disjoint files → parallelizable.
- **Agent assignments**: one implementer per WP (implement=sonnet, profile-loaded); reviewer=opus, distinct from implementer.

### Coordination Points

- **Sync schedule**: `single_branch` — WPs land on the mission branch sequentially at merge; no lane-to-lane merges (C-004: avoid pushing the mission's own `traces/*.md` through the WP03-target driver mid-flight).
- **Integration**: after all three land, run the full blast-radius suites (charter, status/decisions, merge) + `ruff`/`mypy`; confirm the three regression tests are RED on merge-base, GREEN on branch.
