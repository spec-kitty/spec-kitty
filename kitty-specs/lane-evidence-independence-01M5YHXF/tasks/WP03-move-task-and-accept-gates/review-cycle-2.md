---
affected_files: []
cycle_number: 2
mission_slug: lane-evidence-independence-01M5YHXF
reproduction_command:
reviewed_at: '2026-10-29T10:02:06Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (reviewer-renata), cycle 2

Verdict: changes requested, for one blocking finding. It is a one-line fix.

The cycle-1 blocker is fixed as the 2026-10-29 ruling requires:

- **Ruling B.** `preflight._latest_actor_for_transition` reads a generic placeholder as unknown.
  The placeholder set has one authority: `GENERIC_IMPLEMENTATION_ACTORS` via `_actor_key` from the
  status facade. An attestation is still skipped before the placeholder check.
- **Ruling A.** At the move, `_mt_approval_actor` reproduces what the executor records, and the
  move refuses a placeholder. `--force` still bypasses it.
- **Flows.** My no-`--agent` self-approval flow now refuses at the move. Forced past the move, it
  refuses at accept and at consolidate. A bare approval after `agent action review --agent bob`
  lands.
- **Re-pins.** They keep their intent. In `test_tasks.py` and `test_verdict_attribution_4670.py`,
  the walk now stops at the review claim and the refused approval is pinned. In
  `test_owned_checkout_move_task.py`, adding `--agent reviewer` moves the runtime agent slot from
  `implementer` to `reviewer`. The test is about selected-checkout isolation, so that slot
  assertion was incidental, and it is still asserted exactly. `test_move_task_approval_body_collision.py`
  is the same.
- **Cycle-1 nits.** Both fixed: `widened_lane_paths` is the one widening rule, and the lanes
  variant asserts `IMPLEMENTATION_MISSING: WP02`.
- **`731c8f6e`.** Fine: the lift notice now uses the strict reader, so a read error goes into
  consolidate's rollback.
- **Tests.** The targeted run passed 485, including `test_no_dead_symbols`,
  `test_status_module_boundary` and `test_layer_rules`.

## Blocking

**1. The privatisation commit changed an emitted, documented refusal code (`d6422768`).**
- Where: `src/specify_cli/consolidation/wp_evidence.py:59` reads
  `_SINGLE_BRANCH_EVIDENCE_UNREADABLE = "_SINGLE_BRANCH_EVIDENCE_UNREADABLE"`. The rename also
  rewrote the string VALUE, not only the name.
- Effect: a single_branch Mission whose evidence window cannot be diffed now refuses with
  `_SINGLE_BRANCH_EVIDENCE_UNREADABLE: ...`. The same value reaches the orchestrator-api
  `data.preflight_error_codes`.
- That code is the shipped #5939 alias. `kitty-specs/lane-evidence-independence-01M5YHXF/contracts/refusal-codes.md`
  documents it, and so does the orchestrator-api 1.19.0 note ("single_branch keeps emitting its
  documented `SINGLE_BRANCH_*` aliases"). A consumer keying on `SINGLE_BRANCH_EVIDENCE_UNREADABLE`
  no longer matches.
- The tests stayed green only because they compare against the constant
  (`test_single_branch_evidence_axis.py:220`, `test_wp_evidence.py:127`), not against the literal.
- Required fix:
  - Restore the value `"SINGLE_BRANCH_EVIDENCE_UNREADABLE"`. The constant may stay private.
  - Pin the literal in a test (for example `assert ... startswith("SINGLE_BRANCH_EVIDENCE_UNREADABLE: ")`)
    so a future rename cannot change it silently.
  - Re-check that no other constant's value changed in that commit. I grepped and found only this one.
