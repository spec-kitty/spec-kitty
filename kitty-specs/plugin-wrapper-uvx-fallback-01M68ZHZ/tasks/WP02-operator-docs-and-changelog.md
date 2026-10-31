---
work_package_id: WP02
title: Operator docs and changelog
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
phase: Phase 2 - Document the shipped behaviour
history:
- at: '2026-10-31T12:45:00Z'
  actor: planner-priti
  action: Prompt generated via spec-kitty tasks
agent_profile: curator-carla
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet
owned_files:
- docs/guides/how-to/installation/install-claude-code-plugin.md
- docs/changelog/CHANGELOG.md
role: curator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Operator docs and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of this
prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- Address all feedback before declaring the work complete.

---

## Objectives & Success Criteria

The install guide and the changelog currently describe — and recommend — the broken
behaviour (`uvx spec-kitty-cli==<version>` and `pip install spec-kitty-cli`). Bring both
in line with what WP01 ships (FR-006, FR-007, SC-004).

## Context & Constraints

- Shipped behaviour (after WP01): PATH CLI used only when its `--version` is inside the
  bundle's `<major>.<minor>` series → `uvx --from "spec-kitty-cli==<version>"` → `uvx
  --from "spec-kitty-cli>=<version>,<<next-minor>"` → error naming `uv tool install` /
  `pipx install`.
- `docs/changelog/CHANGELOG.md` is the canonical changelog; the root `CHANGELOG.md` is a
  symlink to it. Add under `[Unreleased]`.
- Keep the page's Divio how-to shape and its existing headings, so the docs index stays
  stable (`docs/guides/how-to/installation/install-claude-code-plugin.md`).
- Do not edit `docs/api/cli-commands.md`: no CLI option, argument or command changes.

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: main
- **Merge target branch**: main

## Subtasks & Detailed Guidance

### Subtask T005 – Install how-to

- **Purpose**: An operator debugging a wrapper failure must be able to read the actual
  resolution order.
- **Steps**: Rewrite "How the runtime wrapper works" to the ordered resolution above;
  update the troubleshooting entry so the remedy is `uv tool install spec-kitty-cli` or
  `pipx install spec-kitty-cli` (and mentions `uvx` as the on-demand path); note that a
  `spec-kitty` outside the bundle's series is ignored in favour of the pinned version,
  and that an unpublished pin falls back to the newest release of the same series.
- **Files**: `docs/guides/how-to/installation/install-claude-code-plugin.md`
- **Parallel?**: Yes — independent of T006.
- **Notes**: No `pip install spec-kitty-cli` may remain on the page (SC-004).

### Subtask T006 – Changelog entry

- **Purpose**: The fix is visible in the release notes.
- **Steps**: Add one bullet under `[Unreleased]` in `docs/changelog/CHANGELOG.md`: bold
  impact-first lead with `(#6476)`, then before/after (the wrapper's uvx fallback could
  not run any CLI because it asked uvx for a non-existent executable; now it uses
  `uvx --from`, prefers the pinned series over an incompatible PATH CLI, and retries
  inside the series for an unpublished pin). Keep it under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: Yes.
- **Notes**: Match the surrounding entry style; no new release heading.

## Test Strategy

- `uv run python -m scripts.docs.check_docs_freshness --ci` — expect errors=0 for the
  touched surface.
- `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` if the page is
  indexed by the terminology guard.
- Grep proof: `grep -rn "pip install spec-kitty-cli" docs/guides/how-to/installation/install-claude-code-plugin.md`
  returns nothing.

## Risks & Mitigations

- Docs index churn → keep headings; regenerate only if the freshness check demands it.
- Changelog conflict with other in-flight PRs → one self-contained bullet under
  `[Unreleased]`, no re-ordering of existing entries.

## Review Guidance

- Verify the documented order matches the rendered templates behaviourally.
- Verify the changelog entry is under `[Unreleased]`, carries `(#6476)`, and stays under
  1,200 characters.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
