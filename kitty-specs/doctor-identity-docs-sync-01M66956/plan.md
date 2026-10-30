# Implementation Plan: doctor identity docs sync

**Branch**: `issue-6760-doctor-identity-docs-sync` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/doctor-identity-docs-sync-01M66956/spec.md`
**Input**: Mission specification from `kitty-specs/doctor-identity-docs-sync-01M66956/spec.md` (issue spec-kitty/spec-kitty#6760)

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the execution workflow.

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

Rewrite the stale `doctor identity` documentation in
`docs/migrations/mission-id-canonical-identity.md` from live CLI output: the
state list (`ok`/`legacy`/`conflict` → the live five states `assigned`,
`pending`, `legacy`, `orphan`, `residue`), the Step 2 and Step 4 JSON samples
(`status`/`total`/`ok`/`conflicts` → the live `summary`/`missions[]`/
`duplicate_prefixes`/`ambiguous_selectors`/`fail_on_triggered` contract), the
surrounding `conflicts > 0` prose, and the Step 3 backfill transcript. Add a
small structural test that pins the page's documented states and sample keys
to the imported live identity-audit JSON contract so the drift class that
caused #6760 fails CI instead of recurring. No changes under `src/`.

## Technical Context

**Language/Version**: Python 3.11 (test only; the page itself is Markdown)
**Primary Dependencies**: pytest; `specify_cli.status` (imported contract:
`IDENTITY_STATES`, `IdentityState.to_dict`) and
`specify_cli.cli.commands._identity_audit._build_identity_json` for the
report-key contract
**Storage**: N/A (docs page + test)
**Testing**: one structural test file in `tests/docs/` (precedent:
`tests/docs/test_artifact_placement_seam_page.py` — asserts structure and
citations, never prose). Red-first: it must fail on the pre-fix page.
**Target Platform**: repository docs (`docs/migrations/`) + CI gates
**Project Type**: single
**Performance Goals**: N/A
**Constraints**: docs-only change surface (no `src/` edits); every documented
state/key/sample grounded in a live run on this checkout (fixture project
allowed); page keeps its migration-runbook shape and the terminology of
`docs/api/cli-commands.md`'s `spec-kitty doctor identity` section
**Scale/Scope**: one page (~250 lines touched), one test file, one changelog
entry, docs index regeneration if required

All planning questions are answered; no `[NEEDS CLARIFICATION]` markers
remain. Grounding answers live in
`kitty-specs/doctor-identity-docs-sync-01M66956/research.md` (live contract,
fixture evidence, scope decisions).

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — pass. The page will mirror the CLI's own
  contract (`specify_cli.status.IDENTITY_STATES` / `_build_identity_json`)
  rather than inventing a second description; the new test imports the
  contract instead of restating it.
- **Architectural alignment** — pass. No structural boundary touched;
  `tests/docs/` is the canonical home for page-structure tests.
- **ATDD-first** — pass. The structural test is written red-first against the
  pre-fix page (SC-001).
- **Terminology adherence** — pass. State names and field names come verbatim
  from the live CLI help, which `docs/api/cli-commands.md` carries.
- **Locality of change / smallest viable diff** — pass. One page, one test,
  one changelog entry; adjacent stale prose fixed only where it is the same
  page-vs-live-output defect (research.md decision 3).
- **No violations to justify.**

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctor-identity-docs-sync-01M66956/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 output
├── checklists/          # Specify quality checklist
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
docs/migrations/mission-id-canonical-identity.md   # the page being rewritten
docs/changelog/CHANGELOG.md                        # [Unreleased] entry
tests/docs/test_mission_id_migration_page.py       # structural pin (new)
```

**Structure Decision**: single-project repo; the mission touches the
migration page, the changelog, and adds one test under `tests/docs/` (the
canonical home for doc-page structure tests per
`tests/docs/test_artifact_placement_seam_page.py` precedent). No `src/`
changes.

## Complexity Tracking

*Fill ONLY if Charter Check has violations that must be justified*

None — no charter violations.

## Implementation Concern Map

*Include this section when the mission has multiple distinct architectural areas that inform how tasks are decomposed.*

### IC-01 — Page rewrite from live output

- **Purpose**: Make the migration runbook's audit steps (Step 2 and Step 4)
  match the live `spec-kitty doctor identity` contract so an operator can
  read their real output off the page.
- **Relevant requirements**: FR-001, FR-002, FR-003
- **Affected surfaces**: `docs/migrations/mission-id-canonical-identity.md`
- **Sequencing/depends-on**: none
- **Risks**: over-rewriting (changing migration narrative that is still
  correct); mitigated by grounding every edit in the live runs recorded in
  `research.md` and touching only the state list, the samples, the
  conflicts-prose and the backfill transcript.

### IC-02 — Structural drift pin (red-first)

- **Purpose**: Fail CI when the page's documented state set or JSON sample
  keys diverge from the live identity-audit JSON contract.
- **Relevant requirements**: FR-004
- **Affected surfaces**: `tests/docs/test_mission_id_migration_page.py` (new)
- **Sequencing/depends-on**: IC-01 (the test is written red against the
  pre-fix page, then goes green with the rewrite)
- **Risks**: restating the contract by hand in the test (second source of
  truth) — mitigated by importing `IDENTITY_STATES`, `IdentityState.to_dict()`
  keys and the `_build_identity_json` report keys from `specify_cli`; also
  asserting structure (parsable fenced JSON blocks), not prose wording.
