---
work_package_id: WP03
title: End-to-end repro, changelog and docs
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-004
- FR-005
- FR-006
- SC-001
- SC-002
planning_base_branch: issue-6771-consolidate-dependency-ref-attribution
merge_target_branch: issue-6771-consolidate-dependency-ref-attribution
branch_strategy: Planning artifacts for this mission were generated on issue-6771-consolidate-dependency-ref-attribution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6771-consolidate-dependency-ref-attribution unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-dependency-ref-attribution-01M67J2A
base_commit: c959e265d503e3fc5607c5d792a7271c4d680786
created_at: '2026-10-31T00:34:13.228853+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 3 - Proof and record
history: []
agent_profile: python-pedro
authoritative_surface: tests/consolidation/test_dependency_ref_attribution_6771.py
create_intent:
- tests/consolidation/test_dependency_ref_attribution_6771.py
execution_mode: code_change
model: ''
owned_files:
- tests/consolidation/test_dependency_ref_attribution_6771.py
- docs/changelog/CHANGELOG.md
- docs/guides/how-to/missions/merge-mission.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6771'
---

# Work Package Prompt: WP03 – End-to-end repro, changelog and docs

## Goal

The issue's own reproduction becomes a regression test through the real CLI, under both
strategies, and the docs name the supported way to restack a mission onto a newer dependency
head.

## Red first (T011, T012)

`tests/consolidation/test_dependency_ref_attribution_6771.py`, driving `run_terminus`
(`python -m specify_cli consolidate …`) against `build_coord_mission`:

- Build a two-WP coord mission; cut an external branch from the repository's root commit with
  two or three `src/dep/*` content commits; merge it `--no-ff` into WP02's lane through a
  temporary worktree; `restamp_approvals_at_lane_tips` (review approved that tree).
- `consolidate --strategy merge --dry-run` → **exit 1**, output names an un-attributable
  commit; the target does not move.
- `consolidate --strategy merge` (no flag) → **exit 1**, the target is rolled back (unchanged) —
  the existing fail-closed behavior is preserved.
- `consolidate --strategy merge --dependency-ref dep-branch --dry-run` → **exit 0**.
- `consolidate --strategy merge --dependency-ref dep-branch --yes` → **exit 0**, and both the
  lane's own content and `src/dep/mod0.py` are present on the target.
- A squash variant: the same mission with `--strategy squash --dependency-ref dep-branch`
  consolidates and the dependency content is on the target.

Assert on exit codes, the target's content, and the refusal text — never on incidental
formatting. Keep the module to the three or four CLI runs the fixture needs.

## Docs and record (T013–T015)

- `docs/changelog/CHANGELOG.md`, under `[Unreleased]`: an impact-first bold lead with
  `(#6771)`, before/after, under 1,200 characters.
- `docs/guides/how-to/missions/merge-mission.md`: a short section — restacking onto a newer
  dependency head (merge it into the lane, re-review, declare `--dependency-ref`), and that an
  undeclared merge is still refused.
- Issue-matrix verdicts: `#6771` fixed by this mission; `#4945`, `#4977`, `#4981`, `#5013`
  stay as they are (their repros are the controls that prove nothing was loosened).
- If the changelog or docs surface requires regeneration, run
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`) rather than a
  full reference rebuild.
