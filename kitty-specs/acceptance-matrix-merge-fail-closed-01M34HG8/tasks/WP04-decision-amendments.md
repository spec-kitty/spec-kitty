---
work_package_id: WP04
title: Amend recorded decisions + changelog
dependencies:
- WP01
requirement_refs:
- C-003
- C-004
- FR-006
planning_base_branch: fix/acceptance-matrix-merge-fail-closed
merge_target_branch: fix/acceptance-matrix-merge-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/acceptance-matrix-merge-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/acceptance-matrix-merge-fail-closed unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
history:
- '2026-09-22: authored by /spec-kitty.tasks'
agent_profile: curator-carla
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/adr/3.x/2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md
- docs/changelog/CHANGELOG.md
- kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/merge-driver-algorithm.md
- kitty-specs/gate-artifact-merge-driver-unit-gate-01KZPG7V/spec.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load your assigned profile via `/ad-hoc-profile-load` (profile: `curator-carla`) before
anything else — doctrine/decision-record maintenance discipline applies.

## Objective

Land the decision reversal in the same change (FR-006, C-003): the fail-closed behavior
reverses recorded decisions, so ADR, contract, and the 01KZPG7V FR-004 prose must be
amended, and a consumer-facing changelog entry added.

## Context

See `kitty-specs/acceptance-matrix-merge-fail-closed-01M34HG8/contracts/merge-driver-algorithm-amendment.md`
for the exact before/after. The rule: **gate/verdict artifacts fail closed** on an
unresolvable field conflict; **non-authoritative prose** (review-cycle `.md`) keeps
best-effort behavior.

### Subtask T010 — Amend ADR 2026-07-23-2

- In `docs/adr/3.x/2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md`,
  add a dated amendment note qualifying the "no consolidation abort" rule: it does **not**
  apply to gate/verdict artifacts (acceptance/issue matrix), which now fail closed
  (raise → `Exit(1)` → `git merge --abort`). Cite #4880. Do not rewrite history — append
  an amendment section.

### Subtask T011 — Amend the algorithm contract

- In `kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/merge-driver-algorithm.md`
  (~line 29), replace the "emit a structured conflict result (fail-closed, no consolidation
  abort)" wording for matrix field divergence with the fail-closed-raise contract from the
  amendment note. Keep the prose/review-cycle carve-out explicit.

### Subtask T012 — Amend 01KZPG7V FR-004 note

- In `kitty-specs/gate-artifact-merge-driver-unit-gate-01KZPG7V/spec.md`, add a dated
  supersession note on FR-004: its negative control (the `pass_fail`-conflict→`fail` flip
  treated as *correct*) is superseded by #4880 — matrix verdict-field conflicts now fail
  closed. Reference this mission. (Do not delete the historical FR; mark it superseded.)

### Subtask T013 — Consumer-facing changelog entry

- Add an entry to `docs/changelog/CHANGELOG.md` (the canonical changelog) in the current
  development section, consumer-focused BLUF: e.g. "Fixed: a merge that touches a mission's
  `acceptance-matrix.json` no longer silently flips an accepted verdict to `fail`; a genuine
  verdict conflict now stops the merge for a human to resolve (#4880)."

## Branch Strategy

Planning/base + merge target: `fix/acceptance-matrix-merge-fail-closed`. Depends on WP01
(describes the landed behavior). Enter the workspace `spec-kitty implement WP04` resolves.

## Definition of Done

- ADR amendment note added (dated, cites #4880); contract line 29 reflects fail-closed;
  01KZPG7V FR-004 marked superseded; changelog carries a consumer-focused entry.
- Terminology guard green: `PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.
- `markdownlint` clean on touched docs (run the repo's own invocation).

## Risks / reviewer guidance

- `planning_artifact` WP — every owned file is under `docs/` or `kitty-specs/`; do not edit
  any `src/`/`tests/` path here (that is WP01–03's job).
- Append/annotate; never rewrite a historical ADR or a completed mission's spec destructively.
