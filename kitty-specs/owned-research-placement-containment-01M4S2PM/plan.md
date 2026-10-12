# Implementation Plan: Owned Research Placement Containment

**Branch**: `issue-5882-owned-research-placement-and-plan` | **Date**: 2026-10-12 | **Spec**: `kitty-specs/owned-research-placement-containment-01M4S2PM/spec.md`
**Input**: Mission specification from `kitty-specs/owned-research-placement-containment-01M4S2PM/spec.md`

## Summary

`spec-kitty research` and the top-level `spec-kitty plan` wrapper are the two
authoring surfaces PR #6002 left without an owned selector. `research` resolves
its project/mission root via `find_repo_root()` / `get_project_root_or_exit()`,
both of which follow a linked owned checkout's `.git` pointer back to the
primary — so, run from an owned checkout, it scaffolds its four assets into the
primary (into a stale same-slug copy) or refuses `Mission not found`. The fix
threads a validated `OwnedCheckout` through `research` (mirroring
`mission_record_analysis.py` / `mission_setup_plan.py`): add `OwnedCheckoutOption`,
resolve once via `resolve_owned_or_adopt` (explicit flag or auto-adopt from an
owned cwd), set `project_root = repo_root = owned.owned_root`, and resolve the
three mission dirs from the owned checkout by threading `owned=owned` into the
placement seam. The top-level `plan` wrapper gains the same selector and forwards
it to the already-owned-aware `setup_plan` seam. No new resolver is introduced.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (CLI); `mission_runtime` placement seam; `specify_cli.core.owned_mission` ownership gate
**Storage**: filesystem (`kitty-specs/<slug>/` mission directories)
**Testing**: pytest; red-first `@pytest.mark.regression` through the real `research` entry point on the canonical `owned_checkouts` R/P/S fixtures with `r_snapshot` R-immutability assertions
**Target Platform**: Linux/macOS CLI
**Project Type**: single (CLI library)
**Performance Goals**: N/A (CLI command; no hot path)
**Constraints**: non-owned code path byte-for-byte behaviour-identical; no new root resolver (ADR `2026-08-12-1`, aligns with #6001); typed refusal before any write
**Scale/Scope**: two command surfaces (`research`, top-level `plan`) + one discovery prompt template + changelog

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — ownership resolved only through the existing
  `_owned_checkout` / `core.owned_mission` seam; placement only through
  `placement_seam(..., owned=owned)`. No parallel resolver. PASS.
- **Architectural alignment** — change is confined to the top adapter layer
  (`src/specify_cli/cli/commands/`); no layer-rule or shared-package-boundary
  change. PASS.
- **ATDD-first** — red-first regression through the pre-existing `research` entry
  point precedes the fix; it is RED on current main (confirmed). PASS.
- **Smallest-viable-diff / Locality of change** — edits are local to `research.py`,
  `lifecycle.py`, the research prompt, tests, and CHANGELOG. PASS.
- **Terminology** — "primary"/"owned"/"placement" used per the glossary; no
  retired terms. PASS.

No Charter Check violations → Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/owned-research-placement-containment-01M4S2PM/
├── spec.md              # Mission specification
├── plan.md              # This file
├── analysis-report.md   # Grounding note (two squads + reproduction)
├── tasks.md             # Work-package outline (/spec-kitty.tasks)
└── tasks/               # Work-package detail files
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/
├── research.py          # ADD OwnedCheckoutOption; resolve owned; thread owned= into the seam
├── _owned_checkout.py   # (reuse) OwnedCheckoutOption, resolve_owned_or_adopt, emit_owned_refusal
└── lifecycle.py         # top-level `plan`: expose + forward --owned-checkout to setup_plan

packs/built-in/missions/mission-steps/software-dev/research/
└── prompt.md            # surface the owned selector affordance

tests/integration/
└── test_owned_research_placement.py   # red-first regression (owned_checkouts/stale_root_copy/r_snapshot)

docs/changelog/CHANGELOG.md             # [Unreleased] entry
```

**Structure Decision**: Single-project CLI library. All edits land in the top
adapter layer (`src/specify_cli/cli/commands/`) plus the research discovery
prompt template, tests and changelog. The placement seam and ownership gate are
consumed, not modified.

## Complexity Tracking

*No Charter Check violations — none to justify.*

## Implementation Concern Map

### IC-01 — Research owned-checkout placement

- **Purpose**: Make `spec-kitty research` honour the owned checkout (explicit flag
  or auto-adopt) and never redirect authoring into an unowned/dirty primary.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001
- **Affected surfaces**: `src/specify_cli/cli/commands/research.py` (signature,
  root/mission resolution, `_read_mission_dir_or_exit` seam call); reuse
  `_owned_checkout.py`; `tests/integration/test_owned_research_placement.py`
- **Sequencing/depends-on**: none (the priority slice)
- **Risks**: the non-owned path must stay byte-for-byte identical (existing
  `test_research_read_surface.py` is the guard); `_read_mission_dir_or_exit` is
  called three times (STATUS_STATE, RESEARCH, FINALIZED_EXECUTION_PLAN) — all
  three must thread `owned=`; `validate_plan_filled` must read the owned `plan.md`.

### IC-02 — Top-level `plan` owned forwarding + discovery-prompt affordance

- **Purpose**: Expose `--owned-checkout` on the top-level `plan` wrapper and
  forward it to the owned-aware `setup_plan` seam; surface the owned selector in
  the research discovery prompt.
- **Relevant requirements**: FR-004, FR-005, NFR-001, C-002, C-003
- **Affected surfaces**: `src/specify_cli/cli/commands/lifecycle.py` (`plan`);
  `packs/built-in/missions/mission-steps/software-dev/research/prompt.md`
- **Sequencing/depends-on**: none (independent of IC-01; can land in the same WP)
- **Risks**: the top-level `plan` also runs an interactive `run_plan_interview`
  keyed on `locate_project_root()` — the interview is already skipped in `--json`
  (agent) mode, which is the owned-flow path; leave interactive-owned interview
  resolution as a documented follow-up rather than over-reaching here (C-003).
