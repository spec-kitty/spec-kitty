# Implementation Plan: charter packs refusal code convergence

**Branch**: `issue-6772-charter-packs-refusal-code` | **Date**: 2026-10-30 | **Spec**: kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/spec.md
**Input**: Mission specification from `kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/spec.md` (issue #6772)

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

`charter activate` and `charter deactivate` refuse a malformed `charter_packs` registry in
`.kittify/config.yaml` with different error codes (`ACTIVATION_FAILED` vs
`ACTIVE_CHARTER_CONFIG_INVALID`). The fix converges them on `ACTIVE_CHARTER_CONFIG_INVALID` by
raising a **typed registry error** at the one shared fail-closed registry read
(`require_declared_org_roots` in `src/charter/offering/drg/org_pack_config.py`, behind
`resolve_pack_chain(strict=True)`): a new `OrgPackRegistryUnreadableError` that subclasses both
`ActiveCharterConfigError` (so it carries the `ACTIVE_CHARTER_CONFIG_INVALID` code and the CLI's
existing `config_refusal` mapping catches it) and `ValueError` (so every existing strict reader
that catches `ValueError` — effective set, preset application, requirement-kinds loader — keeps its
documented behaviour). The "declared pack not fetched" case keeps raising a plain `ValueError`, so
`activate` keeps reporting `ACTIVATION_FAILED` with the `spec-kitty charter fetch` remedy. The
pinned asymmetry test is re-pinned and the asymmetry note in `docs/api/charter-commands.md` is
removed; a changelog entry is added.

Full grounding, cause chain and the rejected alternatives live in
`kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/research.md` (decisions D1–D3).

## Technical Context

**Language/Version**: Python 3.11 (package `spec-kitty-cli`, src layout under `src/`)
**Primary Dependencies**: typer/rich (CLI), pydantic, PyYAML (registry read); pytest (tests)
**Storage**: file-based — `.kittify/config.yaml` (org pack registry), activation ledger
**Testing**: pytest; fast suite for the CLI refusals (`tests/specify_cli/cli/commands/charter/test_activation_json_6525.py`), unit suite for the offering-layer seam (`tests/charter_offering/drg/test_org_pack_config_cr04_charter_packs.py`), and the strict readers' existing suites as regression guards
**Target Platform**: cross-platform CLI (Linux/macOS/Windows); CI on GitHub Actions
**Project Type**: single (Python CLI package)
**Performance Goals**: N/A (a refusal path; no hot loop touched)
**Constraints**: `charter.offering` must not import `charter.activation` at module load (lazy import in the raising helper, mirroring `org_pack_discovery._strict_error`); local UPPER_SNAKE refusal codes only; no full heavy suites in-mission (NO_FULL_HEAVY_SUITES_IN_MISSION)
**Scale/Scope**: one exception class + one raise-site change in the offering layer; one test re-pin; docs + changelog. No API, contract or schema change.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Single canonical authority: the typed error is raised at the ONE fail-closed registry read
  (`require_declared_org_roots`), not per-verb in the CLI; no message-text branching.
- [x] Architectural alignment: respects the `charter.offering` → `charter.activation` import
  direction (lazy import, as `org_pack_discovery._strict_error` already does in reverse).
- [x] ATDD-first: the defect is fixed red-first through the pre-existing CLI entry point (the
  pinned test is re-pinned to the converged expectation BEFORE the fix lands).
- [x] Terminology: uses the canonical terms (org pack registry, refusal, code, strict read).
- [x] No charter violations to justify; no Complexity Tracking rows.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings (decisions D1–D3)
├── checklists/          # Spec quality checklist
├── decisions/           # Decision Moments minted by the runtime
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/
├── charter/
│   ├── offering/drg/org_pack_config.py        # THE fix: typed registry error (require_declared_org_roots)
│   └── activation/                            # unchanged; ActiveCharterConfigError's home (activation_ledger.py)
└── specify_cli/cli/commands/charter/
    ├── activate.py                           # unchanged mapping (config_refusal arm already precedes the ValueError arm)
    └── deactivate.py                         # unchanged

tests/
├── specify_cli/cli/commands/charter/
│   └── test_activation_json_6525.py          # re-pin the malformed-charter_packs refusal to the converged code
├── charter_offering/drg/
│   └── test_org_pack_config_cr04_charter_packs.py   # seam-level: the typed error is raised and stays a ValueError
└── (existing suites of the strict readers, run as regression guards)

docs/
├── api/charter-commands.md                   # remove the asymmetry note; converge the code-table row
└── changelog/CHANGELOG.md                    # [Unreleased] entry
```

**Structure Decision**: single-project layout; only the paths above are touched. No new modules —
the exception class lives beside the seam that raises it.

## Implementation Concern Map

One concern; the mission is a single-seam defect fix.

### IC-01 — Typed registry error at the fail-closed registry read

- **Purpose**: Make the unreadable/malformed org-pack registry refusal carry the
  `ACTIVE_CHARTER_CONFIG_INVALID` code on every verb, by typing the error at the shared seam
  instead of mapping it per-verb.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-003
- **Affected surfaces**: `src/charter/offering/drg/org_pack_config.py` (raise site + class);
  `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py` (re-pin);
  `tests/charter_offering/drg/test_org_pack_config_cr04_charter_packs.py` (seam assertions);
  `docs/api/charter-commands.md`; `docs/changelog/CHANGELOG.md` (FR-005)
- **Sequencing/depends-on**: none
- **Risks**: the multiple-inheritance shape (`ActiveCharterConfigError` + `ValueError`) must be
  pinned by a test so a future refactor cannot drop the `ValueError` base silently (that would
  change three strict readers' behaviour). The deactivate-side message body differs in prose from
  the activate side; the mission converges the code, not the prose (research.md, open questions).
