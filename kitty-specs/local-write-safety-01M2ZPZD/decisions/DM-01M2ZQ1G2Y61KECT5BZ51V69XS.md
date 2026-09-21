# Decision Moment `01M2ZQ1G2Y61KECT5BZ51V69XS`

- **Mission:** `local-write-safety-01M2ZPZD`
- **Origin flow:** `specify`
- **Slot key:** `specify.init-safety.destructive-policy`
- **Input key:** `init_destructive_policy`
- **Status:** `resolved`
- **Created:** `2026-09-20T15:30:32.670100+00:00`
- **Resolved:** `2026-09-20T15:33:31.420957+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When spec-kitty init finds user-authored .kittify/missions or memory but no config.yaml, what should it do?

## Options

- Refuse with guidance
- Back up then proceed
- Merge (never delete user content)
- Other

## Final answer

Back up, then proceed: when init re-runs on a populated .kittify/ that is missing config.yaml, move existing operator-authored content (custom missions, memory notes) into a timestamped .kittify/.backup-<UTC-timestamp>/ before copying scaffold, and report the backup path to the user. Never rmtree operator-owned content.

## Rationale

_(none)_

## Change log

- `2026-09-20T15:30:32.670100+00:00` — opened
- `2026-09-20T15:33:31.420957+00:00` — resolved (final_answer="Back up, then proceed: when init re-runs on a populated .kittify/ that is missing config.yaml, move existing operator-authored content (custom missions, memory notes) into a timestamped .kittify/.backup-<UTC-timestamp>/ before copying scaffold, and report the backup path to the user. Never rmtree operator-owned content.")
