# Tasks: The project-intent rename carries a deny entry with it

**Mission**: `project-intent-deny-rename-01M68J6A` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `kitty/mission-project-intent-deny-rename-01M68J6A` (single-branch mission)
**Tracker**: closes #6565

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: the rename carries a ledger deny entry (fails on the planning base) | WP01 | |
| T002 | `DenyListChoice.RENAME` + its narrowing docstring | WP01 | |
| T003 | Token step: deny keys join the stem-token rewrite, ledger target only, one save with the choice | WP01 | |
| T004 | Behaviour tests: legacy surface untouched, idempotence, other deny entries, duplicate spellings, dry run | WP01 | |
| T005 | Deny-list gate: pin the one new origin both directions + a positive control | WP01 | |
| T006 | Migration-level end state (all three entry points) + blast-radius run | WP01 | |
| T007 | ADR `2026-10-19-1`: Decision 4 fifth path, guard enumeration, dated amendment | WP02 | |
| T008 | `AGENTS.md` activation-ledger bullet + `docs/api/charter-commands.md` | WP02 | |
| T009 | `[Unreleased]` changelog entry + docs freshness check | WP02 | |

## Phase 1 — Core fix

### WP01 — The rename authority carries an exclusion

- **Prompt**: [tasks/WP01-rename-carries-denial.md](tasks/WP01-rename-carries-denial.md)
- **Goal**: A ledger project whose `deactivated_directives` names `NNN-mission-type-scope-directive`
  keeps that directive deactivated across the rename (FR-001), through the one rename mapping and the
  one ledger writer (FR-002, C-001, C-002), guarded by one new `DenyListChoice.RENAME` (FR-003) that
  the deny-list gate pins exactly and proves used (FR-004). A legacy surface's hand-written deny key
  is left alone (FR-005, C-004).
- **Priority**: P1 (MVP). **Dependencies**: none.
- **Independent test**: the new deny-rename test is RED on the planning base
  (`git stash`-free: run it before T002/T003) and GREEN on the WP's last commit; the deny-list gate
  and the rename suites are green; the gate's throwaway-offender test still fails a deny-dropping
  migration.

T001 Red-first: the rename carries a ledger deny entry (WP01)
T002 `DenyListChoice.RENAME` + docstring (WP01)
T003 Token step: deny keys join the stem-token rewrite (WP01)
T004 Behaviour tests (WP01)
T005 Deny-list gate pins + positive control (WP01)
T006 Migration-level end state + blast-radius run (WP01)

**Implementation sketch**: T001 (commit the failing test alone) → T002 → T003 (the test goes green)
→ T004 → T005 → T006.

**Risks**:
- The architectural gate goes red between T003 and T005 (the pins name the new origin); that is the
  expected mid-lane red — the merge bar is the WP tip. Do not weaken a pin to fix it.
- The deny rename must be a no-op on a legacy surface: `_refuse_legacy_deny` raises on a deny change
  there, so a wrong predicate turns the rename into a refusal on unmigrated projects (T004 covers it).
- Keep the write count at exactly one: no second `save` call for deny keys.

## Phase 2 — Contract docs

### WP02 — Document the fifth path and the fixed behaviour

- **Prompt**: [tasks/WP02-docs-fifth-path.md](tasks/WP02-docs-fifth-path.md)
- **Goal**: ADR Decision 4, `AGENTS.md` and `docs/api/charter-commands.md` name the rename as the
  fifth deny-list path and state its exact limit (it moves one entry between two spellings of the same
  artifact; it never adds or removes a denial), with an `[Unreleased]` changelog entry (FR-006).
- **Priority**: P2. **Dependencies**: WP01 (the code decides the wording).
- **Independent test**: the changelog entry passes the repository's changelog checks and
  `scripts/docs.check_docs_freshness --ci` reports `errors=0`; a reader of Decision 4 can name the
  fifth path and say what it may not do.

T007 ADR Decision 4 + dated amendment (WP02)
T008 `AGENTS.md` bullet + `docs/api/charter-commands.md` (WP02)
T009 Changelog entry + docs freshness (WP02)

**Risks**: the ADR is normative — do not let the wording read as "synthesis may now clear a denial".
Keep the pre-existing four paths' text intact and add the fifth as a narrowing exception.

## Dependencies

WP01 → WP02.

## Closeout (orchestrator, not a WP)

Issue-matrix verdict for #6565 → `fixed`; tracer files assessed; changelog and docs covered by WP02;
PR body records the pre-fix red and cites the pre-existing CI reds (#6798, #6801, #6816, #5927).
