---
work_package_id: WP07
title: Fold ADR 2026-10-11-2, update docs/glossary/CHANGELOG, finalize descriptor diagram, close
dependencies: []
requirement_refs:
- FR-021
- FR-022
- FR-023
- C-006
- C-007
planning_base_branch: issue-6048-pack-level-pack-yaml
merge_target_branch: issue-6048-pack-level-pack-yaml
branch_strategy: Planning artifacts for this mission were generated on issue-6048-pack-level-pack-yaml. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6048-pack-level-pack-yaml unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-level-declared-in-pack-yaml-01M4NVEN
base_commit: 30c6e20b885fd058889686a231366e896fa6141f
created_at: '2026-10-11T16:47:49.413719+00:00'
subtasks:
- T035
- T036
- T037
- T038
- T039
phase: Phase 3 - Docs & ADR (fold last)
history:
- at: '2026-10-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md
- docs/adr/4.x/index.md
- docs/development/docs-retrieval-index.yaml
- docs/development/page-inventory.yaml
- docs/context/charter.md
- docs/context/governance.md
- CHANGELOG.md
- src/charter/README.md
- src/charter/diagrams/pack-descriptor-model.puml
- src/charter/diagrams/pack-descriptor-model.svg
- src/charter/diagrams/pack-descriptor-example.puml
- src/charter/diagrams/pack-descriptor-example.svg
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `scribe-sally` via `/spk-charter-profile-load`. Read `plan.md` (IC-09 + the "New contradictions to retire explicitly" list), `research.md` (R-2), and the mission's `tracers/design-decisions.md`. Fold LAST so the ADR reflects the final shipped design. Diagram source + README embed are already drafted and committed on the base — finalize, do not recreate.

## Objective

Fold the governing ADR into this PR, retire the NFR-003 carve-out language in prose, update the pack-tier docs + glossary + CHANGELOG, finalize the descriptor-model diagram/README, and close #6049.

## Subtasks

### T035 — Fold ADR `2026-10-11-2` (FR-021)
Add `docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md` (base content is in PR #6049; obtain it with `gh pr diff 6049 --repo spec-kitty/spec-kitty`). **Align Decision §2** from "a single enum in `charter.offering.packs` owns the three values" to: *"`kernel.pack_tiers` is the single authority for the three level names; the descriptor reuses its `PackTier` Literal — no second enum is introduced. Every layer literal, including the former no-hyphen `builtin` provenance spelling, derives from it (this mission performs that fold)."* Add the index + inventory entries (`docs/adr/4.x/index.md`, `docs/development/docs-retrieval-index.yaml`, `docs/development/page-inventory.yaml`) exactly as #6049 does — regenerate via `inventory_lockfile --write` and `docs_index --write` rather than hand-editing if those helpers exist.

### T036 — ADR consequences: retire NFR-003 + cross-version note
In the ADR consequences, explicitly state (a) this mission retires the NFR-003 provenance-spelling freeze (two vocabularies → one, strengthening single-authority), and (b) the cross-version persisted-value note: the serialized provenance spelling changes to `built-in`; verified safe for the current CLI (no read-back compares to `"builtin"`; regenerated JSON + the dogfood manifest self-heal); the only theoretical edge is an older CLI reading a new-spelling artifact post-upgrade.

### T037 — docs/context + glossary (FR-022)
Update `docs/context/charter.md` and `docs/context/governance.md` pack-tier prose: packs now declare `pack_level` in `pack.yaml`; one spelling `built-in` for tier token AND provenance; name the `PACK_LEVEL_MISMATCH`/`MISSING` behaviour and the org deprecation window. US spelling; one Divio type per doc; keep an `updated:` date.

### T038 — CHANGELOG (FR-022)
Add a `CHANGELOG.md` entry (and the matching `docs/changelog/` fragment if the repo uses one) describing the schema bump + provenance unification + vendoring tooling. US spelling (the changelog spelling gate is separate — verify).

### T039 — Finalize diagram/README (FR-023) + close #6049
Confirm `src/charter/README.md` embeds the rendered `pack-descriptor-model.svg` with alt text + `updated:` and that the ADR relative link now resolves (the ADR exists after T035). Tweak the diagram only if the final schema differs from the draft. After the PR is opened, close #6049 with a comment pointing to this PR/ADR (the operator may prefer to close it at merge — coordinate; do not close prematurely if the ADR is not yet merged).

## Definition of Done
- ADR present, internally consistent with reuse-Literal/kernel-authority, index+inventory entries valid.
- NFR-003 retirement + cross-version note in the ADR; docs/context + glossary + CHANGELOG updated; US spelling clean.
- README embeds the rendered diagram with alt text; ADR link resolves.
- docs-freshness / page-inventory / docs-retrieval-index gates green.

## Tests to run (targeted)
`.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q` ; plus the docs-lint / freshness / inventory-lockfile checks the repo provides (e.g. `make docs-lint`, `check_docs_freshness`). Do NOT run a full architectural sweep.

## Reviewer guidance
Verify the ADR Decision §2 matches shipped reality (no "new enum"); verify the NFR-003 retirement is explicit and consistent with WP06's docstring changes; verify no dangling doc links; verify #6049 is closed only in coordination with the operator's merge.

## Branch Strategy
Planning/merge base `issue-6048-pack-level-pack-yaml`; worktree per `lanes.json`.
Implement with: `spec-kitty agent action implement WP07 --agent <name> --mission pack-level-declared-in-pack-yaml-01M4NVEN`
