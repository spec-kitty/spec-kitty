---
work_package_id: WP05
title: Document the system actor rule and record the change
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-013
- SC-005
planning_base_branch: issue-6722-system-status-actor
merge_target_branch: issue-6722-system-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6722-system-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6722-system-status-actor unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 3 - Documentation
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/architecture/
create_intent: []
execution_mode: planning_artifact
model: sonnet
owned_files:
- docs/architecture/status-model.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Document the system actor rule and record the change

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- `docs/architecture/status-model.md` § "The actor" no longer says system writers keep strings; it
  states the rule, the three role values and the null-profile guarantee, and names the system
  writers.
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry: bold impact-first lead with `(#6722)`,
  then before/after, under 1,200 characters.
- FR-013, SC-005.

## Context & Constraints

- Read: `spec.md` § Decision, `contracts/system-actor.md`, and the code as merged by WP02–WP04 — the
  docs must describe what the code does, not what the spec hoped.
- The existing page has a "**Still strings.**" paragraph (`docs/architecture/status-model.md:428`)
  and a "**Role.**" paragraph (`:417`). Replace/extend both; do not bolt a new section on.
- `docs/architecture/status-model.md` is **not** in the frozen set, but
  `docs/architecture/event-ledger-writers-and-readers.md` **is** (ADR `2026-10-29-1` D-9) — do not
  touch it. `services/` and `contracts/` are frozen too.
- The root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the file under
  `docs/`, never the symlink.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `issue-6722-system-status-actor`; completed
  changes merge back into it. Execution worktrees are allocated per computed lane from `lanes.json`.
- **Planning base branch**: `issue-6722-system-status-actor`
- **Merge target branch**: `issue-6722-system-status-actor`

## Subtasks & Detailed Guidance

### T001 – Replace the "Still strings" boundary

- **Steps**: in § "The actor", replace the "**Still strings.**" paragraph with "**System writes.**":
  which writers write the system actor, that `tool` carries the identity each one recorded before
  (`migration:<id>`, `merge`, `recovery`, `finalize-tasks`, the resolved operator identity for the
  attestations and the review-artifact override), and that `profile` and `model` are always `null`
  because a system write has no dispatch binding.
- **Files**: `docs/architecture/status-model.md`.

### T002 – Extend the role paragraph

- **Steps**: add `system` to the role description with what sets it ("the program wrote the event;
  never derived from a lane hop"), and note that `role_for_hop` still answers only
  `implementer`/`reviewer`.
- **Files**: `docs/architecture/status-model.md`.

### T003 – The changelog entry

- **Steps**: under `## [Unreleased]`, in the section matching the repository's existing convention
  for a behaviour change, add an entry: bold impact-first lead ending in `(#6722)`, then the before
  (string actor) and after (4-key system actor), under 1,200 characters. Say that existing logs are
  unaffected and that seeds are still recognised.
- **Files**: `docs/changelog/CHANGELOG.md`.

### T004 – Freshness and terminology

```bash
uv run python -m scripts.docs.check_docs_freshness --ci          # expect errors=0
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen pytest tests/architectural/test_events_import_frozen.py -q
```

- **Notes**: if `check_docs_freshness` demands a regenerated index for a page this diff changed, run
  only that page's regeneration; a full rebuild reads a shared, concurrently-rewritten cache on this
  host. Report any non-determinism in the PR's `## Deferred` rather than papering over it.

## Risks & Mitigations

- **Docs describing the spec rather than the code.** Write T001–T003 after WP02–WP04 land, reading
  the final call sites.
- **Touching a frozen doc path.** Only `docs/architecture/status-model.md` and
  `docs/changelog/CHANGELOG.md` are in scope.

## Review Guidance

- Does the section name all three role values and every system writer?
- Does the changelog entry lead with the impact and cite `(#6722)`, under 1,200 characters?
- Is `event-ledger-writers-and-readers.md` untouched?

## Progress & Status

- `spec-kitty agent tasks add-history WP05 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP05 --to <status>`
