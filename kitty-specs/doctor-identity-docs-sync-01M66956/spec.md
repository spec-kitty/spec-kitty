# Mission Specification: doctor identity docs sync

**Mission Branch**: `issue-6760-doctor-identity-docs-sync`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6760 — "docs/migrations/mission-id-canonical-identity.md: doctor identity states and JSON sample no longer match real output". Follow-up from the pre-merge squad on #5875. Guidance from the operator: ground the rewrite in live `spec-kitty doctor identity --json` output (a throwaway fixture project is fine), keep the page in the shape `docs/api/cli-commands.md` uses, run the docs gates listed for a doc change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator audits a legacy project by the book (Priority: P1)

An operator upgrading a pre-3.2 project follows
`docs/migrations/mission-id-canonical-identity.md` step by step. At Step 2 they
run `spec-kitty doctor identity --json` and compare what the CLI prints against
the page's state list and JSON sample. Today the page names states `ok`,
`legacy` and `conflict` and shows a sample with `status`, `total`, `ok`,
`conflicts` and `dir`/`mission_slug` rows — none of which the CLI prints. The
operator cannot tell whether their project is healthy. After this mission, the
page's state list and samples are the live five-state contract, so the operator
can read their real output directly off the page.

**Why this priority**: The page is the migration runbook; every other step keys
off the audit's states and counts. Wrong states and a wrong sample make the
whole guide unusable at its first verification point.

**Independent Test**: Run `spec-kitty doctor identity --json` on a fixture with
a legacy mission and compare, field by field, against the page's sample; and
diff the page's state list against the command's live `--help` text (the same
contract `docs/api/cli-commands.md` carries).

**Acceptance Scenarios**:

1. **Given** the migration page, **When** a reader lists the `doctor identity`
   states it documents, **Then** they get exactly `assigned`, `pending`,
   `legacy`, `orphan`, `residue` with the live definitions (mission_id
   present/absent × mission_number non-null/null, plus the residue rule).
2. **Given** the migration page's Step 2 JSON sample, **When** it is parsed and
   compared with the keys of a live `spec-kitty doctor identity --json` report,
   **Then** top-level keys, `summary` keys and `missions[]` row keys match
   exactly (`path`, `slug`, `mission_id`, `mission_number`, `state`, `error`,
   `residue_reason`), including `duplicate_prefixes`, `ambiguous_selectors`,
   `fail_on_triggered` and the conditional `residue_remedies`.
3. **Given** the page's Step 4 clean-audit sample, **When** compared with live
   output for a fully backfilled project, **Then** it matches the same
   contract (no `status`/`total`/`ok`/`conflicts` keys).

---

### User Story 2 - The page cannot silently drift again (Priority: P2)

A maintainer lands a future change to the `doctor identity` JSON contract.
Today nothing fails: `docs/api/cli-commands.md` is guarded by the CLI-reference
freshness check, but `docs/migrations/mission-id-canonical-identity.md` has no
guard, which is exactly how #6760 happened. After this mission, a structural
test pins the page's state list and sample keys to the live report builder, so
a contract change that leaves the page behind turns CI red.

**Why this priority**: The fix is only durable if the drift class is caught;
without a pin the same issue reopens at the next contract change.

**Independent Test**: Mutate the page's sample (remove a key, rename a state)
in a scratch checkout; the structural test fails. Restore it; the test passes.

**Acceptance Scenarios**:

1. **Given** the structural test, **When** the page's documented state list or
   JSON sample keys diverge from `specify_cli`'s live identity-audit JSON
   contract, **Then** the test fails.
2. **Given** the page as rewritten by this mission, **When** the test runs on
   an unmodified checkout, **Then** it passes.

### Edge Cases

- What if a `kitty-specs/` child is not a Mission at all? The page already
  documents the `residue` rule and remedies from #5875; the rewrite keeps that
  text and only fixes the state list and samples around it.
- What if the live output contains a conditional key (`residue_remedies`
  appears only when a residue row exists)? The sample must show it as
  conditional, not unconditional, so an operator with a clean project is not
  told to expect it.
- What about the stale prose around the samples (`conflicts > 0`, the
  backfill "refuses to run while conflicts are present")? The live backfill
  has no conflict gate and prints a summary table, not the "Scanning
  kitty-specs/ ... minted ..." transcript the page shows; the same-page
  corrections are in scope because they are the same defect class (page vs
  live output) on the same audit flow.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | State list matches the live contract | As an operator following the migration runbook, I want the page's `doctor identity` state list to name exactly the five live states with their live definitions, so that I can classify my own audit output. | High | Open | [build] | no |
| FR-002 | JSON samples match live output | As an operator, I want the Step 2 and Step 4 JSON samples to have the same top-level keys, `summary` keys, `missions[]` row keys and value shapes as a live `spec-kitty doctor identity --json` report, so that I can compare my output field by field. | High | Open | [build] | no |
| FR-003 | Stale prose and backfill transcript corrected | As an operator, I want the prose around the samples to stop referencing removed keys and states (`status`, `total`, `ok`, `conflicts`, `conflict`) and the Step 3 backfill transcript to match the live `migrate backfill-identity` summary output, so that no step of the runbook contradicts the CLI. | Medium | Open | [build] | no |
| FR-004 | Structural pin against drift | As a maintainer, I want a structural test that fails when the page's documented states or JSON sample keys diverge from the live identity-audit JSON contract, so that this drift class cannot silently recur. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Docs gates stay green | `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0, the committed docs index is fresh after `docs_index --write`, `freshen_adr_inventory` is a no-op, and `tests/architectural/test_no_legacy_terminology.py` passes. | Quality | High | Open |
| NFR-002 | Page shape preserved | The rewrite keeps the page's migration-runbook structure (frontmatter, section order, cross-references) and uses the same terminology as `docs/api/cli-commands.md`'s `spec-kitty doctor identity` section. | Usability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Docs-only change surface | No changes under `src/`; the test added by FR-004 reads the page and asserts against the existing `specify_cli` JSON contract (it must not restate the contract by hand where it can import it). | Technical | High | Open |
| C-002 | Grounded in live output | Every documented state, key and sample value must be reproduced from a live CLI run on this checkout (fixture project allowed), not composed from memory. | Process | High | Open |

### Key Entities *(include if the mission involves data)*

- **Identity audit report**: the `doctor identity --json` payload — `summary`
  (per-state counts), `missions[]` (per-folder rows), `duplicate_prefixes`,
  `ambiguous_selectors`, `fail_on_triggered`, conditional `residue_remedies`.
- **Identity state**: one of `assigned`, `pending`, `legacy`, `orphan`,
  `residue` (the four Mission states of the identity-audit contract plus the
  #5875 residue rule).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A structural test proves the page's documented state set and JSON sample keys equal the live `doctor identity --json` contract; it fails on the pre-fix page (red-first) and passes after — [ratchet] · no-op passable: no
- **SC-002**: All four docs gates named in the procedure (docs_index, freshen_adr_inventory, check_docs_freshness --ci, no-legacy-terminology) pass on the PR head — [build] · no-op passable: no
- **SC-003**: No occurrence of the removed contract (`"status"`, `"conflicts"`, `state: ok`, `state: conflict`) remains anywhere in the page — [build] · no-op passable: no
