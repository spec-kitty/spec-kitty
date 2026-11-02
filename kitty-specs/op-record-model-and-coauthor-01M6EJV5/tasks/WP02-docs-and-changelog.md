---
work_package_id: WP02
title: Documentation, changelog and the generated CLI reference
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-006
- C-001
- NFR-001
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 2 - Documentation
history:
- at: '2026-11-02T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/architecture/trail-model.md
- docs/api/configuration.md
- docs/api/profile-invocation.md
- docs/api/cli-commands.md
- docs/changelog/unreleased/
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Documentation, changelog and the generated CLI reference

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in
the frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## Objectives & Success Criteria

An operator can find, without reading code:

1. that a committed Op record no longer names a model, and that records written
   before the change are immutable history (no migration);
2. how to configure `commit.co_author`, and that
   `profile-invocation complete --co-author` overrides it for one close;
3. a CLI reference that matches the live Typer surface.

## Context & Constraints

- Behaviour comes from WP01; document what landed, not what was planned.
- `docs/api/cli-commands.md` is **generated** by
  `uv run python -m scripts.docs.build_cli_reference`. Do not hand-edit it.
- Since #6988 the changelog is assembled from per-PR fragments: write
  `docs/changelog/unreleased/<pr>.fixed.md` and never touch
  `docs/changelog/CHANGELOG.md`. Read `docs/changelog/unreleased/README.md` for
  the required shape (the style gate rejects the old `[Unreleased]` entry shape).
- Use US spelling; the spelling gate is binding.

## Branch Strategy

- **Strategy**: single-branch mission; all work lands on the mission branch and
  merges to `main`.
- **Planning base branch**: main
- **Merge target branch**: main

## Subtasks & Detailed Guidance

### Subtask T009 – Trail-model reference

- **Purpose**: The canonical description of what an Op record contains must stop
  listing `model_id` and must state the history ruling.
- **Steps**: In `docs/architecture/trail-model.md`, update the paragraph that
  lists "`mission_id`, `wp_id`, and the catalog-winning `model_id`" to describe
  the record's current fields (`actor` is the harness key) and to say that
  records written before #7013 still carry `model_id` and are byte-frozen
  immutable history. Add a short paragraph on the auto-commit trailer.
- **Files**: `docs/architecture/trail-model.md`

### Subtask T010 – Configuration and command reference

- **Purpose**: An operator needs one place to learn the key and the flag.
- **Steps**: Add a `commit.co_author` section to `docs/api/configuration.md`
  (location, shape `Name <email>`, precedence versus `--co-author`, what happens
  when it is malformed, and that it is optional). Document `--co-author` in
  `docs/api/profile-invocation.md` next to the other `complete` options.
- **Files**: `docs/api/configuration.md`, `docs/api/profile-invocation.md`

### Subtask T011 – Regenerate the reference; add the changelog fragment

- **Purpose**: Keep the generated surface true and give the operator an
  impact-first note.
- **Steps**: Run
  `uv run python -m scripts.docs.build_cli_reference` and confirm the only diff is
  the `profile-invocation complete` option table. Write
  `docs/changelog/unreleased/<pr>.fixed.md` in the shape the README requires: a
  bold impact-first lead with the issue reference, before/after, under 1,200
  characters, naming the immutable-history ruling and the resolved-binding
  consequence.
- **Files**: `docs/api/cli-commands.md`, `docs/changelog/unreleased/`

### Subtask T012 – Prove freshness and terminology

- **Steps**: Run
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`)
  and `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`. If the
  freshness gate reports a path outside this mission's diff, stop and report
  rather than "fixing" unrelated docs.
- **Files**: none (verification only)

## Definition of Done

- The three hand-written doc surfaces describe the shipped behaviour.
- `docs/api/cli-commands.md` is regenerated, not hand-edited, and the freshness
  gate reports zero errors.
- One changelog fragment exists for the PR, in the fragment shape.
