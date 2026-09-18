# Tasks: Consistent Mission-Handle Resolution

**Mission**: `mission-handle-resolution-consistency-01M2TPWG` | **Branch**: `issue-4631-4682-mission-handle-resolution`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contract**: [contracts/cli-behavior.md](./contracts/cli-behavior.md)

Six work packages. WP01 is the shared foundation (all others depend on it); WP02–WP05 are
file-disjoint per-command fixes (parallel after WP01); WP06 is the cross-command regression
net (depends on WP02–WP05). ATDD-first: each WP writes its failing test before the fix.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: unit tests for `list_missions_for_selection` (0/1/N + legacy no-`mission_id`) | WP01 | |
| T002 | Add `list_missions_for_selection(main_repo)` (spec/meta population, mid8/friendly_name enrich, slug fallback) | WP01 | |
| T003 | Add sole-mission + count helpers on the shared population | WP01 | |
| T004 | Hoist canonical `MISSION_NOT_FOUND_MESSAGE` / `mission_not_found(handle)` constant | WP01 | |
| T005 | Add `__all__` enumerating full public surface + new symbols | WP01 | |
| T006 | Green + ruff/mypy on the seam | WP01 | |
| T007 | Red: `research --mission <bad>` phantom-write + not-found test (snapshot guard) | WP02 | [P] |
| T008 | Add `.exists()` gate after resolve in research.py before any mkdir/scaffold | WP02 | [P] |
| T009 | Emit canonical `Mission not found: <handle>`, non-zero, before scaffold | WP02 | [P] |
| T010 | Green + confirm no `kitty-specs/<bad>/` created | WP02 | [P] |
| T011 | Red: `plan`/`tasks --mission <bad>` truthful-not-found + disambiguate-regression tests | WP03 | [P] |
| T012 | Branch `_build_setup_plan_detection_error` on explicit `mission_flag` (not-found vs disambiguate) | WP03 | [P] |
| T013 | Ensure both call-sites (setup-plan, check-prerequisites) surface the not-found | WP03 | [P] |
| T014 | Preserve no-handle multi-mission disambiguate path | WP03 | [P] |
| T015 | Green + ruff/mypy | WP03 | [P] |
| T016 | Red: `merge --mission <bad>` fresh + `--resume` not-found; `--abort` tolerance tests | WP04 | [P] |
| T017 | Gate fresh path (merge.py:628) with `.exists()` → canonical not-found | WP04 | [P] |
| T018 | Gate `_dispatch_resume` (merge.py:391) before the no-state check | WP04 | [P] |
| T019 | Keep `merge/resolve.py` raw-slug fallback for `--abort`; leave `_dispatch_abort` ungated | WP04 | [P] |
| T020 | Green + confirm abort still tolerant | WP04 | [P] |
| T021 | Red: bare `next` 0/1/N discovery + legacy-sole-mission + FR-009-no-preflight-bypass tests | WP05 | [P] |
| T022 | Replace `_resolve_mission_slug` empty-branch raise with a typed missing-handle discovery signal | WP05 | [P] |
| T023 | Auto-select sole mission (1); carry listing (N) / empty (0) on the signal | WP05 | [P] |
| T024 | Caller (`next_cmd.py:195-217`) emits + exits: auto-proceed / list / nudge (human + JSON) | WP05 | [P] |
| T025 | Render listing as `slug (mid8) — friendly_name` + backfill nudge; JSON `available_missions` | WP05 | [P] |
| T026 | Keep nonexistent-but-present handle's clean not-found (regression) | WP05 | [P] |
| T027 | Green + ruff/mypy; assert usage semantics not the literal "Invalid value" | WP05 | [P] |
| T028 | Cross-command: nonexistent handle → canonical `Mission not found: <handle>` across fixed commands | WP06 | |
| T029 | NFR-001 snapshot guard across all fixed commands (in-process CliRunner) | WP06 | |
| T030 | FR-013 regression: already-correct commands still emit clean not-found (incl. identity/backfill + reconcile envelopes intact) | WP06 | |
| T031 | Legacy-mission cross-command count agreement (next vs plan/tasks) | WP06 | |
| T032 | Green + full blast-radius run | WP06 | |

---

## WP01 — Shared seam: mission population + canonical not-found constant [FOUNDATION]

**Goal**: Provide the one reusable population/selection helper and the one canonical
not-found message the rest of the mission consumes. **Priority**: P1 (blocks all).
**Independent test**: unit tests for the helper over 0/1/N missions incl. a legacy mission
without `mission_id`; the canonical constant importable and correctly formats a handle.

**Subtasks**: T001, T002, T003, T004, T005, T006
**Depends on**: none | **FRs**: FR-006, FR-012
**Prompt**: [tasks/WP01-shared-seam.md](./tasks/WP01-shared-seam.md)

## WP02 — research: existence gate (kill the phantom write)

**Goal**: `research --mission <bad>` refuses with the canonical not-found and writes nothing.
**Priority**: P1 (data corruption). **Independent test**: two real missions + a bad handle →
non-zero, `kitty-specs/` byte-identical before/after.

**Subtasks**: T007, T008, T009, T010
**Depends on**: WP01 | **FRs**: FR-001
**Prompt**: [tasks/WP02-research-gate.md](./tasks/WP02-research-gate.md)

## WP03 — plan/tasks: truthful not-found

**Goal**: An explicit unmatched handle yields `Mission not found: <handle>`, not the
disambiguate message; the no-handle multi-mission disambiguate path is preserved.
**Priority**: P1. **Independent test**: ≥2 missions + bad handle → not-found; no-handle + ≥2 → disambiguate.

**Subtasks**: T011, T012, T013, T014, T015
**Depends on**: WP01 | **FRs**: FR-002, FR-003
**Prompt**: [tasks/WP03-plan-tasks-notfound.md](./tasks/WP03-plan-tasks-notfound.md)

## WP04 — merge: truthful not-found + abort tolerance

**Goal**: `merge` (fresh and `--resume`) refuses a nonexistent handle with the canonical
not-found; `merge --abort` stays tolerant. **Priority**: P1.
**Independent test**: fresh + resume bad handle → not-found; abort bad handle → tolerant cleanup.

**Subtasks**: T016, T017, T018, T019, T020
**Depends on**: WP01 | **FRs**: FR-004, FR-005
**Prompt**: [tasks/WP04-merge-notfound.md](./tasks/WP04-merge-notfound.md)

## WP05 — next: missing-handle discovery

**Goal**: bare `next` auto-selects (1) / lists (N) / nudges (0) instead of a usage error;
nonexistent-but-present handle keeps its clean not-found. **Priority**: P2.
**Independent test**: 0/1/N missions incl. a legacy sole mission; no `Invalid value` usage error.

**Subtasks**: T021, T022, T023, T024, T025, T026, T027
**Depends on**: WP01 | **FRs**: FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-012
**Prompt**: [tasks/WP05-next-discovery.md](./tasks/WP05-next-discovery.md)

## WP06 — cross-command regression net

**Goal**: Prove the uniform behavior across commands and guard the pre-existing correct
commands (incl. the preserved identity/backfill + reconcile envelopes). **Priority**: P2.
**Independent test**: a single suite asserting the canonical message + snapshot invariance
across the fixed commands and count agreement on a legacy tree.

**Subtasks**: T028, T029, T030, T031, T032
**Depends on**: WP02, WP03, WP04, WP05 | **FRs**: FR-013
**Prompt**: [tasks/WP06-regression-net.md](./tasks/WP06-regression-net.md)

---

## Dependencies

```
WP01 ──┬── WP02 ──┐
       ├── WP03 ──┤
       ├── WP04 ──┼── WP06
       └── WP05 ──┘
```

## MVP scope

WP01 + WP02 (the shared seam + the only data-corruption defect) is the minimum shippable
slice. WP03/WP04/WP05 complete the consistency story; WP06 locks it against regression.
