---
description: "Work package task list for mission backfill-runtime-state-idempotent-claim-slots-01M67HR8"
---

# Work Packages: Backfill runtime state on a slug-identified legacy Mission

**Inputs**: Design documents from `kitty-specs/backfill-runtime-state-idempotent-claim-slots-01M67HR8/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, quickstart.md

**Tests**: Required by this Mission's spec (FR-005 – FR-008, NFR-003) and by charter
ATDD-First Discipline: the defect gets a failing test through the pre-existing entry point
before the fix.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each
work package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single package: `src/specify_cli/`, tests under `tests/`.

---

## Work Package WP01: Envelope identity for the seed claim carrier, proved red-first (Priority: P1) 🎯 MVP

**Goal**: Make `migrate backfill-runtime-state` converge on the #6689 Mission shape by minting the claim carrier's envelope `mission_id` as the value `meta.json` declares, while leaving the deterministic seed namespace, the verifier's tolerance set and the reader untouched.
**Independent Test**: The reported Mission fixture reaches `status_phase` snapshot authority through `spec-kitty migrate backfill-runtime-state --mission <slug>` (exit 0), a second run appends nothing, and the three fail-closed classes still abort on the same fixture.
**Prompt**: `tasks/WP01-envelope-identity-claim-carrier.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Red-first: build the reported Mission fixture and observe the engine-level failure (new test file)
T002 Red-first: prove the CLI entry point exits 1 on that fixture before the fix
T003 Fix: split declared mission id from seed namespace, and put the declared id on the carrier envelope
T004 Idempotency + namespace-stability rows (seed id unchanged, second run seeds nothing, pre-fix row stays sound)
T005 Fail-closed controls on the same fixture (tampered payload, missing seed, strip-before-verify) with paired positive control
T006 Green through the CLI entry point, plus the whole-shape regression rows for declared ULID and undeclared mission id
T007 Local gates: ruff, mypy, the touched migration suites

### Implementation Notes

- Test first, then fix, then re-run the same rows (record the pre-fix output in the PR).
- Keep `_claim_carrier` the single envelope authority; both `_build_seed_events` and
  `_legacy_contract_carriers` call it.
- Do not touch `src/specify_cli/status/store.py` (NFR-004) and do not add any tolerance to
  `_seed_row_mismatch` (C-003).

### Parallel Opportunities

- None inside this WP; the rows are written against one fixture and one seam.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Changing the seed namespace by accident would re-seed every existing corpus → T004 pins the
  seed id to its pre-fix value on the reported fixture.
- A test that only asserts `verify_backfill(...).ok` could pass if the verifier were weakened
  → T005 pairs every refusal with a positive control on the identical fixture.

---

## Work Package WP02: Operator-facing record — changelog and the cutover how-to (Priority: P2)

**Goal**: Record the user-facing change where an operator hitting the #6689 block will look: the `[Unreleased]` changelog entry and the cutover-guard troubleshooting table.
**Independent Test**: The changelog entry exists under `[Unreleased]` with the `(#6689)` reference and before/after, the how-to table row names the new behaviour, and `check_docs_freshness --ci` reports errors=0.
**Prompt**: `tasks/WP02-changelog-and-cutover-howto.md`
**Requirement Refs**: FR-001, FR-005, C-004

### Included Subtasks

T008 Write the `[Unreleased]` changelog entry for #6689
T009 Update the cutover-guard how-to so the recovery table names the slug-identified Mission shape
T010 Run the docs freshness gate and the legacy-terminology test

### Implementation Notes

- Bold impact-first lead with `(#6689)`, then before/after, under 1,200 characters.
- Only the docs surface this diff touches; do not rebuild the whole CLI reference on this
  shared host (brief: the installed CLI's global asset cache is not safe to race).

### Dependencies

- Depends on WP01 (the behaviour it documents must be the landed behaviour).

### Risks & Mitigations

- Docs freshness gate drift on a shared machine → regenerate only the touched surface and
  verify with `scripts.docs.check_docs_freshness --ci`.
