# Decision Moment `01M7VRSCZZPMQHPVF9HP5T4HM9`

- **Mission:** `skill-surfaces-converge-01M7VRS0`
- **Origin flow:** `specify`
- **Slot key:** `specify.proof.digest-list-home`
- **Input key:** `digest_list_home`
- **Status:** `resolved`
- **Created:** `2026-11-20T06:02:35.903966+00:00`
- **Resolved:** `2026-11-20T06:31:04.129625+00:00`
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

A: reviewed package-data JSON plus a committed git-history generator; append-only; a test fails on a missing current render so skill-edit PRs re-run the generator; RELEASE_CHECKLIST step (operator ruling via orchestrator 2026-11-20)

## Rationale

_(none)_

## Change log

- `2026-11-20T06:02:35.903966+00:00` - opened
- `2026-11-20T06:31:04.129625+00:00` - resolved (final_answer="A: reviewed package-data JSON plus a committed git-history generator; append-only; a test fails on a missing current render so skill-edit PRs re-run the generator; RELEASE_CHECKLIST step (operator ruling via orchestrator 2026-11-20)")
