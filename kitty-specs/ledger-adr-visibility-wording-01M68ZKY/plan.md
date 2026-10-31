# Implementation Plan: Reconcile the migration-ledger ADR's visibility wording

**Branch**: `issue-6362-adr-visibility-wording` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/ledger-adr-visibility-wording-01M68ZKY/spec.md`
**Input**: Mission specification from `kitty-specs/ledger-adr-visibility-wording-01M68ZKY/spec.md`

## Summary

The Accepted ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` still decides, in §5
and in its #E deliverable bullet, that visibility ships as a `spec-kitty doctor migrations`
sub-surface plus an `upgrade --list-applied` flag. Neither command exists; the ledger mission
that implemented the decision shipped exactly one read surface, `spec-kitty migrate ledger`
(`--json` emitting the same structured report), fed by the single pending source
`VersionDetector.applicable_migrations`. A closeout note in the ADR already records the
divergence — but a reader lands on §5 first, so the decision document itself is wrong about what
shipped.

The change is documentation-only, in three parts:

1. **Rewrite §5 and #E** to name `spec-kitty migrate ledger [--json]` and that single pending
   source, and re-frame the `doctor migrations` / `upgrade --list-applied` proposal as the
   rejected/historical alternative, with the reason it was not built.
2. **Add a narrow docs guard** that extracts every `spec-kitty …` command snippet from the ADR's
   current visibility decision (§5 body and the #E bullet) and asserts each resolves to a
   registered Typer command path. It is red on today's ADR (`doctor migrations` is unregistered)
   and green after the rewrite, so the wording cannot drift back to a phantom command.
3. **Update the page's inventory/changelog surfaces** that the edit touches (`updated:`
   frontmatter, ADR inventory regeneration if required, `[Unreleased]` changelog entry), and run
   the docs gates for the edited page.

No command alias, no ledger code, no migration-semantics change.

## Technical Context

**Language/Version**: Markdown (ADR) + Python 3.11 (guard test)
**Primary Dependencies**: `pytest`; `scripts.docs._typer_walker.walk` and
`scripts.docs.check_cli_reference_freshness.extract_referenced_paths` (reused, read-only); the
live `specify_cli.app` Typer surface
**Storage**: files — `docs/adr/4.x/*.md`, `docs/development/*.yaml` inventories, changelog
**Testing**: pytest subset `tests/docs/` (new guard + the ADR/docs freshness tests), plus the
docs gate scripts (`check_docs_freshness --ci`, spelling/structural lint for `docs/adr/**`)
**Target Platform**: repository CI (Linux); no runtime surface changes
**Project Type**: single project (documentation change inside a Python CLI repository)
**Performance Goals**: N/A — no runtime behaviour changes; the guard walks the Typer surface once
**Constraints**: documentation surface only (NFR-003); no new allowlist entries (NFR-002); the
ADR must keep its historical proposal text (C-003)
**Scale/Scope**: 1 ADR page edited, 1 new test module (~80 lines), 1 changelog entry, inventory
files only if regeneration requires them

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Note |
|---|---|---|
| Single canonical authority | PASS | The ADR is the single decision record and the shipped Typer path is the single command authority; the guard binds one to the other instead of adding a second list of command names. |
| Architectural alignment | PASS | Documentation and a docs test only; no `src/` boundary moves. |
| ATDD-first / DIRECTIVE_034 | PASS | The guard is written and shown red against the pre-fix ADR before the wording changes. |
| Terminology canon (Mission vs feature) | PASS | Uses "read surface", "pending source", "tracked/clone-local partition", "audit-only drift" as the ADR and `migrate_cmd.py` already do. |
| DIRECTIVE_024 Locality of Change | PASS | One ADR page plus its inventories; no sweep of other ADRs (recorded as a deliberate non-goal in research D4). |
| DIRECTIVE_025 Boy Scout Rule | PASS | The stale wording is the defect; no unrelated ADR prose is rewritten. |
| DIRECTIVE_041 (test only real behaviour) | PASS | The guard asserts a real invariant (current decision → registered command), not prose shape; no test pins arbitrary sentences. |
| DIRECTIVE_044 (do not edit shipped migrations) | PASS | No migration module is touched. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted suites only: `tests/docs/` selections and docs gate scripts. |
| Pre-existing Failure Reporting Rule | PASS | Any pre-existing red (e.g. #6801, #6816, #5927, #6798) is cited in the PR, never worked around. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ledger-adr-visibility-wording-01M68ZKY/
├── spec.md              # Mission specification
├── research.md          # Discovery + Phase 0 grounding (decisions D1–D4)
├── plan.md              # This file
├── tasks.md             # /spec-kitty.tasks output
└── tasks/               # Work-package files
```

### Source Code (repository root)

```
docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md   # §5 visibility decision, #E bullet,
                                                        #   closeout note; `updated:` frontmatter
docs/changelog/CHANGELOG.md                             # [Unreleased] entry (#6362)
tests/docs/test_migration_ledger_adr_visibility.py      # NEW: current-decision → registered path

# touched only if regeneration requires it:
docs/adr/4.x/index.md
docs/development/page-inventory.yaml
docs/development/docs-retrieval-index.yaml
```

**Structure Decision**: single project. The change is a documentation reconciliation inside an
existing accepted ADR plus one docs guard; no new package, module boundary or CLI surface.

## Implementation Concern Map

### IC-01 — Reconcile §5 and #E with the shipped surface

- **Purpose**: Make the ADR's current visibility decision name the command that exists, and keep
  the rejected proposal as clearly marked history.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, C-001, C-002, C-003, SC-001, SC-002
- **Affected surfaces**: `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` (§5 body, the #E
  bullet, the closeout note at ~391-395, `updated:` frontmatter)
- **Sequencing/depends-on**: none
- **Risks**: the historical paragraph must not re-introduce a `spec-kitty`-prefixed phantom path
  that the guard would catch; keep the rejected names as bare prose. Do not restate partition /
  pending / drift semantics differently from `migrate_cmd.py`'s tokens
  (`in-place` / `recorded-elsewhere` / `pending`, drift reported only).

### IC-02 — Red-first docs guard on the current visibility decision

- **Purpose**: Fail when the ADR's current visibility decision names a command path that is not
  registered, so the wording cannot silently drift back.
- **Relevant requirements**: FR-005, SC-001
- **Affected surfaces**: `tests/docs/test_migration_ledger_adr_visibility.py` (new)
- **Sequencing/depends-on**: the red run happens **before** IC-01's rewrite; the same test proves
  green after it
- **Risks**: set `SPEC_KITTY_ENABLE_SAAS_SYNC` / `SPEC_KITTY_NO_UPGRADE_CHECK` before importing
  `specify_cli` (the walker is read-only but the app import is not side-effect free); scope the
  scan to the two sections so unaffected historical prose in other ADRs is out of scope.

### IC-03 — Inventory, changelog and docs gates

- **Purpose**: Keep the edited page consistent with the generated documentation surfaces and
  record the user-facing wording change.
- **Relevant requirements**: NFR-001, NFR-002, SC-003, SC-004
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`; `docs/adr/4.x/index.md`,
  `docs/development/page-inventory.yaml`, `docs/development/docs-retrieval-index.yaml` only if the
  regenerators report a diff
- **Sequencing/depends-on**: IC-01
- **Risks**: the docs regenerators read a shared machine-local asset cache in this batch
  environment (see the batch brief); regenerate only this page's sections and verify with
  `check_docs_freshness --ci` (errors=0) rather than a full rebuild.

## Phase 0 / Phase 1 notes

Phase 0 research is `research.md` (discovery decisions D1–D4: the shipped surface, the
no-implementation constraint, the token/vocabulary match, and the scoped guard). Phase 1 design
artifacts are not separately scaffolded for this mission type; the affected decisions, the
historical rendering, and the guard contract are captured in `spec.md` "Key Entities", the
concern map above, and `research.md`.
