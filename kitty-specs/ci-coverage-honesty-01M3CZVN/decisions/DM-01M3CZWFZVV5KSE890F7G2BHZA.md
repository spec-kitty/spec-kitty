# Decision Moment `01M3CZWFZVV5KSE890F7G2BHZA`

- **Mission:** `ci-coverage-honesty-01M3CZVN`
- **Origin flow:** `specify`
- **Slot key:** `specify.escalation.nightly_red_p0_mechanism`
- **Input key:** `nightly_red_p0_mechanism`
- **Status:** `resolved`
- **Created:** `2026-09-25T19:15:13.531659+00:00`
- **Resolved:** `2026-09-25T19:31:15.132917+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a nightly run-all-regardless suite (or the newly-wired integration lane) goes red, how should CI escalate to a P0, and how should it avoid duplicate noise on consecutive red nights?

## Options

- Auto-open a GitHub issue labeled priority:P0, deduped by a stable per-suite key (reopen/update existing rather than file a new one each night)
- Fail the nightly job loudly + notify only (no auto-issue)
- Both: fail loudly AND auto-open a deduped P0 issue

## Final answer

Both: nightly run-all-regardless suites (incl. newly-wired integration lane) fail loudly AND auto-open/update a priority:P0 GitHub issue deduped by a stable per-suite key (reopen/update existing, not a new issue each night).

## Rationale

_(none)_

## Change log

- `2026-09-25T19:15:13.531659+00:00` — opened
- `2026-09-25T19:31:15.132917+00:00` — resolved (final_answer="Both: nightly run-all-regardless suites (incl. newly-wired integration lane) fail loudly AND auto-open/update a priority:P0 GitHub issue deduped by a stable per-suite key (reopen/update existing, not a new issue each night).")
