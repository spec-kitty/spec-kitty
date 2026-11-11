# Decision Moment `01M75NY6CET5GK3CZ4QEEBJXGC`

- **Mission:** `cli-owns-its-commits-01M75NTA`
- **Origin flow:** `specify`
- **Slot key:** `specify.init.protected-branch`
- **Input key:** `init_protected_branch`
- **Status:** `resolved`
- **Created:** `2026-11-11T16:09:29.742549+00:00`
- **Resolved:** `2026-11-11T16:09:32.282548+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

init on a protected branch (main) inside a git repository: commit there, or leave the files?

## Options

_(none)_

## Final answer

Commit through the existing upgrade bookkeeping committer (baseline-diff set, the one holder of the scaffold-bookkeeping capability), so init behaves like upgrade on the same branch; --no-commit opts out. Flagged for operator review in the PR. Operator absent (cloud dispatch).

## Rationale

_(none)_

## Change log

- `2026-11-11T16:09:29.742549+00:00` - opened
- `2026-11-11T16:09:32.282548+00:00` - resolved (final_answer="Commit through the existing upgrade bookkeeping committer (baseline-diff set, the one holder of the scaffold-bookkeeping capability), so init behaves like upgrade on the same branch; --no-commit opts out. Flagged for operator review in the PR. Operator absent (cloud dispatch).")
