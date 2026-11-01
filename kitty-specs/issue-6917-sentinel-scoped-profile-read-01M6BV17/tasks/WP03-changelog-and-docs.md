---
work_package_id: WP03
title: Changelog and docs
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- NFR-002
planning_base_branch: issue-6917-sentinel-scoped-profile-read
merge_target_branch: issue-6917-sentinel-scoped-profile-read
branch_strategy: Planning artifacts for this mission were generated on issue-6917-sentinel-scoped-profile-read. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6917-sentinel-scoped-profile-read unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: Phase 3 - Changelog and docs
history:
- at: '2026-11-01T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: deepseek-v4.1-flash-1017
owned_files:
- docs/changelog/CHANGELOG.md
- docs/architecture/profile-load-reliability.md
- kitty-specs/issue-6917-sentinel-scoped-profile-read-01M6BV17/**
role: curator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Changelog and docs

## ⚡ Do This First: Load Agent Profile

Load `curator-carla` (curator) before starting.

## Objectives & Success Criteria

- One `[Unreleased]` changelog entry under `docs/changelog/CHANGELOG.md` that names both effects
  (bounded profile parses; lazy lineage graph), bold impact-first lead with `(#6917)`, before/after,
  under 1,200 characters.
- The profile-load architecture page records the scoped read and the new accessor as current
  behaviour (not as a plan).
- Mission tracers closed and the issue-matrix row for #6917 resolved.

## Context & Constraints

- Read first: `docs/changelog/CHANGELOG.md` (entry style and placement), and
  `docs/architecture/profile-load-reliability.md`.
- Do **not** regenerate the whole CLI reference: the shared machine cache is contended by other
  agents. Verify with `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0)
  instead of a full rebuild.
- Changelog is a maintenance surface: match the existing bullet shape, no marketing tone.

## Branch Strategy

- **Strategy**: feature-branch (single_branch mission)
- **Planning base branch**: `issue-6917-sentinel-scoped-profile-read`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### T010 – Changelog entry

- **Steps**: add the bullet at the top of `## [Unreleased]` (or the FIXES subsection that matches
  the existing layout). Lead with the user-visible effect: `agent tasks status` no longer parses the
  whole agent-profile catalogue or the lineage graph to draw the 👤 marker. Include the measured
  before/after (26 documents / ~2.1 s → at most the named ids / ≤ 0.5 s), the fact that the marker
  and its overlay/activation semantics are unchanged, and the `(#6917)` reference.
- **Files**: `docs/changelog/CHANGELOG.md`.

### T011 – Architecture page note

- **Steps**: in `docs/architecture/profile-load-reliability.md`, add a short subsection stating the
  two current facts: the marker path reads only the ids it names through
  `ActiveCharterService.agent_profile_sentinels(ids)`, and profile lineage is resolved lazily. Keep
  it factual and link the accessor contract under the mission directory.
- **Files**: `docs/architecture/profile-load-reliability.md`.

### T012 – Close the mission trail

- **Steps**: record the issue verdict for #6917 (`spec-kitty agent issue-verdict`), append the final
  tracer entries (`spec-kitty agent tracer-append --mission ... --category approach|design-decisions|tooling-friction`),
  and leave the acceptance matrix consistent with the delivered tests.
- **Files**: `kitty-specs/issue-6917-sentinel-scoped-profile-read-01M6BV17/**`.

## Test Strategy

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
uv run pytest tests/cross_cutting/packaging -q -k "changelog or docs" || true   # only if such a marker exists
```

## Risks & Mitigations

- **Full-doc regeneration churn** → regenerate nothing globally; check freshness only.
- **Stale architecture claim** → word the section as delivered behaviour and cite the merged code.

## Progress & Status

Claim with `spec-kitty agent action implement WP03 --agent pi:deepseek-v4.1-flash-1017:curator-carla`.
