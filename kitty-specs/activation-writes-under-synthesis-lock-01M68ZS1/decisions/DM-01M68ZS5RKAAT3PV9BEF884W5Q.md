# Decision Moment `01M68ZS5RKAAT3PV9BEF884W5Q`

- **Mission:** `activation-writes-under-synthesis-lock`
- **Origin flow:** `specify`
- **Step id:** `specify.problem_statement`
- **Input key:** `problem_statement`
- **Status:** `resolved`
- **Created:** `2026-10-31T12:43:32.499294+00:00`
- **Resolved:** `2026-10-31T12:45:30.802319+00:00`
- **Opened by:** `22272470+Ivan-Melck@users.noreply.github.com`
- **Other answer:** `false`

## Question

What problem does this Mission solve?

## Options

_(none)_

## Final answer

Two write paths still race charter synthesis without the run-wide synthesis lock (#6453). (1) charter activate/deactivate write the activation config outside the lock, so a deactivation that lands inside a synthesis run's activation-append window is lost: synthesis's stale read either overwrites it or the deactivation refuses with precondition_changed and the artifact stays in force. (2) The activation-ledger migration's manifest stamp (activation_ledger._stamp_manifest) reads and rewrites the whole synthesis manifest unlocked, so it can drop manifest entries a concurrent synthesis run just wrote. Grounded on main at 6f73b2a98e: neither writer takes the lock (issue #6719).

## Rationale

_(none)_

## Change log

- `2026-10-31T12:43:32.499294+00:00` — opened
- `2026-10-31T12:45:30.802319+00:00` — resolved (final_answer="Two write paths still race charter synthesis without the run-wide synthesis lock (#6453). (1) charter activate/deactivate write the activation config outside the lock, so a deactivation that lands inside a synthesis run's activation-append window is lost: synthesis's stale read either overwrites it or the deactivation refuses with precondition_changed and the artifact stays in force. (2) The activation-ledger migration's manifest stamp (activation_ledger._stamp_manifest) reads and rewrites the whole synthesis manifest unlocked, so it can drop manifest entries a concurrent synthesis run just wrote. Grounded on main at 6f73b2a98e: neither writer takes the lock (issue #6719).")
