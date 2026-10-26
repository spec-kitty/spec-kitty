# Research Specification: Why does `charter list` omit an org pack's in-force required directive?

**Mission Branch**: `issue-6417-charter-list-org-required`
**Created**: 2026-10-26
**Status**: Complete
**Research Type**: Case Study (code reading plus a reproduction against the installed CLI)

## Research Question & Scope

**Primary Research Question**: Why does `spec-kitty charter list` not name an org pack's
required directive that `spec-kitty doctor charter-packs` reports as org-required (#6417), and is
the cause a product gap, scenario drift, or both?

**Sub-Questions**:

1. Which in-force computation should the listing reuse, and through which seam?
2. Which consumers of `charter list --json` does a payload change affect?
3. Which red-first tests pin the fix, and can the Cucumber scenario run in this container?

**Scope**:

- **In Scope**: `src/specify_cli/cli/commands/charter/list_cmd.py`, the activation ledger and
  `PackContext` in-force readers, the org required floor readers, the
  `governance-in-force.feature` scenario and its Java step bindings, every repository consumer of
  `charter list --json`.
- **Out of Scope**: changing core activation semantics (ruling `required_always_active_divergence`;
  FR-023 stays as is), `doctor charter-packs`, the `--all` availability scan unification (#6012).
- **Boundaries**: `origin/main` at `e28ddabf` (4.0.0rc8).

**Expected Outcomes**:

- `research.md` with the root cause, decisions, the consumer list and the red-first tests.
- Input for the software-dev Mission that delivers the fix.

## Research Methodology Outline

### Research Approach

- **Method**: Case study.
- **Data Sources**: the source files named in `research.md`, issue #6417 and its triage comment,
  and a shell port of the scenario fixture run against the CLI installed from this branch
  (`research/repro.sh`).
- **Analysis Approach**: trace the listing's data path, compare it with the readers that decide
  what is in force, and confirm with the reproduction.

### Success Criteria

- The root cause is named with file and line references.
- Every repository consumer of `charter list --json` is listed.
- At least one red-first test is identified that can run in this container.

## Research Requirements

### Data Collection Requirements

- **DR-001**: Research MUST read the listing and in-force code paths at the base commit.
- **DR-002**: Sources are cited inline in `research.md` (file:line or command); no separate
  source register, since every source is a file in this repository.

### Analysis Requirements

- **AR-001**: Findings MUST be synthesized into decisions in `research.md`.
- **AR-002**: The reproduction MUST be runnable (`research/repro.sh <dir> old|fixed`).
- **AR-003**: Limitations (the JVM suite cannot run here) MUST be stated.

### Quality Requirements

- **QR-001**: All claims MUST be supported by a cited file or command; an uncited claim is
  labelled a hypothesis.

## Key Concepts & Terminology

- **Required floor**: the ids an org pack's `org-charter.yaml` lists under `required_<plural>`.
- **Absent key**: an `activated_<plural>` key missing from the activation ledger; what it puts in
  force is `ArtifactKind.effective_when_absent` (`"all"` or `"required"`).
- **In force**: admitted by `PackContext.admits` / `PackContext.effective_ids`.

## Evidence Tracking Guidance

Evidence is recorded inline in `research.md` with its source; the reproduction script is
`research/repro.sh`.
