# Research Specification: Is the lane/worktree execution model the main source of friction, and what should replace or tighten it?

**Mission Branch**: `docs/lane-worktree-friction-research`
**Created**: 2026-11-06
**Status**: Draft
**Research Type**: Case Study (mixed: empirical classification of project records + architecture review)

## Research Question & Scope

**Primary Research Question**: Over the last three months, how much of the friction recorded in
Spec Kitty's own dogfooding is caused by the lane and worktree execution model, through which
mechanisms, and which direction for that model removes the most friction at an acceptable cost?

**Sub-Questions**:

1. What share of friction tracers, issues and fix effort traces back to lanes and worktrees, and
   with what severity (data loss, wrong verdict, forced override, wasted time)?
2. Within that share, which part is caused by persistent per-lane **checkouts** (worktrees) and
   which by lanes as **branches**, coordination topology or other causes?
3. Which mechanisms of the model produce the top causes?
4. What do the options (tighten; ephemeral checkouts; default `single_branch`; drop lane
   worktrees; others) cost and break, and how do they interact with the Java write service that
   takes over status writes?

**Scope**:

- **In Scope**: mission tracer files, retrospectives, review cycles, `kitty-ops/` records,
  engineering field reports; GitHub issues and merged PRs; git history; the architecture docs,
  ADRs and code of lanes, worktrees, coordination, consolidation and status surfaces; the
  doctrine in `spec-kitty-open-packs` (`packs/built-in`, `packs/internal`).
- **Out of Scope**: any product code, test, ADR or doctrine change; starting an implementation
  mission; hosted surfaces.
- **Boundaries**: window 2026-08-06 to 2026-11-06; repositories `spec-kitty/spec-kitty` and
  `spec-kitty/spec-kitty-open-packs`.

**Operator inputs**:

- Observation (2026-11-06): "the worktree system has been causing us issues and is the cause for
  most of the friction tracers in the last months". Treated as a hypothesis to verify.
- Ruling (2026-11-06): the resolved status surface is the only source of truth; a lane
  worktree's own status files never count (#6466, #6884). Treated as a fixed constraint.

**Expected Outcomes**:

- A cause taxonomy with counts, severity and model attribution.
- A mechanism analysis for the top causes.
- An options analysis and a ranked recommendation with a phased path, a first slice and the
  operator decisions needed.
- The report lands in `docs/plans/engineering-notes/` through a draft docs-only PR.

## Research Methodology Outline

### Research Approach

- **Method**: Case study with a squad of read-only analysts, one per source cluster (tracers,
  issues, named examples, PRs and git churn, architecture and options, doctrine), followed by a
  synthesis and a pre-PR adversarial squad (evidence-quality lens, architecture lens).
- **Data Sources**: listed under In Scope; every source is logged in
  `research/source-register.csv`.
- **Analysis Approach**: each record gets one primary cause code, a model attribution and a
  severity, using the shared code book in `research.md`. Counts are reproducible from the
  commands recorded in `research.md`.

### Success Criteria

- Every in-window tracer entry and every issue in the labelled population is classified.
- The operator's observation is confirmed, qualified or refuted with numbers.
- At least four options are compared on the same criteria.
- Every claim in the report cites a tracer, issue, PR, code location or ADR.

## Research Requirements

### Data Collection Requirements

- **DR-001**: Research MUST collect data from the sources listed under In Scope.
- **DR-002**: All sources MUST be documented in `research/source-register.csv`.
- **DR-003**: Citations use repository paths (`path:line`) and issue/PR numbers.

### Analysis Requirements

- **AR-001**: Findings MUST be synthesized into the engineering note and `research.md`.
- **AR-002**: Methodology MUST be documented and reproducible (commands recorded).
- **AR-003**: Limitations MUST be explicitly identified.

### Quality Requirements

- **QR-001**: All claims MUST be supported by cited evidence.
- **QR-002**: Confidence levels MUST be assigned to findings in `research/evidence-log.csv`.
- **QR-003**: Alternative interpretations MUST be considered (e.g. friction caused by the gates
  rather than by checkouts; reporting bias in catfooding issues).

## Key Concepts & Terminology

- **Lane**: a unit of parallel execution in a Mission, recorded in `lanes.json`; it has a lane
  branch and, today, a lane worktree.
- **Lane worktree**: the persistent git worktree `.worktrees/<slug>-lane-<id>` checked out on a
  lane branch.
- **Resolved status surface**: the checkout whose `status.events.jsonl` is authoritative (the
  coordination branch for coordination topologies, the PRIMARY partition otherwise).
- **Topology**: `single_branch`, `lanes`, `coord`, `lanes_with_coord` (see
  `docs/context/topology.md`).

## Evidence Tracking Guidance

- Log every reviewed source in `research/source-register.csv`.
- Capture each key finding in `research/evidence-log.csv`, with a confidence level.
- Reference evidence row IDs from `research.md` and from the engineering note.
