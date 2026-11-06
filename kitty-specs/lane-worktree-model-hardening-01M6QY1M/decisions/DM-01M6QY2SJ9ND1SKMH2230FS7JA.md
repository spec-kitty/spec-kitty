# Decision Moment `01M6QY2SJ9ND1SKMH2230FS7JA`

- **Mission:** `lane-worktree-model-hardening-01M6QY1M`
- **Origin flow:** `specify`
- **Slot key:** `specify.rulings.default-topology`
- **Input key:** `default_topology`
- **Status:** `resolved`
- **Created:** `2026-11-06T08:02:27.017677+00:00`
- **Resolved:** `2026-11-06T08:02:29.368253+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

Ruling 1: how is a Mission's default topology chosen (reversing the #5100 explicit-only rule)?

## Options

_(none)_

## Final answer

Default topology by Mission size, reversing the #5100 explicit-only rule. single_branch when the finalized tasks have <=2 WPs or lane computation yields one lane; lanes otherwise. An explicit --topology always wins. Applied at finalize-tasks, because create runs before WPs exist. Needs an ADR. S8 must land before or with S7.

## Rationale

Operator ruling, stijn-dejongh, 2026-11-06 (epic #7276). Quoted as given.

## Change log

- `2026-11-06T08:02:27.017677+00:00` - opened
- `2026-11-06T08:02:29.368253+00:00` - resolved (final_answer="Default topology by Mission size, reversing the #5100 explicit-only rule. single_branch when the finalized tasks have <=2 WPs or lane computation yields one lane; lanes otherwise. An explicit --topology always wins. Applied at finalize-tasks, because create runs before WPs exist. Needs an ADR. S8 must land before or with S7.")
