# Decision Moment `01M75NY1Q2F35PYMESZB0S5DWN`

- **Mission:** `cli-owns-its-commits-01M75NTA`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.outside-mission-dirt`
- **Input key:** `outside_mission_dirt`
- **Status:** `resolved`
- **Created:** `2026-11-11T16:09:24.962372+00:00`
- **Resolved:** `2026-11-11T16:09:27.322609+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a gate that guards a Mission write sees dirt outside every Mission (for example src/ edits), does it refuse or warn?

## Options

_(none)_

## Final answer

Per #7556: record-analysis commits only its report, so dirt outside the Mission is a warning there; the single_branch implement claim keeps refusing on code dirt (the WP commits code in that checkout) and only another Mission's kitty-specs/ files become a warning. Operator absent (cloud dispatch); answer taken from the issue's Expected section.

## Rationale

_(none)_

## Change log

- `2026-11-11T16:09:24.962372+00:00` - opened
- `2026-11-11T16:09:27.322609+00:00` - resolved (final_answer="Per #7556: record-analysis commits only its report, so dirt outside the Mission is a warning there; the single_branch implement claim keeps refusing on code dirt (the WP commits code in that checkout) and only another Mission's kitty-specs/ files become a warning. Operator absent (cloud dispatch); answer taken from the issue's Expected section.")
