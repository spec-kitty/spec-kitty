---
work_package_id: WP02
title: 'Annotate ADR #4360-A with both verified premise-falsifications'
dependencies: []
requirement_refs:
- FR-007
- NFR-002
planning_base_branch: fix/ci-aggregate-source-eligibility
merge_target_branch: fix/ci-aggregate-source-eligibility
branch_strategy: Planning artifacts for this mission were generated on fix/ci-aggregate-source-eligibility. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ci-aggregate-source-eligibility unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-aggregate-source-eligibility-01M2MFDD
base_commit: 67e97e2768b5e648e4261ae3521c6e17b9c1f242
created_at: '2026-09-16T07:20:41.653713+00:00'
subtasks:
- T007
- T008
- T009
history:
- at: '2026-09-16T07:11:32Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: curator-carla
authoritative_surface: docs/adr/3.x/
create_intent: []
execution_mode: code_change
owned_files:
- docs/adr/3.x/2026-09-15-1-ci-main-verdict-topology.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile:
`/ad-hoc-profile-load curator-carla` (or `spec-kitty agent profile show curator-carla` + `spec-kitty charter context --action implement --mission ci-aggregate-source-eligibility-01M2MFDD --json`). Apply the resolved initialization, boundaries, directives, and tactics, then state which you applied.

## Objective

Annotate `docs/adr/3.x/2026-09-15-1-ci-main-verdict-topology.md` so its #4360-A / Axis-3a record carries the two verified, live-grounded corrections (DIRECTIVE_003 decision documentation, DIRECTIVE_010 spec fidelity). Do **not** rewrite the ratified Decision Outcome — annotate the *mechanism narration* as superseded and point to this mission's research.

Read first: `../research.md` (D-01, D-02 — the verified evidence + exact anchors), `../spec.md` Context section. The evidence is already gathered and orchestrator-verified; this WP is editorial fidelity, not new investigation.

## Subtasks

### T007 — Add the "Superseded post-Stage-1 — corrected mechanism (2026-09-16)" annotation
In the ADR's Axis-3 / #4360-A areas (the mechanism list item #3 in "Context and Problem Statement", and Axis 3 "3a"), add a clearly-marked annotation block recording BOTH corrections, with evidence:
1. **Mechanism superseded:** there are NO `report-main` legs in `ci-modules.yml` (0 grep hits); main CI Modules runs conclude `success` (verified via `gh run list`); the `--branch main` fallback query *succeeds* (does not return `[]`). The refusal is from `reconcile` on SELECTED-but-undelivered shards, triggered by a red/partial PR-head run adjudicated as a `main`-labelled aggregate.
2. **The failure is cosmetic:** no main-verdict consumer reads the mislabelled run — `fleet_main.py:50` queries `event=push&branch=main` (a `workflow_run` aggregate is invisible); `fleet_verdict.py:395-405` resolves the aggregate back to its source run and tests THAT run's provenance (PR-head → PR path, never `main=true`); branch protection requires only `"Clean install verification"`. It is the PR's own correct red, merely displayed under a `main` label.
Note that Axis-3a is therefore delivered as **tested provenance hardening + doctrine correction**, not a release-authority correctness fix, and reference `kitty-specs/ci-aggregate-source-eligibility-01M2MFDD/research.md`. Keep the ratified lever table and Decision Outcome intact.

### T008 — Preserve doctrine integrity & links
Ensure the annotation is internally consistent (dates, issue refs #4360/#4360-B, cross-links to `2026-07-17-1`), does not contradict the ratified bundle, and uses canonical terminology (Mission; the "main verdict" sense). Verify the ADR still renders (headings/anchors intact).

### T009 — Gates
Run: `PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/architectural/test_no_legacy_terminology.py -q`; check docs freshness for an EDIT to an existing ADR (this is not a NEW page, so the triple-registration for new pages does not apply — but confirm no docs-index/build gate flags the edit: `git grep -l "2026-09-15-1-ci-main-verdict-topology"` to see if any index references its description/title that must stay in sync). Confirm `ruff format --check .` is unaffected (markdown only). Retired-surface scan: 0 hits on added lines.

## Branch Strategy

Planning/base branch: `fix/ci-aggregate-source-eligibility`. Final merge target: `fix/ci-aggregate-source-eligibility` (→ local `main`, then PR to `upstream/main`; operator merges). Independent write-scope (`docs/adr/3.x/`) → its own lane; parallelizable with WP01. Enter the resolved workspace via `spec-kitty implement WP02`.

## Definition of Done

- The ADR #4360-A record carries a dated, evidence-cited annotation of BOTH corrections (mechanism superseded; failure cosmetic), pointing to the mission research (SC-004).
- The ratified Decision Outcome / lever table is unchanged; only the mechanism narration is annotated.
- Terminology guard green; retired-surface scan 0 hits; no docs gate regressed.

## Risks / reviewer guidance

- Do NOT overreach into rewriting the ratified decision — this is an annotation, not a re-ratification.
- Reviewer: verify every factual claim in the annotation is one the mission actually verified (research D-01/D-02 anchors), not a paraphrase that drifts.
- NFR-002 (post-merge provenance spot check) is verified during landing, not in this WP; this WP records the doctrine correction that motivates it.
