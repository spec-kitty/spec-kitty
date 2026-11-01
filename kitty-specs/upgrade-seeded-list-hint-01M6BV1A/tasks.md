# Tasks: The upgrade hint recognises an activation list a released preset wrote

**Mission**: `upgrade-seeded-list-hint-01M6BV1A` · **Branch**: `issue-6684-upgrade-seeded-list-hint` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: a list set-equal to a released `default` preset list must produce the seeded-list hint (fails on `main`) | WP01 | |
| T002 | Red-first: a released preset list plus an interview id the preset lacks must also hint | WP01 | [P] |
| T003 | Guard: a hand-picked two-id list and a today's-in-force list keep their current outcomes; activation surface stays byte-identical | WP01 | [P] |
| T004 | `_seeded_list_hints` gains the released-preset provenance, bounded by today's in-force set, one hint per kind | WP01 | |
| T005 | Warning text says which provenance it reports, the listed/selected counts, and both narrowing commands | WP01 | [P] |
| T006 | ADR amendment `## Amendment 2026-11-01 (#6684)` records the ruling, the refused alternative and the residual | WP02 | |
| T007 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry naming #6684 | WP02 | [P] |
| T008 | Module docstring states both provenances and the residual | WP01 | [P] |

## Phase 1 — Red first, then the hint

### WP01 — The released-preset provenance in the seeded-list hint

**Goal**: a present activation list a released `default` preset wrote is recognised and warned about, whatever the catalogue has grown to since; nothing is written. **Priority**: P1. **Prompt**: [tasks/WP01-released-preset-hint.md](tasks/WP01-released-preset-hint.md)
**Independent test**: `uv run pytest tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py` — the two new cases are red before T004 and green after, and the existing cases never change outcome.

T001 Red-first: a list set-equal to a released `default` preset list must produce the seeded-list hint (fails on `main`) (WP01)
T002 Red-first: a released preset list plus an interview id the preset lacks must also hint (WP01)
T003 Guard: a hand-picked two-id list and a today's-in-force list keep their current outcomes; activation surface stays byte-identical (WP01)
T004 `_seeded_list_hints` gains the released-preset provenance, bounded by today's in-force set, one hint per kind (WP01)
T005 Warning text says which provenance it reports, the listed/selected counts, and both narrowing commands (WP01)
T008 Module docstring states both provenances and the residual (WP01)

Dependencies: none. Risk: the superset test (`preset ⊆ listed ⊆ preset ∪ selected`) is easy to loosen into "any list larger than the selection"; T003 is the tripwire.

## Phase 2 — The decision record

### WP02 — The ADR amendment, the changelog and the module docstring

**Goal**: the ruling (no reset, warn-only, hint covers released-preset seeds), the refused alternative and the residual are readable without the diff. **Priority**: P1. **Prompt**: [tasks/WP02-decision-record.md](tasks/WP02-decision-record.md)
**Independent test**: read the amendment and the changelog entry; each states the decision, the alternative refused and the residual. `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0.

T006 ADR amendment `## Amendment 2026-11-01 (#6684)` records the ruling, the refused alternative and the residual (WP02)
T007 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry naming #6684 (WP02)

Dependencies: T007 reads naturally after T004/T005 (the behaviour it describes). Risk: an ADR amendment that restates the code instead of the decision; keep it to the ruling, the alternative and the residual.
