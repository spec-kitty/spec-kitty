# Contract — Adversarial evidence

Every adversarial-squad point-cut records each contested finding's disposition; none may be
silently dropped. Dispositions: `accepted` (finding stands, folded), `changed` (spec/plan altered
in response), or `deferred_with_rationale` (not folded now, with a recorded reason).

## Ledger (see research.md for the full table)

- **Post-spec squad #4858** (architect-alphonso, debugger-debbie, reviewer-renata): all findings
  `changed` or `accepted` — see `../research.md` §Adversarial evidence.
- **Post-spec squad #4868 + fold coherence** (debugger-debbie, reviewer-renata): all findings
  `changed` or `accepted` — see `../research.md` §Adversarial evidence.
- **Post-plan squad**: to run after plan artifacts land; dispositions appended here + tracer.
- **Pre-merge squad**: to run over the final diff before the PR; dispositions appended here.

## Rule

No `deferred_with_rationale` disposition may hide a correctness gap. A deferral must name the
follow-up (tracker item or explicit out-of-scope line) and a reviewer must be able to see it.
