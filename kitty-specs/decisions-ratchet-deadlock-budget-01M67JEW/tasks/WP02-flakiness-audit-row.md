---
work_package_id: WP02
title: The surface is recorded where the flake policy lives
dependencies:
- WP01
requirement_refs:
- FR-006
- SC-004
- C-001
planning_base_branch: issue-6773-decisions-ratchet-deadlock-budget
merge_target_branch: issue-6773-decisions-ratchet-deadlock-budget
branch_strategy: Planning artifacts for this mission were generated on issue-6773-decisions-ratchet-deadlock-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6773-decisions-ratchet-deadlock-budget unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
phase: Phase 2 - The record
history:
- at: '2026-10-30T23:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/development/testing/testing-flakiness.md
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/development/testing/testing-flakiness.md
role: implementer
tags: []
---

# WP02 — The surface is recorded where the flake policy lives

## Context

`docs/development/testing/testing-flakiness.md` is the single flake policy and its
"Audit + disposition of known flake surfaces" table is the disposition register: every
known surface gets a row with its tier, its root cause and the sanctioned disposition.
#6773 is a newly diagnosed surface with a landed fix, so it needs a row (FR-006). Without
one, the next reader re-diagnoses it from scratch — exactly what the policy exists to
prevent.

Read first: `spec.md` (FR-006, SC-004), `plan.md` §D6, `research.md` D-1..D-5, and the
whole of `docs/development/testing/testing-flakiness.md` (the row must match the table's
existing voice and column shape: `| Surface | Tier | Disposition |`).

## Owned files

- `docs/development/testing/testing-flakiness.md` — the only file this WP edits.

Do **not** touch `docs/development/testing/testing-parallel.md`, the generated docs index,
or `src/`. No changelog entry: this is a test-and-docs change with no user-facing
behaviour change (C-001).

## T006 — The audit row

Add one row to the audit table, in the style of the existing rows (bold lead-in naming the
surface, then tier, root cause, disposition, evidence):

- **Surface**: `tests/specify_cli/decisions/test_service_terminal_concurrency.py::test_terminal_calls_do_not_deadlock_with_other_decision_lock_holders` (#6773).
- **Tier**: 2 (correctness test).
- **Root cause**: the ratchet leaned on a wall clock it did not own — the product's fixed
  10 s decisions-lock acquire bound. A holder that was merely slow surfaced as a
  `DecisionError(LOCK_TIMEOUT)` refusal and was reported as a failed worker, with no
  deadlock present. There is no lock-order cycle among the four participants, and the
  surface did not reproduce on demand (7 broad runs, 14 file runs under `-n 4`, 40
  in-process iterations).
- **Disposition**: **fixed at root cause, no retry, nothing quarantined.** The scenario now
  pins the acquire bound it runs under, one harness-owned budget decides "stuck", and a
  timed-out join reports a thread dump plus the decisions-lock holder. The refusal contract
  keeps its own coverage in `test_decisions_lock_waiter_times_out_and_writes_nothing`.
- **Evidence**: this mission's `kitty-specs/decisions-ratchet-deadlock-budget-01M67JEW/research/deadlock-budget-probe.md`.

Bump the page frontmatter `updated:` field to the day of the change (currently
`'2026-10-05'`). Keep the prose inside the table cell's one-paragraph style — no nested
lists, no new sections.

## T007 — Gates

```bash
uv run python -m scripts.docs.check_docs_freshness --ci         # expect errors=0
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

If the freshness gate reports a generated index that lists this page, regenerate only that
surface (do not rebuild the whole reference — other agents share this host's asset cache)
and re-run the gate printed above. Record both results in the WP activity log.

## Definition of done

- Exactly one new row, matching the table's column shape and voice, with tier, root cause,
  disposition and evidence pointer.
- `updated:` bumped; no other section edited.
- `check_docs_freshness --ci` → errors=0; legacy-terminology gate green.
