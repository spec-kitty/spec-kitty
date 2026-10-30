---
description: "Work package task list for #6757 — audit collisions judged on selectable Missions"
---

# Work Packages: Audit collisions only between selectable Missions

**Inputs**: Design documents from `kitty-specs/audit-collision-selectable-missions-only-01M66YHT/`
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (user stories),
[research.md](./research.md) (decisions D-1…D-6)

**Tests**: Required. This is a defect fix (issue #6757); the failing test through the
existing entry point lands before the fix (DIRECTIVE_034, ATDD-first).

**Organization**: Two work packages. WP01 carries the red-first engine contract
test and the ~14-line production change; WP02 carries the user-facing changelog
entry and the one doc page whose wording states the audit's collision rule.

**Prompt Files**: `kitty-specs/audit-collision-selectable-missions-only-01M66YHT/tasks/WP01-*.md`,
`…/tasks/WP02-*.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/` at the repository root.

---

## Work Package WP01: Red-first engine contract and the collision-population split (Priority: P1) 🎯 MVP

**Goal**: Make `run_audit()` judge `DUPLICATE_PREFIX` and `AMBIGUOUS_SELECTOR`
on the selectable-Missions population while every other finding keeps the
engine's own `is_mission_dir` population, and pin both directions in
`tests/audit/`.

**Independent Test**: `uv run pytest tests/audit/test_engine_keeps_its_mission_rule.py -q`
— the rewritten file fails on the pre-fix engine (fake collision present) and
passes after the split, while the real-collision cases pass in both states.

**Prompt**: `kitty-specs/audit-collision-selectable-missions-only-01M66YHT/tasks/WP01-engine-collision-population-split.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, SC-001, SC-002, SC-003, SC-004, SC-005

### Included Subtasks

T001 Rewrite `tests/audit/test_engine_keeps_its_mission_rule.py` around one shared fixture family: the #6757 fake-collision fixture (`001-real` + committed `001-tracked-spec-only`) and the real-collision fixtures (`080-alpha`/`080-beta`; `081-legacy`/`081-real`; the three-member `082-alpha`/`082-beta`/`082-leftover` group)
T002 [P] Add the non-git-root and pre-identity edge cases to the same fixture family (spec.md-only folder on a non-git root; tracked id-less `meta.json` still colliding)
T003 Run the new tests against the unmodified engine and record the red output (the fake-collision assertion must fail; the real-collision assertions must pass) — `spec-kitty agent tasks add-history WP01 --note …`
T004 Split the populations in `src/specify_cli/audit/engine.py`: add the residue-aware walk in `run_audit()`, thread it into `_compute_repo_findings_by_slug()`, call `find_duplicate_prefixes(repo_root, residue_aware=True)` and `find_ambiguous_selectors(selectable_states)`, leave `DUPLICATE_MISSION_ID` and the identity index on the engine population, and update the module docstring's step list
T005 Correct the now-false contract prose: the four `src/specify_cli/status/identity_audit.py` docstrings (module, `audit_repo`, `find_duplicate_prefixes`, `find_ambiguous_selectors`) and the inline `#5875 / FR-008` comment in `run_audit()` — same PR, no behaviour change
T006 Re-run the new tests green, then the blast radius: `tests/audit/`, `tests/doctor/test_identity_audit.py`, `tests/context/test_is_mission_dir.py`, `tests/integration/test_colliding_mission_flow.py`
T007 Prove the half-by-half dependency: revert only the `find_duplicate_prefixes(..., residue_aware=True)` half and confirm the duplicate-prefix assertion goes red; restore, revert only the `find_ambiguous_selectors(selectable_states)` half and confirm the selector assertion goes red; restore
T008 Record the CLI-level exit-code proof: `doctor mission-state --audit --fail-on error` exits 1 on the #6757 fixture (residue folder's `IDENTITY_MISSING`) and 0 on a clean repository

### Implementation Notes

- The engine keeps `audit_repo(options.repo_root)` for `identity_index` —
  `IDENTITY_MISSING` on a `meta.json`-less folder is the #5875 contract and must
  not move.
- The collision groups are **rebuilt** over the selectable population by the
  existing helpers; never filter group members afterwards (research D-3).
- `residue` rows never carry a `mission_id`, so `DUPLICATE_MISSION_ID` has no
  reason to change population.
- No new public function, parameter or module: `residue_aware` already exists on
  both helpers.

### Parallel Opportunities

- T002 is a separate test file section from T001 but shares the fixture helper;
  run sequentially unless the helper is landed first.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Post-filtering a group would silence a real collision when a residue folder
  joins it → build groups from the selectable population (T001's three-member
  case pins this).
- Accidentally narrowing `IDENTITY_MISSING` would change the `--fail-on error`
  gate → T001 keeps the folder's `IDENTITY_MISSING` assertion on the same
  fixture and T007 pins the exit code.
- Extra walk cost → measured at ~0.07 s engine + ~0.04 s collision pair on a
  210-Mission scratch repo; the assertion in T005 keeps the identity-audit
  performance test in the blast radius.

---

## Work Package WP02: Changelog and doc wording (Priority: P2)

**Goal**: Tell users what changed for them (their audit stops reporting a fake
collision, real ones are unchanged) and correct any doc that states the audit's
collision rule.

**Independent Test**: Read the `[Unreleased]` entry — impact-first bold lead,
`(#6757)`, before/after, under 1,200 characters — and confirm the doc page that
describes `doctor mission-state --audit` / `doctor identity` matches the shipped
behaviour.

**Prompt**: `kitty-specs/audit-collision-selectable-missions-only-01M66YHT/tasks/WP02-changelog-and-docs.md`
**Requirement Refs**: C-003, SC-001

### Included Subtasks

T009 Add the `[Unreleased]` entry to `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink to it) with the impact-first bold lead, `(#6757)`, and before/after in the house style of the #5875 entry
T010 Correct `docs/api/cli-commands.md` where it documents the audit's collision reports, if its wording claims residue folders participate (leave it untouched if it already implies selectable Missions only, and say so in the PR)

### Implementation Notes

- Only user-facing surfaces. No ADR: no architectural boundary moves, the
  read-side rule is unchanged and reused.
- The `IDENTITY_MISSING` `backfill-identity` remedy on a `meta.json`-less folder
  is explicitly **out of scope** (issue #6757 asks only to keep that finding);
  name it in the PR's `## Deferred` section instead of changing it.

### Dependencies

- Depends on WP01 (the entry describes shipped behaviour).

### Risks & Mitigations

- A changelog entry that overclaims ("collisions are no longer reported") would
  mislead → the wording says real collisions are unchanged, with the residue
  exclusion named.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: WP02's changelog draft can start once WP01's tests are
  green; keep the entry's wording for after the diff is final.
- **MVP Scope**: WP01 alone fixes the reported defect; WP02 is the user-facing
  hand-off.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01, WP02 |
| C-003 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Rewrite the engine contract test around one fixture family | WP01 | P1 | No |
| T002 | Non-git-root and pre-identity edge cases | WP01 | P1 | Yes |
| T003 | Record the red output before the fix | WP01 | P1 | No |
| T004 | Two-population split in the engine | WP01 | P1 | No |
| T005 | Correct the now-false `identity_audit` docstrings | WP01 | P1 | Yes |
| T006 | Green run + blast-radius suites | WP01 | P1 | No |
| T007 | Half-by-half revert proof | WP01 | P1 | No |
| T008 | CLI exit-code proof (`--fail-on error`) | WP01 | P1 | No |
| T009 | Changelog `[Unreleased]` entry (#6757) | WP02 | P2 | No |
| T010 | Correct the audit collision-rule doc wording | WP02 | P2 | No |
