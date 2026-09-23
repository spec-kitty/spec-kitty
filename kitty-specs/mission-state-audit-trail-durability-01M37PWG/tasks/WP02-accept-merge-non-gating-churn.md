---
work_package_id: WP02
title: Accept/merge non-gating via self-bookkeeping-churn
dependencies:
- WP01
requirement_refs:
- C-006
- FR-008
- NFR-005
planning_base_branch: fix/mission-state-audit-trail-durability
merge_target_branch: fix/mission-state-audit-trail-durability
branch_strategy: Planning artifacts for this mission were generated on fix/mission-state-audit-trail-durability. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-state-audit-trail-durability unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
phase: Phase 2 - Reconciliation
history:
- timestamp: '2026-09-23T18:10:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/coordination/
create_intent: []
execution_mode: code_change
mission_id: 01M37PWGWRFNZY8X2Y7P7KJJGK
owned_files:
- src/specify_cli/coordination/coherence.py
- tests/mission_runtime/test_self_bookkeeping_allowlist.py
role: implementer
tags: []
tracker_refs: []
wp_code: WP02
---

## ⚡ Do This First: Load Agent Profile

Load `/ad-hoc-profile-load implementer-ivan` and apply its initialization/boundaries/directives before anything else. State which you applied.

# Work Package Prompt: WP02 — Accept/merge non-gating via self-bookkeeping-churn

## Objective

Register the tracked audit root `.kittify/mission-state-audit/` as **self-bookkeeping churn** so a `--fix` run's tracked-but-uncommitted output never gates `spec-kitty accept`, `merge`, or `agent mission record-analysis`. This preserves the #2384 property (a repair must not block accept) now that the artifacts are tracked instead of ignored — the reason Option A was safe.

## Context & Constraints

- `is_self_bookkeeping_churn` is defined once in `src/specify_cli/coordination/coherence.py:50` and consumed by `merge/git_probes.py`, `review/dirty_classifier.py`, `acceptance/__init__.py`, `cli/commands/agent/mission_record_analysis.py`, `implement.py`, `implement_cores.py`. Covering the audit root in the single definition propagates to all consumers — change only `coherence.py`.
- Today it recognizes `meta.json`, `.kittify/encoding-provenance/global.jsonl`, dossier snapshots, and `kitty-ops/<ULID>.jsonl` (`:102-110`). Add `.kittify/mission-state-audit/**` (manifest JSON + quarantine JSONL under it).
- Depends on WP01 (the root must exist / be tracked). Do NOT edit the audit-write code (WP01) or the summary (WP03).

## Subtasks

### T007 — Cover the audit root in the churn allowlist
In `coherence.py:is_self_bookkeeping_churn`, add a normalized-path check that returns `True` for any path under `.kittify/mission-state-audit/` (both the manifest `*.json` at the root and the `quarantine/<run_id>/<slug>/status.events.jsonl` subtree). Mirror the existing matcher style (regex or `endswith`/`startswith` normalized on `/`). Keep it tight — match the audit root specifically, not all of `.kittify/`.

### T008 — Red-first test: repair output is churn, accept not gated
In `tests/mission_runtime/test_self_bookkeeping_allowlist.py`: assert `is_self_bookkeeping_churn(".kittify/mission-state-audit/<run_id>.json")` and `is_self_bookkeeping_churn(".kittify/mission-state-audit/quarantine/<run_id>/<slug>/status.events.jsonl")` are both `True`, and a control path outside the root is `False`. Write it failing first, then implement T007.

## Definition of Done
- The audit root (manifest + quarantine subtree) is classified self-bookkeeping churn; a control path is not.
- `ruff`/`mypy` clean.
- (Integration proof that accept/merge are actually ungated end-to-end lives in WP04's e2e; this WP proves the unit-level classification.)

## Reviewer guidance
Confirm the matcher is scoped to `.kittify/mission-state-audit/` and does not accidentally whitelist unrelated `.kittify/` paths. Confirm only `coherence.py` changed (consumers inherit).
