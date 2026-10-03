# Decision Moment `01M3RM0GV7C890S8BQR1J8JTVP`

- **Mission:** `in-harness-feedback-survey-01M3PK9W`
- **Origin flow:** `plan`
- **Slot key:** `plan.architecture.trigger-surfacing`
- **Input key:** `survey_surfacing`
- **Status:** `resolved`
- **Created:** `2026-09-30T07:38:35.751591+00:00`
- **Resolved:** `2026-09-30T07:45:52.077036+00:00`
- **Opened by:** `cursor`
- **Other answer:** `false`

## Question

How is the survey surfaced at trigger points?

## Options

- Post-step agent-check block in trigger templates + inline TTY prompt for humans
- Trigger commands embed a feedback_survey offer in their JSON output
- Other

## Final answer

Upgrade-check style post-step block in trigger prompts/skills (agent-check -> native ask -> agent-submit) plus inline TTY prompt for humans; trigger commands' JSON contracts unchanged

## Rationale

_(none)_

## Change log

- `2026-09-30T07:38:35.751591+00:00` — opened
- `2026-09-30T07:45:52.077036+00:00` — resolved (final_answer="Upgrade-check style post-step block in trigger prompts/skills (agent-check -> native ask -> agent-submit) plus inline TTY prompt for humans; trigger commands' JSON contracts unchanged")
