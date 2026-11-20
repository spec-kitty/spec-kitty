# Decision Moment `01M7VRSCZZPMQHPVF9HP5T4HM9`

- **Mission:** `skill-surfaces-converge-01M7VRS0`
- **Origin flow:** `specify`
- **Slot key:** `specify.proof.digest-list-home`
- **Input key:** `digest_list_home`
- **Status:** `deferred`
- **Created:** `2026-11-20T06:02:35.903966+00:00`
- **Resolved:** `2026-11-20T06:05:12.445178+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where does the frozen historical-render digest list live, and how is it regenerated per release?

## Options

- A: reviewed JSON package-data file + committed git-history generator; append-only test fails if a digest is dropped or a current render is missing (regenerate in the skill-edit PR)
- B: same file, regenerated only at release via checklist
- C: Python module constant
- Other

## Final answer

_(none)_

## Rationale

Raised to the operator via the orchestrator; working assumption A until answered

## Change log

- `2026-11-20T06:02:35.903966+00:00` - opened
- `2026-11-20T06:05:12.445178+00:00` - deferred
