# Tracer — Tooling Friction

Mission: move-task / approval-gate ergonomics (#3469)

## Seed (planning)

This mission *is* a tooling-friction remediation — the friction is the subject. Seed observations
from grounding + this mission's own run:

- The very defects under fix (over-broad issue-matrix gating, no truthful verdict, missing flag
  aliases) are friction this mission's own approval step would hit. Watch for and record any
  recurrence while dogfooding.
- Grounding found several reported sub-defects already fixed on main (#4330) or by-design
  (#2816). Friction: the issue text drifts from current behavior — reproduce-before-fix mattered.

## Appended during implement

**Live dogfood at WP04 approval (2026-09-20):** moving WP04 `--to approved` hit the exact defect this
mission fixes. The gate demanded issue-matrix verdicts for `#2816`, `#3454`, `#3469`, `#4330` — but
only `#3469` is the mission's actual target; `#2816` (event-sourced subtasks, coordinated-around),
`#3454` (umbrella parent), and `#4330` (already-landed work we build on) are all context-only
citations. On the INSTALLED (pre-fix) CLI there is NO truthful verdict for them — the allowed set is
`fixed | verified-already-fixed | deferred-with-followup | in-mission`. Forced to record
`deferred-with-followup` with evidence stating the truth ("context-only, no work owed, no follow-up
intended") — precisely MOES-Media's documented workaround in #3469. **After this mission merges,
`not-applicable` will be the honest value AND these context-only refs won't be scaffolded as gating
rows at all.**

Confirmations that #4330 already landed (validated live): the error was BATCHED (all 4 rows in one
message, not one-at-a-time) and named `issue-matrix.json` (not `.md`). Both correctly excluded from
this mission's scope.
