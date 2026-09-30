---
title: Investigations
description: Scope and compatibility investigations — issue analyses, schema-generation research, and mission review reports, split into live and historical.
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/index.md
---
# Investigations

Standalone investigation and scope-assessment artifacts: issue analyses,
compatibility matrices, schema research, and mission review reports.

These notes follow the distil-then-retire lifecycle described in the
[plans index](../index.md): a page stays **Live** while its question is open and
moves to **Historical** once its subject ships or is decided. The active cycle is
4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

## Live

Open questions and unshipped scope still worth consulting:

- [Consumer-repo layout portability: disposition and sequencing](2026-08-consumer-repo-layout-portability.md) —
  how to make the software-dev mission work in repos that are not laid out as `src/` + `tests/`.
  The bounded fix shipped (#3016); the broader work (#2330) is on *CLI 4.x stable*.
- [Retrospective-learning surface: disposition and sequencing](2026-08-retrospective-surface-disposition.md) —
  what to do about retrospective classifier false positives and tracer-entry parsing (#2267, #3072).
- [ADRs as a first-class primitive: scope assessment](issue-1040-scope-assessment.md) —
  whether to fold ADR support into a mission (#1040, open on the *Product backlog*).
- [WP & Op Schema Model](wp-op-schema-model.md) — parked idea: formalize work-package files and the
  Op record through code-owned models; most of the model already exists, so the remaining win is narrow.
  - [WP & Op Schema — related tracker tickets](wp-op-schema-related-tickets.md)
  - [WP prompt & Ops debrief — model/schema proposal](wp-op-schema-proposal.md)

## Historical (shipped, decided or superseded)

Kept as records only; do not consult them for current behavior.

- [Events and tracker fork census (#797)](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/issue-797-events-tracker-fork-census.md) —
  **decided**; the CLI now pins `spec-kitty-events>=10.4.0,<11`.
- [External observability endpoints: squad assessment (RFC #2497)](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/2497-external-observability-endpoints-assessment.md) —
  **superseded**; the RFC closed and the event-journal and sync modules it assumed were removed.
- [Write-path topology: ambient-location root cause](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/write-path-topology-root-cause.md) —
  **delivered in 3.2.6**; foreign-checkout writes are now refused (#3128, #3129).
- [Review-artifact integrity: the open gap is a missing writer (#3044)](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/review-artifact-write-integrity-3044.md) —
  **writer shipped** (PR #3211); the wider #3044 epic continues on *CLI 4.x stable*.
- [WP & Op schema research reports](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/wp-op-schema-research/README.md) — verbatim squad reports behind the
  schema-model idea: [code as-is](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/wp-op-schema-research/code-as-is.md),
  [feasibility](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/wp-op-schema-research/feasibility.md), [roadmap and ADR fit](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/wp-op-schema-research/roadmap-adr.md).
- [Declared-but-inert doctrine/DRG seams](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/2026-08-declared-but-inert-doctrine-seams.md) —
  **retired**; 3.2.x research brief on doctrine artifacts that are declared but never consumed (#3608, #3530, #3629).
- [Pack-level metadata manifest](2026-08-pack-level-metadata-manifest.md) —
  **retired**; ratified in ADR `2026-08-16-1` and shipped by mission `pack-metadata-manifest-unification-01M052PT`.
- [Mission-type step-model unification](mission-type-step-model-unification.md) —
  **retired**; shipped via ADR `2026-07-16-2` (#2658) + mission `templates-as-config-01KXMS1G`.
- [Mission Review Report: windows-compatibility-hardening-01KP5R6K](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/2026-04-14-windows-compatibility-hardening-mission-review.md) —
  **retired**; mission squash-merged as `89bab26e5`.
- [Mission-Next Compatibility Matrix](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/mission-next-compatibility.md) —
  **retired**; superseded by `shared-package-boundary-cutover-01KQ22DS` (ADR `2026-04-25-1`).
- [Model-First Schema Generation](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/model-first-schema-generation.md) —
  **retired**; shipped as the `scripts/generate_schemas.py` pipeline.
- [Scoping brief — #2684 task-move / runtime-state cluster](2684-task-move-cluster-scoping.md) —
  **retired**; shipped via ADR `2026-07-19-1` + mission `wp-runtime-state-eviction-01KXWN13`.
- [Mission spec — evict runtime-mutable WP state (#2684)](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/2684-task-move-cluster-spec.md) —
  **retired**; shipped via ADR `2026-07-19-1` + mission `wp-runtime-state-eviction-01KXWN13`.
- [WP Runtime-State Eviction — Prerequisite Mission Scope](wp-runtime-state-eviction-scope.md) —
  **retired**; shipped via ADR `2026-07-19-1` + mission `wp-runtime-state-eviction-01KXWN13`.
- [Issue #1111 Analysis — Branch Alignment Report](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/issue-1111-analysis.md) —
  **retired**; Epic #1111 closed COMPLETED (2026-06-02).
- [Fast-Follow Spec: Implement-Loop Friction Quick-Wins](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/investigations/loop-friction-fastfollow-spec.md) —
  **retired**; #2581 closed COMPLETED, shipped via mission `loop-reliability-ci-red-burndown-01KXWWD6`.

## See also

- [Plans index](../index.md)
