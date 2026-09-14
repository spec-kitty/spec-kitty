# Mission Specification: Mission-create idempotency guard

**Mission**: mission-create-idempotency-guard-01M2FNZ8
**Issue**: #4033 (defect 1 — no idempotency guard on mission creation)

## Intent Summary

`spec-kitty specify` / `agent mission create` invoked twice for the same intent currently
creates **two** missions (different mid8, both `{"result":"success"}`, both exit 0) — a
silent duplicate a trainee hit while following the docs. Add a **fail-closed idempotency
guard** on the single create seam (`core/mission_creation.create_mission_core`), with an
**abandonment-aware auto-allow** and an **explicit override** for the legitimate cases.

Design (operator-decided):
- **Duplicate key = same `mission_slug` AND same `mission_type`.** A `research` and a
  `software-dev` mission sharing a name are legitimately different work.
- **Abandonment-aware:** if the only prior same-key mission is *abandoned* — canceled, or
  genesis / no lifecycle events / spec never committed (never actually worked) — the guard
  does **not** fire; the common "I gave up and re-ran" case just works.
- **Escape hatch:** an explicit `--allow-duplicate` flag (on `agent mission create` and
  `specify`, threaded to `create_mission_core(allow_duplicate=True)`) creates a second
  *live* same-key mission on purpose; the programmatic factory passes it for volume creation.

Primary actor: an operator (or agent host, or the factory) running mission creation.
Invariant that must always hold: **no orphan scaffold on refusal** (the guard runs before
any scaffold/branch is written), and the create seam is the single authority (all callers
covered).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Re-running the same create is refused, not silently duplicated (P1)

An operator runs `agent mission create "task-list"` (software-dev), then runs the exact
same command again. Today they get two `task-list-<mid8>` missions. After this mission the
second create is **refused** with an error naming the existing mission and the
`--allow-duplicate` override, and **no scaffold is written**.

**Acceptance**: a second same-slug+same-type create against a live prior mission raises
`MissionCreationError` before scaffold write; `kitty-specs/` contains exactly one mission.

### User Story 2 - Re-create after abandonment just works (P1)

An operator creates a mission, cancels it (or never commits its spec), then re-runs the
create for the same name. The guard does **not** fire — the prior mission is abandoned, so
a fresh one is created without any flag.

**Acceptance**: with the prior same-key mission canceled / genesis-only, a re-create
succeeds with no `--allow-duplicate` and produces one new live mission.

### User Story 3 - Deliberate second mission + factory volume (P2)

An operator genuinely wants a second mission with the same name; they pass
`--allow-duplicate`. The factory creating missions programmatically at volume passes the
same flag. Both succeed.

**Acceptance**: `--allow-duplicate` (or `create_mission_core(allow_duplicate=True)`)
overrides the guard and creates the second live same-key mission.

### Edge Cases

- Same slug, **different** mission_type → allowed (not a duplicate).
- Abandonment undeterminable (corrupt/unreadable prior mission state) → **fail closed**: treat as live and refuse (safer; override available).
- The prior mission is merged/done → treated as live for guard purposes (a completed same-name mission still signals a likely re-run mistake); overridable.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-001 | `create_mission_core` refuses, with `MissionCreationError` raised **before** any scaffold/branch is written, when an existing **non-abandoned** mission shares the same `mission_slug` AND `mission_type`. | Proposed |
| FR-002 | The refusal message names the existing mission (slug + mid8) and the `--allow-duplicate` override. | Proposed |
| FR-003 | The guard does **not** fire when every prior same-key mission is abandoned (canceled, or genesis / no lifecycle events / spec never committed); a re-create then succeeds with no flag. | Proposed |
| FR-004 | An explicit `--allow-duplicate` flag on `agent mission create` and `/spec-kitty.specify`, threaded to `create_mission_core(allow_duplicate=True)`, overrides the guard; the programmatic factory path passes it. | Proposed |

### Non-Functional Requirements

| ID | Requirement | Threshold / Measure | Status |
|----|-------------|---------------------|--------|
| NFR-001 | No behavior change for the non-duplicate case. | Existing `tests/core` mission-creation tests pass unchanged. | Proposed |
| NFR-002 | No orphan scaffold on refusal. | On a guarded refusal, `kitty-specs/` and lane branches are unchanged (asserted). | Proposed |
| NFR-003 | Code quality + red-first. | ruff/format/mypy clean; complexity ≤15; an issue-pinned `@pytest.mark.regression` repro is RED through the real entry point before the fix. | Proposed |

### Constraints

| ID | Constraint | Status |
|----|-----------|--------|
| C-001 | The guard lives at the single create seam (`create_mission_core`), so CLI, specify, and factory callers are all covered. | Active |
| C-002 | Fail closed on ambiguity: if abandonment cannot be determined, treat the prior mission as live and refuse. | Active |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- Running the documented create twice yields **one** mission + an actionable refusal, not two silent successes.
- An operator who canceled/abandoned a mission can re-create the same name with **no** extra flag.
- A deliberate second mission (and the factory) works via `--allow-duplicate`; existing non-duplicate creation is unchanged (test suite green).
