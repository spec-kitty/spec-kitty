---
work_package_id: WP02
title: Audience readers on profile lists
dependencies:
- WP01
requirement_refs:
- FR-003
- NFR-004
planning_base_branch: issue-6929-docsite-frontmatter-migration
merge_target_branch: issue-6929-docsite-frontmatter-migration
branch_strategy: Planning artifacts for this mission were generated on issue-6929-docsite-frontmatter-migration. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6929-docsite-frontmatter-migration unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
phase: Phase 2 - Reader ports
history:
- at: '2026-11-01T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/docs/
create_intent: []
execution_mode: code_change
owned_files:
- scripts/docs/audience_resolver.py
- scripts/docs/touched_set_gates.py
- tests/docs/test_audience_resolves.py
- tests/docs/test_touched_set_gates.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Audience readers on profile lists

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- `audience_resolver.py` and `touched_set_gates.py` read `audience: [{profile, guidance_text}]` only (FR-003, C-001).
- A profile resolves through `_dockitty_contract.persona_page` (`docs/context/audience/<profile>.md` or `<profile>/index.md`). A profile that names a catalog slug (first segment `internal` or `external`) and does not resolve is **dangling**; any other profile is free text (counted, never dangling) — the same semantics as today's `.md`-vs-free-text split.
- An entry missing `profile` or `guidance_text`, or a non-list `audience`, is reported (it is what the doc-kitty schema rejects): add `malformed` to the report shape as a separate list so the `{from, to}` dangling contract stays as is.

## Context & Constraints

- Grounding §2 lists both readers. No test reads `audience` over the real tree, so these ports are green before WP03 migrates the corpus.
- Keep the CLI flags, JSON keys (`checked_count`, `dangling_references`) and the non-vacuity floor (`assert_examined_floor`). `--changed-from` mode unchanged.
- `touched_set_gates`: presence (a touched page declares at least one resolvable profile), placement orientation (`internal`/`external` from the profile's first segment), the page-relative path variant disappears.

## Branch Strategy

- **Strategy**: `single_branch` on `issue-6929-docsite-frontmatter-migration`; planning base and merge target are that branch.
- Implement with `spec-kitty agent action implement WP02 --agent claude --mission docsite-frontmatter-migration-01M6BRJK`.

## Subtasks

### T008 — Port `audience_resolver.py`
- First commit: rewrite `tests/docs/test_audience_resolves.py` fixtures to the profile-list shape (dangling profile, clean profile, free-text profile, zero-examined floor, malformed entry, diff-scoped four cases) — red against the old reader.
- Then port `_read_audience` → returns `list[AudienceEntry]`; `_resolves` → `persona_page(...) is not None`; update the module docstring (the canonical form is now doc-kitty's profile list; cite ADR `2026-10-31-1` D-7).

### T009 — Port `touched_set_gates.py`
- `_audience_values` → profiles; `check_audience_presence` resolves via the contract; `_audience_orientation` reads the profile's first segment. Update messages ("declares no audience profile", "profile '<p>' is not a persona under docs/context/audience/").
- Rewrite the fixtures in `tests/docs/test_touched_set_gates.py` first (red), then port.

### T010 — Fixtures and docs strings
- Grep the two test files for `docs/context/audience/` path strings and convert them. No other file changes.

## Definition of Done

- `pytest tests/docs/test_audience_resolves.py tests/docs/test_touched_set_gates.py` green; red-first commits visible.
- ruff/format/mypy clean on both scripts; complexity ≤ 15.

## Reviewer guidance

- Confirm free text is still never dangling, and a catalog-shaped missing profile is.
- Confirm no legacy string branch remains (single shape).
