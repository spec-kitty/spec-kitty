---
affected_files: []
cycle_number: 1
mission_slug: lane-evidence-independence-01M5YHXF
reproduction_command:
reviewed_at: '2026-10-29T07:03:31Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (reviewer-renata), cycle 1

Verdict: changes requested, for one blocking finding.

What holds up:
- The move evidence gate runs on every topology and lane kind through `wp_evidence`.
- The issue's coord flow refuses `IMPLEMENTATION_MISSING` at the move, and a non-owned lane commit
  does not count.
- A positively-same identity refuses `REVIEW_NOT_INDEPENDENT`.
- The accept preflight is strict regardless of `--lenient` and records the attestation first.
- `--force` bypasses the move gates.
- One owned-file matcher remains (the `_mt_*` helpers delegate to `wp_evidence`).
- The single_branch wording assertions are unchanged.
- The re-pins I sampled keep their intent and no assertion was removed: the rework harness,
  `reject_fix_approve_cycle`, `4905_coord_staging`, `approval_body_collision`, `fixmode_ownership`,
  `accept_clean_tree` and `single_branch_refusal_wording`.
- Targeted run: 155 passed.

## Blocking

**1. An implementer can self-approve real work by omitting `--agent`, and it lands at accept and consolidate as an independent review (decision 4).**
- Reproduced through the real CLI on a coord Mission. Probe:
  `/tmp/claude-0/-home-user-spec-kitty/98a00833-f8c1-5968-adf2-832916f6ed94/scratchpad/probe/test_noagent_probe.py`.
  1. `claude` implements WP02 (`agent action implement --agent claude`) and commits its owned file.
  2. `claude` runs `move-task WP02 --to approved --note lgtm` with no `--agent` and no `--force`.
     Exit 0. The auto-walk records `for_review -> in_review -> approved` with the actor
     `{tool: "user", role: "reviewer"}`.
  3. `accept --lenient` exits 0.
  4. `consolidate` exits 0, and every WP is `done`.
- Why: at the move, `_mt_approver_identity` returns `None` without `--agent`
  (tasks_move_task.py, `_mt_approver_identity`), so `_mt_require_independent_approval` skips the
  check. The executor then records the generic placeholder `user` (`st.actor = st.agent or ... or "user"`).
  At accept and consolidate, `_independent_reviewer_confirmed` compares `claude::` with `user::`,
  sees two different identities, and confirms an independent review.
- The implementer side already treats `user` as no identity: `review_roles._qualifies` excludes
  `GENERIC_IMPLEMENTATION_ACTORS`. The approver side does not.
- This is User Story 2 (self-approval refused) failing at every surface. It needs no `--force`;
  the only step is leaving out a flag.
- Required fix:
  - **(B) Required.** Make the strict backstop read a generic placeholder approver as unknown.
    `preflight._latest_actor_for_transition` should skip an event whose actor key is in
    `GENERIC_IMPLEMENTATION_ACTORS` (or a shared generic-actor set). With no confirmable reviewer,
    `_independent_reviewer_confirmed` is then False, and accept and consolidate refuse
    `REVIEW_NOT_INDEPENDENT`. This matches #5939's own definition ("False when either actor is
    missing/unknown"), so it does not change the identity comparison of ruling 1. It is an
    out-of-map edit to `preflight.py`; record the rationale.
  - **(A) Optional, needs an operator ruling.** At the move, refuse an unforced approval that would
    record a generic placeholder approver (no `--agent`, no binding, no review claimer), telling
    the operator to pass `--agent`. The current ruling only allows a positively-same identity to
    refuse at the move, so do (A) only if the operator extends the ruling.
  - Add regression coverage: the probe flow must refuse at accept and at consolidate with
    `REVIEW_NOT_INDEPENDENT`. Also check that real reviews still pass: with `--agent bob`, and
    through `agent action review` followed by a bare approval out of `in_review` (the review
    claimer is resolved).

## Non-blocking

- **Decision 2, not re-checking `for_review/in_review -> approved` at the move.** Acceptable under
  the force ruling (C-004): the hollow WP got into review through a forced hop, and accept and
  consolidate refuse it. The issue's exact flow (an unforced move from below) refuses at the move.
  Record it in the WP04 decision record.
- **Decision 1, `--diagnose` now exits 1 before the readiness summary.** A report mode now prints
  only the evidence refusal. Consider folding the evidence refusal into the diagnose report as a
  blocked check (exit 1 kept), so the rest of the report stays visible. Exit 2 for
  `--attest-no-implementation` with `--no-commit` or `--diagnose` is fine.
- **Decisions 3 and 5** (independence in owned checkouts and single_branch with the alias code;
  the gate running after the deferred `for_review` auto-commit): both fine.
- **`_mt_lane_window_paths` duplicates the widening rule.** It re-implements the "widen by
  dependency windows when no owned change shows" rule of `wp_evidence._scan_lane` /
  `_widened_paths`. The windows come from `wp_evidence`, but deciding when to widen now lives in
  two places (DIRECTIVE_044). Expose one `wp_evidence` function that returns a lane's evidence
  paths for a set of patterns, and call it from both.
- **`test_hollow_self_approval_is_refused_at_the_move[lanes]`** asserts only that "implementation"
  appears in the output. Assert `IMPLEMENTATION_MISSING: WP02` on lanes too; the code leads the
  message there as well.
