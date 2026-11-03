---
work_package_id: WP02
title: Changelog fragment, docs and mission record
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-005
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Changelog, docs and record
history:
- at: '2026-11-03T08:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: deepseek-v4.1-flash-1017
owned_files:
- docs/changelog/unreleased/**
- docs/api/agent-subcommands.md
- kitty-specs/tracer-append-owned-checkout-01M6G9FW/**
role: curator
tags: []
task_type: implement
tracker_refs:
- '#7081'
---

# Work Package Prompt: WP02 – Changelog fragment, docs and mission record

## ⚡ Do This First: Load Agent Profile

Load `curator-carla` (curator) before starting.

## Objectives & Success Criteria

- One changelog **fragment** at `docs/changelog/unreleased/<pr>.fixed.md` with an impact-first bold
  lead naming the `(#7081)` reference, before/after, under 1,200 characters.
- `docs/api/agent-subcommands.md` documents `tracer-append --owned-checkout` as current behaviour.
- The `#7081` issue-matrix row is resolved and the Mission's tracer files are closed.

## Context & Constraints

- Read first: `docs/changelog/unreleased/README.md` (fragment name/section/shape),
  `docs/api/agent-subcommands.md` (the tracer-append entry).
- Since #6988 the changelog is assembled from fragments; `check_changelog_style` **rejects** the old
  `[Unreleased]`-entry shape in `docs/changelog/CHANGELOG.md`. Do not edit `CHANGELOG.md`.
- The shared machine cache for a full CLI reference rebuild is contended by other agents: regenerate
  only what the diff changes and verify with
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0).

## Branch Strategy

- **Strategy**: single_branch mission
- **Planning base branch**: `kitty/mission-tracer-append-owned-checkout-01M6G9FW`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### T007 – Changelog fragment

- **Steps**: create `docs/changelog/unreleased/<pr>.fixed.md` (use the issue number plus branch slug
  until the PR exists, then rename to the PR number). Content is a single bullet, no heading:

  `- **`spec-kitty agent tracer-append` writes into the checkout that owns the Mission** (#7081). **Before:** it resolved the repository root, so from an owned checkout it wrote `traces/` into the primary checkout on protected `main` and refused `PROTECTED_BRANCH_REFUSED`. **After:** it accepts `--owned-checkout` (and adopts the checkout it is invoked from), resolving the write root, branch and protection policy from the owned Mission fact, and refuses a typed owned error before writing anything on an invalid target.`

- **Files**: `docs/changelog/unreleased/<pr>.fixed.md` (new).
- **Verify**: `uv run --frozen python -m scripts.docs.check_changelog_style` and
  `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.

### T008 – API docs

- **Steps**: in `docs/api/agent-subcommands.md`, extend the `tracer-append` entry to document
  `--owned-checkout` (the shared help text) and the two behaviours: adoption from an owned checkout,
  and the typed refusal on an invalid target. Keep the page's existing table/section shape; if a
  help-output fixture is embedded, update it in place.
- **Files**: `docs/api/agent-subcommands.md`.

### T009 – Mission record

- **Steps**: append the wrap-up findings to the Mission's `traces/approach.md` and
  `traces/tooling-friction.md`, then resolve the issue-matrix row for `#7081` with
  `spec-kitty agent issue-verdict` once the fix is verified, pointing at the test module and the
  implementation commit.
- **Files**: `kitty-specs/tracer-append-owned-checkout-01M6G9FW/traces/**`, issue matrix.

## Test Strategy

```bash
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run python -m scripts.docs.check_docs_freshness --ci
```

## Risks & Mitigations

- **Editing `CHANGELOG.md` instead of a fragment** → checked by `check_changelog_style` in T007.
- **A full docs rebuild racing other agents** → verify with `check_docs_freshness --ci`, do not
  rebuild the whole reference.

## Review Guidance

- Confirm the fragment shape and that no shared changelog file was touched.
- Confirm the docs describe delivered behaviour, not a plan, and that the help text matches the
  shared `OWNED_CHECKOUT_HELP` string.

## Progress & Status

Start by running
`spec-kitty agent action implement WP02 --agent pi:deepseek-v4.1-flash-1017:curator-carla`
from the repository root, and record progress with
`spec-kitty agent tasks add-history WP02 --note "..."`.
