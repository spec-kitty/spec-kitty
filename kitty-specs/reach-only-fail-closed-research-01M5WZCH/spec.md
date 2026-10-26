# Research Specification: Why does an unreadable synthesis manifest deliver tactics of an inactive directive?

**Mission Branch**: `issue-6454-reach-only-fail-closed`  
**Created**: 2026-10-26  
**Status**: Complete  
**Research Type**: Case Study (code inspection plus live reproduction)

## Research Question & Scope

**Primary Research Question**: Where does reach-only membership fail open when the synthesis
manifest cannot be read, and which callers and tests does a fix touch? (#6454)

**Sub-Questions**:

1. Is `reach_only._manifest_slugs` the only place the read error is swallowed?
2. Which callers of `reach_only_ids` / `_manifest_slugs` change behaviour under a fix?
3. Which tests must go red first?

**Scope**:

- **In Scope**: `src/charter/activation/synthesizer/reach_only.py` and its callers in
  `action_governance_bundle.py`, `compiler.py` and the synthesize append path.
- **Out of Scope**: ledger concurrency (#6453), repair guidance (#6455), the other sibling
  synthesis fixes (#6456).
- **Boundaries**: `origin/main` at `e28ddabf`.

**Expected Outcomes**:

- A confirmed root cause, a caller table and a red-first test list in `research.md`, which
  the follow-up software-dev Mission specifies from.

## Research Methodology Outline

### Research Approach

- **Method**: Case Study
- **Data Sources**: the source tree, the existing tests in `tests/charter/synthesizer/`, the
  issue and its triage comments.
- **Analysis Approach**: read every caller; reproduce the fail-open through the real bundle.

### Success Criteria

- Root cause reproduced live (not inferred).
- Every caller of `reach_only_ids` and `_manifest_slugs` classified.
- Red-first tests named for tactics and styleguides.

## Research Requirements

### Data Collection Requirements

- **DR-001**: Research MUST read every caller of `reach_only_ids` and `_manifest_slugs`.
- **DR-002**: Sources are the files cited in `research.md` (file and function names).

### Analysis Requirements

- **AR-001**: Findings MUST be synthesized into `research.md` (decisions, evidence, open questions).
- **AR-002**: The reproduction MUST be repeatable from the existing test fixture.
- **AR-003**: Limitations MUST be explicitly identified.

### Quality Requirements

- **QR-001**: All claims MUST be supported by a cited file or the reproduction output.

## Key Concepts & Terminology

- **Reach-only artifact**: a synthesized tactic or styleguide that reaches action context
  only through its directive's `suggests` edge, never as a root.
- **Synthesis manifest**: `.kittify/charter/synthesis-manifest.yaml`, the registry of
  synthesized artifacts.
- **Created-artifacts record**: `.kittify/charter/synthesized-artifacts.yaml` (plus the
  legacy `synthesized-tactics.yaml`), every id synthesis has created, per kind.

## Evidence Tracking Guidance

Evidence is inline in `research.md` (reproduction output and caller table).
