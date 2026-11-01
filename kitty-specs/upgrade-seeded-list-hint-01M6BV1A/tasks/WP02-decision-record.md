---
work_package_id: WP02
title: The decision record — ADR amendment and changelog
dependencies:
- WP01
requirement_refs:
- FR-007
planning_base_branch: issue-6684-upgrade-seeded-list-hint
merge_target_branch: issue-6684-upgrade-seeded-list-hint
branch_strategy: Planning artifacts for this mission were generated on issue-6684-upgrade-seeded-list-hint. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6684-upgrade-seeded-list-hint unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
phase: Phase 2 - The decision record
history: []
agent_profile: planner-priti
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/changelog/CHANGELOG.md
execution_mode: planning_artifact
owned_files:
- docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: documentation
tracker_refs: []
---

# WP02 — The decision record

## Objective

Record the operator ruling that closed #6684 so it is not discoverable only in a diff: no reset
migration, upgrade stays warn-only, and the hint now also recognises a list a released preset wrote.

## Subtasks

- **T006** ADR `docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md`: add
  `## Amendment 2026-11-01 (#6684): the seeded-list hint covers a released-preset seed` after the
  #6685 amendment. It states:
  - the decision: option (b), **no reset migration**; the upgrade keeps reporting and never narrows;
  - why the alternative was refused: set-equality cannot tell a seeded list from a deliberate
    activate-all (#6499), no provenance is recorded, and the ledger's L1 validation refuses a provenance
    key that could not be backfilled anyway;
  - what changed instead: the hint's provenance test now also matches the released `default` preset lists
    frozen in `_charter_pack_cutover_snapshots.DEFAULT_SNAPSHOTS`, so a list seeded before the catalogue
    grew is reported;
  - the residual: a whole-catalogue seed from a release whose catalogue later grows is still only caught
    while the catalogue is unchanged (not reachable with any released CLI today, because the 4.0.0rc6/rc7
    catalogues equal today's), and the follow-up shape if it becomes reachable.
- **T007** `docs/changelog/CHANGELOG.md` under `[Unreleased]`: one entry in the existing style — bold
  impact-first lead with `(#6684)`, before/after, "what to do", under 1,200 characters.

## Definition of done

- The amendment names the ruling, the alternative, the mechanism and the residual, and links #6629/#6499/
  #6685 as the surrounding decisions.
- The changelog entry is user-facing (what an operator sees on the next `spec-kitty upgrade`), not a code
  summary.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 (an ADR amendment needs no
  index regeneration; the ADR inventory only tracks new files — verify rather than assume).
- `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` stays green.

## Notes

- Do not restate the code; state the decision and the reason.
- Keep the amendment short (under ~30 lines) — the surrounding amendments are terse.
