---
work_package_id: WP04
title: Documentation, ADR amendment, changelog
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-007
planning_base_branch: ccr-11788f1f-qu75jg
merge_target_branch: ccr-11788f1f-qu75jg
branch_strategy: Planning artifacts for this mission were generated on ccr-11788f1f-qu75jg. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-11788f1f-qu75jg unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
phase: Phase 2 - Polish
history:
- at: '2026-10-06T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
agent: claude
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: sonnet
owned_files:
- docs/development/how-to/create-a-pack-skill.md
- docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md
- docs/changelog/CHANGELOG.md
- docs/development/docs-retrieval-index.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Documentation, ADR amendment, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log. Address every feedback item before completing.

---

## Objectives & Success Criteria

- FR-007: the pack-skill how-to, the pack-skills ADR and the changelog describe the `missing` kind, the `no_tool_folder` finding, `--fix` projection, and the #4275 upgrade fixes, as shipped by WP01–WP03.
- Docs gates pass: docs index, freshness (errors=0), terminology guard.

## Context & Constraints

- Read the merged diffs of WP01–WP03 first; docs mirror shipped behaviour (code is the source of truth).
- Audience: pack authors and project operators (software-engineer persona). Plain language; Divio type of each page unchanged; bump `updated:` dates.
- Terminology: Mission, never feature; canonical `status commit`.

## Branch Strategy

- **Planning base branch**: `ccr-11788f1f-qu75jg` · **Merge target branch**: `ccr-11788f1f-qu75jg`.

## Subtasks & Detailed Guidance

### Subtask T015 – How-to

- In `docs/development/how-to/create-a-pack-skill.md`, where the four finding kinds (drift, stale, orphaned, unresolvable) are listed, add `missing` (in force but not installed for a configured tool that accepts skills, or installed copy deleted) and state that `doctor skills --fix` installs it. Add a short note on `no_tool_folder`.

### Subtask T016 – ADR amendment

- Append a dated "Amendment 2026-10-06" section to `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md` (around the doctor findings list, ~line 249): new `missing` kind and `--fix` projection; rationale #5801; verifier/assessment blind spot deferred.

### Subtask T017 – CHANGELOG

- Under `[Unreleased]` in `docs/changelog/CHANGELOG.md`, add two bold impact-first entries (before → after):
  - **`spec-kitty upgrade` no longer fails when a configured tool folder such as `.claude/` is missing, and a failed upgrade no longer records the new version (#4275).**
  - **`spec-kitty doctor skills` now reports pack skills that are in force but not installed, and `--fix` installs them; it also fails when no configured tool folder exists (#5801).**

### Subtask T018 – Docs gates

```bash
.venv/bin/python scripts/docs/docs_index.py --write
.venv/bin/python scripts/docs/check_docs_freshness.py --ci
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Review Guidance

- Docs match the merged code; changelog format matches neighbours; gates green.

## Activity Log

- 2026-10-06T08:10:00Z – system – Prompt created.
