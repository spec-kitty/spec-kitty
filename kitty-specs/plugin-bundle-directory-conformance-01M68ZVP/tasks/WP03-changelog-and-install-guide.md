---
work_package_id: WP03
title: Changelog and the Claude install guide
dependencies:
- WP01
- WP02
requirement_refs:
- SC-001
planning_base_branch: issue-6479-plugin-bundle-directory-conformance
merge_target_branch: issue-6479-plugin-bundle-directory-conformance
branch_strategy: Planning artifacts for this mission were generated on issue-6479-plugin-bundle-directory-conformance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6479-plugin-bundle-directory-conformance unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: Phase 3 - Documentation
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/guides/how-to/installation/install-claude-code-plugin.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6479'
---

# Work Package Prompt: WP03 – Changelog and the Claude install guide

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting.

---

## Objectives & Success Criteria

Record the user-facing change and stop the install guide describing a runtime
wrapper the bundle no longer ships.

Done when:

- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry: bold impact-first
  lead with `(#6479)`, then before/after, under 1,200 characters, in the style of
  the surrounding entries. (The root `CHANGELOG.md` is a symlink to that file —
  edit the file, never replace the symlink.)
- `docs/guides/how-to/installation/install-claude-code-plugin.md` no longer
  documents `bin/spec-kitty-wrapper*`, the uvx fallback or the "How the runtime
  wrapper works" section; it states that the skills call `spec-kitty` and that the
  bundle installs without a top-level `bin/`.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`
  and `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` passes.

## Context & Constraints

- Shipped behaviour is defined by WP01/WP02 and `spec.md` FR-001…FR-008.
- Do not rebuild the whole CLI reference (other agents share the installed CLI's
  global asset cache); regenerate only the surface this diff changes.
- Keep the doc's marketplace caveat honest: the marketplace source path is still a
  deferred product decision (#6479 `## Deferred`), so do not claim the marketplace
  install works from a committed path.

## Subtasks

- **T010** — Changelog entry.
- **T011** — Install-guide rewrite (agent, no wrapper, `spec-kitty` on PATH).
- **T012** — Docs freshness check plus the terminology test.

## Definition of Done

- Both checks green; no wrapper mention left in the guide.
- Tracer updated.
