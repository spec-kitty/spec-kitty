---
work_package_id: WP01
title: Full run keeps legacy edges it did not regenerate
dependencies: []
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-010
- NFR-002
- NFR-003
- C-005
- SC-004
planning_base_branch: issue-6453-synthesis-record-integrity
merge_target_branch: issue-6453-synthesis-record-integrity
branch_strategy: Planning artifacts for this mission were generated on issue-6453-synthesis-record-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6453-synthesis-record-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-synthesis-record-integrity-01M5ZBC9
base_commit: 0c696c13d0252e382cc859d4c8a8d7bc5b9aa978
created_at: '2026-10-27T19:26:10.538053+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Remediation
history:
- at: '2026-10-27T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/reconcile.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/synthesizer/reconcile.py
- tests/charter/synthesizer/test_synthesize_reconcile.py
- tests/charter/synthesizer/test_styleguide_reach_only.py
- tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py
- tests/specify_cli/cli/commands/charter/test_synthesis_report_6404.py
- tests/charter/synthesizer/test_orchestrator_resynthesize.py
- tests/charter/synthesizer/test_project_intent_directive.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Full run keeps legacy edges it did not regenerate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission synthesis-record-integrity-01M5ZBC9`).
- Address all feedback before your work is complete; record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Issue #6456 (triage: P2, delivery unchanged). A full `charter synthesize` run strips the legacy `<tactic|styleguide> --applies--> directive:*` edge from **every** synthesized reach-only artifact, also those it did not regenerate, and reports "legacy applies edge replaced by suggests" although no successor was written. Operator decision (DM `01M5ZBDAH1Z51X0W35XMMYPHTY`): **skip** stripping artifacts the run did not regenerate; do NOT write a successor edge (C-005).

Done when:
- FR-007: a full (preserve-mode) run keeps the legacy `applies` edge of a synthesized tactic AND styleguide it did not regenerate.
- FR-008: such an edge is not in `stripped_legacy_edges` / the delta's stripped refs (no "replaced by suggests" line for it).
- FR-009: a regenerated artifact's legacy edge is still stripped and reported (positive control, same fixture).
- FR-010: the dead `directive:PROJECT_* --requires--> mission_type:*` edge (#6443) is still stripped on a full run even when that `PROJECT_*` directive is NOT regenerated.
- NFR-002: `reach_only_ids` is the same for a fixture with the kept edge as with it stripped.

## Context & Constraints

- Spec: `kitty-specs/synthesis-record-integrity-01M5ZBC9/spec.md` (US3, FR-007..FR-010). Plan: `plan.md` IC-01 and "Design notes". Research: `research.md` §1.
- Charter: `.kittify/charter/charter.md`; red-first (DIRECTIVE_034/041), tidy-first (Standing Order #2), complexity ≤ 15, no new `noqa`/`type: ignore`.
- Code (`src/charter/activation/synthesizer/reconcile.py`, origin/main `581b5c46`):
  - `_is_dead_mission_type_edge(edge, regenerated_urns=None)` `:294-307`
  - `_is_legacy_applies(edge, synthesized_urns, regenerated_urns=None)` `:310-331` — passes the SAME `regenerated_urns` to the dead-edge check (`:323`). This coupling is the trap.
  - `legacy_applies_edges` `:344-350`
  - `merge_project_overlay(..., topic_scoped=False)` `:353-412`, strip at `:393` (`updated_urns if topic_scoped else None`)
  - `_graph_delta` `:593-627` — `legacy_applies_edges(existing_overlay, synthesized_urns)` `:610` and `_is_legacy_applies(e, synthesized_urns)` `:620` (no regenerated filter)
  - full-run caller `:785-791`; topic-scoped caller `resynthesize_pipeline.py:389-396` (reports via `legacy_applies_edges(..., regenerated)`).
- The run report: `stripped_legacy_edges` (see `tests/charter/synthesizer/test_synthesis_report_6404.py:46`).

## Branch Strategy

- **Strategy**: populated by finalize-tasks.
- **Planning base branch**: issue-6453-synthesis-record-integrity
- **Merge target branch**: issue-6453-synthesis-record-integrity

Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace `spec-kitty agent action implement WP01 --agent claude --mission synthesis-record-integrity-01M5ZBC9` gives you.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first tests

- **Purpose**: prove the defect on today's code before changing it.
- **Steps**: in `tests/charter/synthesizer/test_synthesize_reconcile.py` add:
  1. `merge_project_overlay` full run (no `topic_scoped`) over an existing overlay with `tactic:regen` (in updated) and `tactic:untargeted` + `styleguide:style` (not in updated), each with a legacy `applies` edge, all in `synthesized_urns`: assert the untargeted tactic's and styleguide's edges survive, `tactic:regen`'s is gone (FR-007, FR-009).
  2. `legacy_applies_edges` as the full run reports it lists only `tactic:regen` (FR-008). Prefer asserting through the delta: drive `_graph_delta` (or the public `reconcile_synthesis` path used by other tests in the file) and check the stripped refs.
  3. FR-010: an existing overlay holding `directive:PROJECT_001 --requires--> mission_type:software-dev` where the updated overlay does NOT contain `directive:PROJECT_001`: a full run still drops it and reports it with `DEAD_MISSION_TYPE_EDGE_REASON`. (This one is green today — it is the guard for T002/T003.)
- Commit the red tests first (`test(#6456): ... red-first`). Confirm 1 and 2 fail and 3 passes.

### Subtask T002 – Tidy-first split (behaviour-preserving)

- **Purpose**: decouple the dead-edge filter from the applies filter.
- **Steps**: give `_is_legacy_applies` AND `legacy_applies_edges` (`:344-350`, which also forwards one set to both branches) a split filter: keep the positional `regenerated_urns` meaning "both branches" (the topic-scoped meaning, so `resynthesize_pipeline.py:389` — not owned by this WP — stays untouched), and add a keyword-only `dead_edge_regenerated_urns` (default: same as `regenerated_urns`) that a full run sets to `None`. At every call site pass today's values. No behaviour change: the full suite of `tests/charter/synthesizer/` is unchanged. Separate commit (`refactor(#6456): ...`).

### Subtask T003 – The fix

- **Steps**: applies branch always filters by the regenerated set: `merge_project_overlay` uses `updated_urns` for the applies branch on every run, and `updated_urns if topic_scoped else None` for the dead-edge branch; `_graph_delta` calls `legacy_applies_edges(existing_overlay, synthesized_urns, fresh_node_urns, dead_edge_regenerated_urns=None)` at `:610` and the same split at `:620`. Keep `legacy_applies_edges(existing, synthesized, regenerated_urns=None)` callable (one caller passes the regenerated set). Update docstrings (`merge_project_overlay`, `_is_legacy_applies`, `legacy_applies_edges`, `LEGACY_APPLIES_REASON` comment) to state that only regenerated artifacts are stripped. T001 tests go green.

### Subtask T004 – Re-pin and re-check existing tests

- **Re-pin (they assert the reversed behaviour; say so in the docstring with `#6456`)**:
  - `test_synthesize_reconcile.py::test_legacy_applies_strip_is_limited_to_regenerated_reach_only_sources` (`full.edges`, `legacy_applies_edges(existing, synthesized)` assertions ~`:927-931`).
  - `test_styleguide_reach_only.py::test_legacy_styleguide_applies_edge_is_stripped_and_reported` (~`:471-488`, `full.edges == []`) — reverses an earlier mission's styleguide "scenario 5".
- **Re-check, change only if red**: `tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py` (out-of-matrix: run it locally; prune/dry-run tests injecting a legacy edge on a non-regenerated tactic ~`:168-185`, `:279`, `:330`), `tests/specify_cli/cli/commands/charter/test_synthesis_report_6404.py` (`stripped_legacy_edges` ~`:46`), `test_orchestrator_resynthesize.py::...strips_legacy_applies`, `test_project_intent_directive.py`. Where a test injects a legacy edge on a tactic the run DOES regenerate, it must stay unchanged.

### Subtask T005 – Pin the new reporting

- Kept edge whose target directive is absent from every layer → reported as a non-blocking `preserved_dangling_endpoint` conflict (`_classify_conflicts`, ~`:704`).
- `--prune` (`apply_prune`, ~`:826-850`): a kept edge on a non-regenerated node is excised with that node as ordinary prune content, not reported as "replaced".
- NFR-002: `reach_only_ids` (in `reach_only.py`, read-only use) returns the same set for an overlay with the kept legacy edge as without it (a legacy `applies` edge never makes an artifact reach-only). Put this test in `test_styleguide_reach_only.py` or `test_synthesize_reconcile.py` (owned files only).

## Test Strategy

```bash
uv run --frozen pytest tests/charter/synthesizer/ tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py tests/specify_cli/cli/commands/charter/test_synthesis_report_6404.py -q
uv run --frozen ruff check src/charter/activation/synthesizer/reconcile.py tests/charter/synthesizer/
uv run --frozen ruff format --check --force-exclude src/charter/activation/synthesizer/reconcile.py <changed tests>
uv run --frozen mypy src/charter/activation/synthesizer/reconcile.py
```

## Risks & Mitigations

- #6443 regression → FR-010 test lands before the change.
- Complexity of `merge_project_overlay` ≤ 15 → compute both filter sets before the loop.

## Review Guidance

- Red-first commit precedes the fix; the split commit is behaviour-preserving.
- No successor `suggests` edge is ever written for a non-regenerated artifact (C-005).
- Re-pinned tests name `#6456` and explain the reversal.
- ruff, format and mypy are clean on touched files.

## Progress & Status

Progress lives in the status event log. Use `spec-kitty agent tasks add-history WP01 --note "..."`, `spec-kitty agent tasks mark-status T00x --status done`, and `spec-kitty agent tasks status`.
