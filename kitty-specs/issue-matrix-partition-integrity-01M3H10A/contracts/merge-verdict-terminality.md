# Contract: Merge verdict-terminality enforcement

Behavioral contract for the merge path applying the terminal-verdict rule (FR-006), mirroring
`tasks_move_task.py::_issue_matrix_approval_blocker`. Backed by ATDD tests.

## Trigger

`spec-kitty merge` recording work packages `done` / advancing the target, on any topology.

## Guarantees

1. **Block mode** — with `policy.merge_gates.mode: block`, if any **gating** row is non-terminal
   (`in-mission` or `unknown`), merge REFUSES before the target advances and names the offending
   row(s). *(US3.1)*
2. **Warn mode** — with `mode: warn`, merge still advances and records the work packages `done`, but
   prints the same unresolved-row list the `done` transition prints. The change from today is the
   surfaced warning, not a changed landing outcome under `warn`. *(US3.2)*
3. **Positive control** — the same mission with the row resolved to a terminal verdict advances in
   either mode with no verdict-terminality complaint. *(US3.3)*
4. **Correct partition** — the verdict read that feeds this rule resolves from the COORD partition /
   branch ref (per the issue-matrix-read contract), including post-consolidation; it never reads the
   PRIMARY residue. *(FR-004, FR-005; witnessed US4.2)*
5. **Rule reuse** — the terminality classification is the existing one (`unknown`/`in-mission`
   non-terminal; `fixed`/`verified-already-fixed`/`deferred-with-followup`/`not-applicable` terminal);
   merge does not re-define verdict semantics.

## Failure modes closed

- Merge landing a mission whose gating row is still `in-mission` with exit 0 (the #4943 leg-2 bug).
- The coord husk read making the gate see "nothing to enforce" (the #4943 leg-1 bug — closed by the
  issue-matrix-read contract's partition split).
