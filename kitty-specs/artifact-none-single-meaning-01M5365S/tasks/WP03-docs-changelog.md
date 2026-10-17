---
work_package_id: WP03
title: Docs & CHANGELOG
dependencies:
- WP01
- WP02
requirement_refs:
- SC-001
- SC-002
- SC-003
planning_base_branch: fix/artifact-none-single-meaning
merge_target_branch: fix/artifact-none-single-meaning
branch_strategy: Planning artifacts for this mission were generated on fix/artifact-none-single-meaning. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/artifact-none-single-meaning unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
phase: Phase 2 - Documentation
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: doctrine-daphne
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/architecture/artifact-placement-seam.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Docs & CHANGELOG

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (`doctrine-daphne`) before parsing the rest of this prompt, and behave according to its guidance.

- **Profile**: `doctrine-daphne`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Record the user-facing change and the one-meaning rule in the canonical docs.
Done when the CHANGELOG has an impact-first `[Unreleased]` entry referencing #5697,
the artifact-placement doc states the single meaning of an unclassified kind and
the new PRIMARY kinds, and the docs-freshness + terminology gates pass.

Requirements: SC-001, SC-002, SC-003 (documented outcomes). Depends on WP01 + WP02.

## Context & Constraints

- CHANGELOG canonical path: `docs/changelog/CHANGELOG.md` (repo-root `CHANGELOG.md` is a symlink — edit the canonical path only).
- This is a `planning_artifact` WP: every owned file is under `docs/`. Do NOT edit any `src/` or `tests/` path here.
- Only this WP touches CHANGELOG, so no concurrent-conflict risk.
- `docs/architecture/artifact-placement-seam.md` is the placement-seam reference; if it describes `None`/unclassified semantics, update it. If a different page (e.g. `docs/architecture/status-model.md`) is the real home for this and the seam doc does not mention `None`, record that in a history note and update the correct page instead — but keep ownership to `docs/architecture/artifact-placement-seam.md` for this WP (adjust the owned_files only via a corrected finalize if truly needed).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `finalize-tasks`. Planning artifacts land on the primary partition.

## Subtasks & Detailed Guidance

### Subtask T013 – `[Unreleased]` CHANGELOG entry

- **Purpose**: tell consumers the refuse is fixed.
- **Steps**: add a `[Unreleased]` entry to `docs/changelog/CHANGELOG.md`, impact-first, with the `(#5697)` ref and a before→after. Draft:
  > **Squash consolidation no longer refuses byte-identical mission files that the artifact classifier left unclassified (#5697).** An unclassified artifact kind (`kind_for_mission_file → None`) now means one thing to every consumer — "not a coordination record", routed through `is_coordination_kind_file` — so the squash projection no longer carries a `None` path as coordination bookkeeping and no longer refuses on content it should accept. Before: a byte-identical `research/**` evidence file (and any other unclassified mission file) could trip a deterministic squash refuse (the #5552 class). After: it is primary-bound on write and never projected. Also classifies the previously-unclassified mission files (`research/**`, research deliverables, `gap-analysis.md`, `audit-report.md`, `occurrence_map.yaml`, `goals.md`, `release.md`, `meta.json`) with honest PRIMARY kinds.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Validation**: entry matches the changelog style; `(#5697)` present.

### Subtask T014 – Update the artifact-placement doc

- **Purpose**: make the one-meaning rule discoverable.
- **Steps**: in `docs/architecture/artifact-placement-seam.md`, add a short "Unclassified kinds (`None`)" note: an unrecognised `kitty-specs/<slug>/` path classifies to `None`, which every consumer reads as "not a coordination record" via `is_coordination_kind_file` — it is primary-bound on write and never projected by the squash projection. Add one sentence that the same rule also routes a NON-mission path (a repo-root `meta.json`/config file some callers stage) to `primary_bound` on the workflow commit partition — this is deliberate unification with the #2533 write-side, not a regression. List the four new PRIMARY kinds and the four deliberately-excluded `kitty-specs/`-adjacent paths (`lint-report.json`, `docs/**`, `answers.yaml`, `mission-events.jsonl`).
- **Files**: `docs/architecture/artifact-placement-seam.md`.
- **Validation**: content renders; terminology canon respected (Mission, not Feature).

### Subtask T015 – Docs freshness + terminology gates

- **Purpose**: keep the docs gates green.
- **Steps**: if an ADR or new doc *page* was added (not expected here — only edits), run `.venv/bin/python scripts/docs/docs_index.py --write`. Always run `.venv/bin/python scripts/docs/check_docs_freshness.py --ci` (expect 0 errors) and `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`. Fix any `codespell`/UK-spelling finding the changelog touch surfaces (`.venv/bin/python -m scripts.docs.check_spelling` if the docs-lint flags it).
- **Files**: (gate run only; regenerate the retrieval index only if a page was added.)
- **Validation**: freshness errors = 0; terminology test green.

## Definition of Done

- CHANGELOG `[Unreleased]` entry present (#5697, impact-first, before→after).
- Artifact-placement doc states the one-meaning rule + new kinds + excluded paths.
- `check_docs_freshness.py --ci` = 0 errors; `test_no_legacy_terminology.py` green.

## Risks & Reviewer Guidance

- **Reviewer**: confirm the CHANGELOG lead is impact-first and consumer-facing, not an internal narrative; confirm no `Feature` terminology; confirm the retrieval index was regenerated only if a page was actually added.
- **Risk**: a stray UK spelling on the changelog touch trips the us-spelling docs-lint (known gotcha). Run the spell check locally before marking done.
