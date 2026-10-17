---
work_package_id: WP03
title: 'Deliverable hygiene: changelog + CLI reference'
dependencies:
- WP02
requirement_refs:
- SC-001
- SC-002
planning_base_branch: kitty-base-6320
merge_target_branch: kitty-base-6320
branch_strategy: Planning artifacts for this mission were generated on kitty-base-6320. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty-base-6320 unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
phase: Phase 3 - Hygiene
history:
- at: '2026-10-17T19:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet-4-6
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/agent-subcommands.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Deliverable hygiene: changelog + CLI reference

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Record the user-facing change and document the new CLI option, mirroring how #6023 did it.
Depends on WP02 (the option must exist).

- **SC-001 / SC-002**: the delivered behavior is documented; the changelog states the before→after impact.

## Context & Constraints

- `docs/changelog/CHANGELOG.md` is the canonical changelog (root `CHANGELOG.md` is a symlink — edit the canonical one). Add one **Fixed** entry under `[Unreleased]`, matching the existing style exactly: a **bold lead sentence stating the user-facing impact with `(#6320)`**, then before→after plain language. Keep it under 1,200 characters (`tests/docs/test_changelog_style.py`). Mirror the merged #6023 entry's shape.
- `docs/api/agent-subcommands.md` documents `agent mission issue-verdict`. Add the `--owned-checkout` option to its entry, mirroring how `acceptance-verdict`'s `--owned-checkout` is documented there (grep for it). If the doc's frontmatter `description` changes, re-run the docs retrieval index (`scripts/docs/docs_index.py --write`) so the index stays in sync (DOCS-INDEX-DRIFT gate); the SEO description gate is 50–180 chars.

## Subtasks

T014 Add the `[Unreleased] → Fixed` changelog entry for #6320 (impact-first, before→after, `(#6320)`, <1,200 chars) (WP03)
T015 Document `issue-verdict --owned-checkout` in `docs/api/agent-subcommands.md` mirroring `acceptance-verdict`; regenerate the docs retrieval index if a description changed (WP03)

## Test strategy

No new tests. Run `tests/docs/test_changelog_style.py`, `tests/architectural/test_no_legacy_terminology.py`, and `scripts/docs/check_docs_freshness.py --ci` (errors=0) before hand-off.

## Definition of Done

- Changelog entry present and style-clean; CLI option documented; retrieval index fresh if touched.
- `mark-status` the subtasks done.

## Risks & reviewer guidance

- Changelog >1,200 chars reds the style gate; the description SEO gate is 50–180 chars.
- Reviewer: confirm the entry leads with user impact, not internal jargon, and names the symptom.
