---
work_package_id: WP02
title: Verdict contract (not-applicable) + approval-blocker + ADR
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-006
- FR-010
- FR-013
- FR-014
- NFR-001
- NFR-005
planning_base_branch: fix/move-task-approval-ergonomics
merge_target_branch: fix/move-task-approval-ergonomics
branch_strategy: Planning artifacts for this mission were generated on fix/move-task-approval-ergonomics. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/move-task-approval-ergonomics unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-move-task-approval-ergonomics-01M302R0
base_commit: 7c8fee57647800effe6bad12045532c2e46a3b7e
created_at: '2026-09-20T20:20:19.363467+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Implementation
history:
- at: '2026-09-20T19:15:00Z'
  actor: system
  action: Prompt generated for move-task-approval-ergonomics mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- docs/adr/3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md
- tests/specify_cli/cli/commands/test_issue_matrix_not_applicable.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/review/_issue_matrix.py
- src/specify_cli/cli/commands/agent/issue_verdict.py
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- docs/adr/3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md
- tests/specify_cli/cli/commands/test_issue_matrix_not_applicable.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3469'
---

# Work Package Prompt: WP02 – Verdict contract + approval-blocker + ADR

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill before reading
anything else. Then read `spec.md`, `plan.md`, `data-model.md`,
`contracts/classification-and-verdict-contract.md`, and WP01's landed classifier.

## Objective

Add the truthful, additive, terminal, non-gating `not-applicable` verdict to the governance
vocabulary and wire the approval blocker to the WP01 classifier. Pin the lever SSOT: **classification
decides whether a row is REQUIRED; verdict decides whether an existing row is RESOLVED.** Record the
contract change in an ADR that supersedes the never-implemented WP09 `not_applicable` intent.

## Context (grounding — verify anchors; they may have drifted)

- `src/specify_cli/cli/commands/review/_issue_matrix.py` — `IssueMatrixVerdict(StrEnum)` (~L50–68).
  Verified additive-safe: values are parsed via `IssueMatrixVerdict(value)`, so appending
  `NOT_APPLICABLE = "not-applicable"` leaves the four legacy values validating unchanged (NFR-001).
  The evidence-token rule (a `deferred-with-followup` evidence string must contain `#\d+` or
  `Follow-up:`) lives here (~L348–360).
- `src/specify_cli/cli/commands/agent/issue_verdict.py` — `--verdict` help enumerates the four values
  (~L297) and `--evidence-ref` help (~L300) does NOT mention the evidence-token rule. `--actor` is the
  existing actor flag here (the vocabulary WP04 reconciles move-task toward).
- `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` (anchors VERIFIED) — the approval
  blocker `_issue_matrix_approval_blocker` (L198–302), `_issue_matrix_evaluation` (referenced set built
  L137, `referenced_issues - matrix_issues` subtract at **L144**; matrix rows via
  `_issue_matrix_row_issues` L148–154). The `in-mission` gating flip is at **L271–272**
  (`if target_lane != Lane.DONE: unresolved_in_mission = []`), helper `_issue_matrix_in_mission_rows`
  L157–166 — **NOT L296–300, which is only the message-render block (WP-prompt drift, corrected).**
  `not-applicable` must be **terminal**: route it so it is non-gating at BOTH `approved` and `done` —
  do NOT run it through the `unresolved_in_mission` path at all.
- **Do NOT re-fix #4330**: the JSON-first error prefix (`_issue_matrix_error_prefix` ~L90–112) and the
  batched missing-row message (~L277–295) already landed. Leave them alone (C-002).

## Subtasks

### T006 — Red-first regression test (RED first)
`tests/specify_cli/cli/commands/test_issue_matrix_not_applicable.py`, `@pytest.mark.regression`,
pinned `#3469`. Assert (RED on current main): `issue-verdict --verdict not-applicable` is accepted;
a row with `not-applicable` does NOT block the `approved` transition; it also passes the `done`/merge
completeness gate (terminal); and the four legacy verdicts still validate.

### T007 — Add `NOT_APPLICABLE` to the enum (additive)
Append `NOT_APPLICABLE = "not-applicable"` to `IssueMatrixVerdict`. Do not reorder/rename existing
members. Confirm any exhaustive `match`/dict over the enum handles the new member (grep for consumers).

### T008 — CLI/help + evidence-token doc
In `issue_verdict.py`: add `not-applicable` to the `--verdict` help with its non-gating meaning, and
document the evidence-token rule in `--evidence-ref` help (FR-006). Ensure `--verdict not-applicable`
validates and persists.

### T009 — Approval blocker: gating from the shared helper + terminal not-applicable + SSOT
Wire `tasks_parsing_validation.py`'s `referenced_issues` (L137) / subtract (L144) to derive the *gated*
reference set from **WP01's exported shared helper** (`gating_issue_numbers` / `is_gating`) — **import
and consume it; do NOT re-encode `ref.classification == implementation_target` here** (that fork is the
exact FR-012 defect). Make `not-applicable` non-gating at `approved` AND terminal at `done`: route it
so it never enters the `unresolved_in_mission` path (the gating flip is at L271–272, not the L296–300
message block). Encode the lever SSOT (FR-013): an operator may record any verdict on any row; a
`not-applicable` verdict makes a row non-gating regardless of classification; an
`implementation_target` classification requires a row even if none was scaffolded. WP02 owns this file;
WP03 never edits it (WP03 imports the same helper).

### T010 — ADR
Write `docs/adr/3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md` recording: the new value, its
non-gating + terminal semantics, the classification narrowing (WP01), the backward-compat rationale
(additive StrEnum, no migration), and an explicit note **superseding the never-implemented WP09
`not_applicable` Gate-4 intent** documented in `merge_gates.py` so two definitions do not diverge.
Follow `docs/architecture/README.md` / existing ADR format; add it to `docs/adr/3.x/index.md`.

## Branch Strategy

Planning base `fix/move-task-approval-ergonomics`; branches from WP01's result; merges back to the
same branch (then upstream `main` via PR). Worktree per computed lane from `lanes.json`.

## Test Strategy (ATDD / red-first — required)

T006 RED first through the `issue-verdict` + approval-transition entry points, pinned `#3469`, GREEN
after the fix. Targeted: `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/ -q -k "issue_matrix or issue_verdict or approval"`.
**NFR-002 non-regression:** also run the existing #4330 guards (JSON-first error string, batched
missing-row surfacing) as blast-radius and confirm they stay green — this WP touches the same files.

## Definition of Done

- `not-applicable` is accepted, non-gating at `approved`, terminal at `done`/merge.
- Approval blocker gates only `implementation_target` refs (from the WP01 classifier); lever SSOT
  encoded.
- Four legacy verdicts unchanged; no migration; #4330 behaviors untouched.
- ADR written + indexed, superseding the WP09 intent.
- T006 RED→GREEN; ruff + mypy --strict clean; complexity ≤15; new branches/helpers have focused tests.

## Reviewer Guidance

Confirm additivity (legacy values still parse). Confirm `not-applicable` is terminal (passes `done`),
distinct from `in-mission`. Confirm the approval blocker no longer gates non-`implementation_target`
refs. Confirm the ADR cites/supersedes the WP09 intent. Confirm C-002 (no #4330 re-fix).
