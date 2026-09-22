---
work_package_id: WP02
title: Authoritative non-lane event-type registry (#4897)
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
planning_base_branch: fix/silent-destructive-write-hardening
merge_target_branch: fix/silent-destructive-write-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/silent-destructive-write-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/silent-destructive-write-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-silent-destructive-write-hardening-01M355VK
base_commit: 286b75cccb0cbfeb6cc7e65550337527c27bba81
created_at: '2026-09-22T18:43:39.627554+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_authoritative_non_lane_registry_4897.py
execution_mode: code_change
owned_files:
- src/specify_cli/status/lifecycle_events.py
- src/specify_cli/status/store.py
- src/specify_cli/migration/mission_state.py
- tests/migration/test_mission_state_repair.py
- tests/status/test_authoritative_non_lane_registry_4897.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile via `/ad-hoc-profile-load`
(profile: `python-pedro`, role: `implementer`). Adopt its identity, boundaries, and discipline
for the whole work package.

## Objective

Fix #4897: `spec-kitty doctor mission-state --fix` (and `spec-kitty upgrade`, which routes into the
same repair) quarantines the authoritative `DecisionPoint*` rows out of `status.events.jsonl` on a
healthy mission — exit 0, `errors=0` — and the advertised `doctor decisions --repair` then rebuilds
`index.json` from the emptied log to zero entries. The decision record becomes unreadable by every
CLI surface.

## Structural root cause (parallel authority / inverted ownership)

Two subsystems disagree about who owns `DecisionPoint*` rows in the shared `status.events.jsonl`
append log:
- **Decisions + durable reader treat the JSONL rows as authoritative.** `decisions/index_fold.py`
  rebuilds `index.json` from "the authoritative event log"; `status/store.py:597 is_non_lane_event`
  returns True for ANY row with `event_type` (explicitly naming `DecisionPoint*`).
- **The mission-state repair treats them as a prunable mirror.** `migration/mission_state.py:1919
  _is_preserved_non_lane_row` (:1972) preserves only retrospective + `LIFECYCLE_EVENT_TYPES`, and its
  docstring (:1940-1944) asserts DecisionPoint's "canonical store is elsewhere" — the inverse of the
  truth. It KNOWINGLY diverges from the reader (:1955-1956).

**Operator-chosen fix (decision `01M3560PHPQM617TH5MZHWRF8J`): one shared registry, not another
hand-maintained preserved-set entry** — closing the recurring whack-a-field class (#2376
retrospective, #3066 WPStatusChanged, #3541 review_result, #4897 DecisionPoint).

## Guidance per subtask

### T006 — Red-first regression test
Add `tests/status/test_authoritative_non_lane_registry_4897.py` with a `@pytest.mark.regression`
test pinned to #4897: build a healthy mission with one resolved Decision Moment, run
`doctor mission-state --fix`, assert the `DecisionPoint*` row count in `status.events.jsonl` is
unchanged and `doctor decisions` stays `clean: true` and `agent decision list` count unchanged. RED
before the fix. (Follow the QA repro script in the issue.)

### T007 — Create the authoritative non-lane event-type registry
Introduce ONE registry — a `frozenset[str]` of authoritative non-lane `event_type`s (at minimum
`DecisionPointOpened/Resolved/Deferred/Canceled/Widened`) plus a predicate — placed with the existing
status event-type authority (`status/lifecycle_events.py`, alongside `LIFECYCLE_EVENT_TYPES`, or a
clearly-named sibling). It must express the same authority the durable reader already applies (any
row bearing an authoritative `event_type`). Document that this is the single source both the reader
and every repair/prune consult.

### T008 — `is_non_lane_event` consults the registry
Refactor `status/store.py:597 is_non_lane_event` to derive its `event_type` decision from the new
registry (behavior-preserving for currently-preserved rows).

### T009 — `_is_preserved_non_lane_row` consults the registry
Make `migration/mission_state.py:_is_preserved_non_lane_row` DELEGATE to the shared registry/predicate
rather than maintaining a narrower parallel list. `DecisionPoint*` rows must now be preserved; the
already-preserved classes (annotation, retrospective, WPStatusChanged, review_result) must remain
preserved (no regression). Update the now-inverted docstring.

### T010 — Honest repair status
Ensure `_repair_mission` (:1671-1691) does not report `errors=0`/`status="repaired"` success when it
would quarantine a canonical row. With T009 no canonical rows are quarantined; add a guard/assertion
so a future divergence surfaces as an error rather than a silent success.

### T011 — Single-authority test + no-regression
Add a focused test asserting BOTH consumers (`is_non_lane_event` and `_is_preserved_non_lane_row`)
derive from the one registry (e.g., parametrize over the registry and assert agreement) — a
non-vacuous guard against the whack-a-field class reopening. Extend/adjust
`tests/migration/test_mission_state_repair.py` to cover DecisionPoint preservation and confirm the
other preserved classes are unaffected.

## Definition of Done

- T006 regression RED before, GREEN after.
- `doctor mission-state --fix` preserves `DecisionPoint*` rows; `doctor decisions` stays clean;
  `agent decision list` count stable.
- One registry; both consumers consult it; single-authority test present.
- Already-preserved classes unchanged (no regression).
- Blast radius green: `tests/status/`, `tests/migration/`, `tests/unit/migration/`,
  `tests/integration/migration/test_lifecycle_events_preserved.py`, decisions tests.
  `ruff`, `ruff format --check`, `mypy` clean. Touched functions ≤15 complexity.

## Reviewer guidance

Confirm the registry is a single authority (not a copied list); confirm `is_non_lane_event` and the
repair both consult it; confirm DecisionPoint rows survive `--fix`; confirm no regression to
retrospective/annotation/WPStatusChanged/review_result; confirm the regression test fails on
merge-base.
