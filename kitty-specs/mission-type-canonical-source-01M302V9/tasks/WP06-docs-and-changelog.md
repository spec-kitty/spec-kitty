---
work_package_id: WP06
title: Docs / CHANGELOG / freshness
dependencies:
- WP05
requirement_refs:
- NFR-003
planning_base_branch: fix/mission-type-canonical-source-3831
merge_target_branch: fix/mission-type-canonical-source-3831
branch_strategy: Planning artifacts for this mission were generated on fix/mission-type-canonical-source-3831. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-type-canonical-source-3831 unless the human explicitly redirects the landing branch.
subtasks:
- T050
- T051
- T052
phase: Phase 6 - Docs
history:
- at: '2026-09-20T19:20:00Z'
  actor: system
  action: Prompt generated for mission-type-canonical-source
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/architecture/mission-type-resolution.md
execution_mode: code_change
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/architecture/mission-type-resolution.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Docs / CHANGELOG / freshness

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load`.

## Objectives & Success Criteria
User-facing changes documented; docs retrieval index + freshness + terminology gates green.

## Context & Constraints
- Canonical CHANGELOG is `docs/changelog/CHANGELOG.md` (repo-root `CHANGELOG.md` is a symlink).
- New ADR (WP02) + new doc page ⇒ regenerate the docs retrieval index.

## Subtasks & Detailed Guidance
### Subtask T050 – CHANGELOG
- `[Unreleased]` entries — bold impact-first lead with `(#3831)` and `(#4088)`, then before→after (org-tier custom mission types now resolve as themselves; project overrides honoured via migration).
### Subtask T051 – Docs + gates
- Author/refresh `docs/architecture/mission-type-resolution.md` (canonical source, `path_conventions` slot, migration). Run `.venv/bin/python scripts/docs/docs_index.py --write`, `.venv/bin/python scripts/docs/check_docs_freshness.py --ci` (errors=0), `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.
### Subtask T052 – Tracers
- Assess the three tracer files at close (append friction/decisions learned).

## Test Strategy
- Docs freshness (errors=0) + terminology guard green.

## Risks & Mitigations
- Freshness gate red on new ADR → regenerate the index in the same commit.

## Review Guidance
- Confirm CHANGELOG impact-first with issue refs; freshness/terminology green.

## Activity Log
- 2026-09-20T19:20:00Z – system – Prompt created.
