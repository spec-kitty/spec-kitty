# Decision Moment `01M4KC04NV3A879MWDYGAK4EJA`

- **Mission:** `destructive-residue-context-01M4KBPS`
- **Origin flow:** `plan`
- **Slot key:** `plan.scope.rmtree-in-gate`
- **Input key:** `rmtree_in_gate`
- **Status:** `resolved`
- **Created:** `2026-10-10T16:58:04.347733+00:00`
- **Resolved:** `2026-10-10T16:58:05.954900+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should the architectural gate also forbid shutil.rmtree of a git checkout outside the destructive guard?

## Options

- Yes
- No
- Other

## Final answer

Yes: the gate also forbids shutil.rmtree of a git checkout path outside the destructive guard.

## Rationale

_(none)_

## Change log

- `2026-10-10T16:58:04.347733+00:00` — opened
- `2026-10-10T16:58:05.954900+00:00` — resolved (final_answer="Yes: the gate also forbids shutil.rmtree of a git checkout path outside the destructive guard.")
