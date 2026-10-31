# Decision Moment `01M68ZS774P1AQYYB44TPV45PR`

- **Mission:** `activation-writes-under-synthesis-lock`
- **Origin flow:** `specify`
- **Step id:** `specify.scope_boundaries`
- **Input key:** `scope_boundaries`
- **Status:** `resolved`
- **Created:** `2026-10-31T12:43:33.988842+00:00`
- **Resolved:** `2026-10-31T12:45:40.736016+00:00`
- **Opened by:** `22272470+Ivan-Melck@users.noreply.github.com`
- **Other answer:** `false`

## Question

What is explicitly out of scope for this Mission?

## Options

_(none)_

## Final answer

Out of scope: inventing a new lock or lock scope (the existing run-wide synthesis lock from #6453 is reused); the compiled-catalog write reached from the post-write recompile_or_notify (a staleness question re-derived by the next synthesis run, not a lost-write one); activation writers other than activate/deactivate/preset/the org-required promotion primitive and the ledger migration; and any change to the other pre-existing red-on-main suites (#6798, #6801, #6816, #5927).

## Rationale

_(none)_

## Change log

- `2026-10-31T12:43:33.988842+00:00` — opened
- `2026-10-31T12:45:40.736016+00:00` — resolved (final_answer="Out of scope: inventing a new lock or lock scope (the existing run-wide synthesis lock from #6453 is reused); the compiled-catalog write reached from the post-write recompile_or_notify (a staleness question re-derived by the next synthesis run, not a lost-write one); activation writers other than activate/deactivate/preset/the org-required promotion primitive and the ledger migration; and any change to the other pre-existing red-on-main suites (#6798, #6801, #6816, #5927).")
