---
affected_files: []
cycle_number: 1
mission_slug: next-lifecycle-integrity-01M77BWP
reproduction_command:
reviewed_at: '2026-11-12T11:10:44Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review (reviewer-renata): changes requested. Docs only; the code is approved as-is.

The code in `runtime_bridge_query.py` is correct. The `next_command` table is implemented exactly: the first decision keeps its fields through `PendingDecisionPrompt`, there is one door read, and every 4-tuple caller is updated. The tests went red first, then green, and ruff, format, mypy and C901 are clean. Do not change the code. Two problems in the docs block approval, because the Review Guidance requires that "the docs match the shipped behaviour". Both put wrong instructions in front of agents.

**Issue 1 (blocking): the `terminal` guidance now skips acceptance for every Mission that reaches `terminal` without the new gate.**

Where:
- `docs/architecture/runtime-loop.md:199-207` (the `terminal` section);
- `runtime-loop.md:253` (Agent Loop step 6, "consolidate if the Mission has not landed");
- `src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md`: the kind table (`terminal | Mission accepted, or landed`), the Next Action table (`terminal | Accepted or landed: consolidate...`) and step 4 of the bash loop.

Why it is wrong:
- The gate is software-dev only, and only for a finalized board (decision `plan.next.gate_scope_family`).
- Documentation, research, plan and custom Missions, and a no-WP software-dev Mission, still get `kind=terminal` when the run completes, with no acceptance.
- `spec-kitty accept` is the canonical step there (see `acceptance/non_wp_runtime.py` for the `plan` family), and `consolidate` does not gate on acceptance. An agent that follows the new text consolidates an unaccepted Mission.
- It also contradicts WP03's own query row: `mission_state: "done"` with no finished board names `spec-kitty accept`.

Fix: say that `terminal` means one of two things:
- for a software-dev Mission with a finalized board: accepted, or landed;
- otherwise: the run completed. Run `spec-kitty accept --mission <slug>` if it is not accepted, then consolidate.

Keep the bash loop handling `terminal` with accept-then-consolidate for those Missions.

**Issue 2 (blocking): the never-rewind rules are stated unconditionally, but they apply only when the run is not authoritative.**

Spec FR-006, FR-016 and the operator ruling `authoritative_run_scope` (A: split by use) limit them that way. Where:
- `runtime-loop.md:209-235`: "Once a software-dev Mission has a finalized work-package board, an advancing `next` never sends... A finished board... returns `blocked`... for every `--result`" and "A claimable work package is dispatched from the board as before";
- `SKILL.md`, "A finished software-dev board is never rewound... for any `--result`", and the Known Issues entry for #335.

These statements contradict three cases in the planned WP02 behaviour:
- (a) FR-006 positive control: a run legitimately at `review`, with the last WP approved, issues the runtime `accept` step, not `MISSION_AWAITING_ACCEPTANCE`.
- (b) Ruling A: a run at `tasks` with a dispatchable board advances through the engine to `analyze`. It is not dispatched from the board. Board dispatch only overrides runs that are absent, untouched, or at discovery, research, specify or plan.
- (c) Runs at analyze, implement, review or accept keep the runtime path.

Fix: scope the section to a run that is not authoritative (no run, untouched, or issued at a planning step before `analyze`; for board dispatch, `tasks` is excluded). State the authoritative cases (a)–(c) as unchanged. Mirror the same qualifier in `SKILL.md`. Re-check the wording against WP02's final behaviour before the next review.

**Minor (not blocking):**
- `tests/next/test_query_next_command_7553.py` reaches the runtime-terminal row (`mission_state="done"` with no board) only through the `_query_next_command` unit. That is acceptable, but an end-to-end cell would be stronger if a fixture is cheap.
