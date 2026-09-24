---
work_package_id: WP05
title: 'Docs & tracker close-out: CHANGELOG + ADR index + #4959/#4966'
dependencies:
- WP01
- WP02
- WP03
- WP04
requirement_refs:
- C-006
- FR-006
planning_base_branch: fix/coord-read-fail-closed
merge_target_branch: fix/coord-read-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/coord-read-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/coord-read-fail-closed unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
history:
- event: created
  at: '2026-09-24T05:45:24Z'
  actor: architect-alphonso
agent_profile: scribe-sally
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/changelog/CHANGELOG.md
- docs/adr/3.x/index.md
- docs/development/3-2-page-inventory.yaml
- docs/development/3-2-docs-retrieval-index.yaml
role: implementer
tags: []
tracker_refs:
- '#4959'
- '#4966'
---

## ⚡ Do This First: Load Agent Profile
`/ad-hoc-profile-load scribe-sally` before anything else.

---

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objective
Close the mission's user-facing record. Depends on WP01–WP04 so the CHANGELOG reflects landed behavior and the ADR (authored by WP01) is present to register.

## Subtasks

### T015 — CHANGELOG entry
Add one entry to canonical `docs/changelog/CHANGELOG.md` (root is a symlink) under `[Unreleased] → Fixed`. Bold, operator-symptom-first, `(mission; #4959, #4966)` ref, before→after. Lead example: *"`spec-kitty agent tracer-append` and the decision ledger no longer silently destroy or hide a teammate's mission files when the coordination worktree isn't materialised (a fresh clone or CI checkout) (mission; #4959, #4966)."* Then: tracer now fails closed instead of overwriting `traces/*`; the decision ledger + `accept` now read the same authoritative copy so a mission can't get permanently stuck. Budget for the whole file's markdownlint set.

### T016 — Register ADR + regenerate inventories
Add a `2026-09-24` row for `2026-09-24-2-coord-read-fail-closed.md` to `docs/adr/3.x/index.md` (MD060 spaced pipes, chronological). Regenerate `docs/development/3-2-page-inventory.yaml` (`PYTHONPATH=. python -m scripts.docs.freshen_adr_inventory`) and `docs/development/3-2-docs-retrieval-index.yaml` (`PYTHONPATH=. python -m scripts.docs.docs_index --write`). Verify the exact script names in-tree first.

### T017 — Close-out + gates
Draft the #4959/#4966 close-out text for the PR body (`Closes #4959`, `Closes #4966`; epic #5002 stays open for #4979). Run the terminology guard (`tests/architectural/test_no_legacy_terminology.py`) and `scripts/docs/check_docs_freshness.py --ci` (errors=0; external-URL link warnings OK).

## Branch Strategy
Base + target `fix/coord-read-fail-closed`; planning-lane workspace (primary checkout).

## Definition of Done
- Consumer-focused CHANGELOG entry (FR-006), style-matched, file markdownlint-clean.
- ADR registered in index + both inventories (no DOCS-INDEX-DRIFT / LEAK-MISSING-INVENTORY).
- #4959/#4966 close-out text ready (epic #5002 stays open); terminology green; docs-freshness errors=0. Mission terminology only (C-006).

## Reviewer guidance
Confirm the CHANGELOG lead is operator-legible (symptom-first), both issue refs present, and the ADR appears in all three surfaces. Confirm freshness/terminology pass.
