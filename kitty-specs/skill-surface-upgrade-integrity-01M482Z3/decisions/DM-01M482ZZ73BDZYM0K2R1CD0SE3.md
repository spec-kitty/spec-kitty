# Decision Moment `01M482ZZ73BDZYM0K2R1CD0SE3`

- **Mission:** `skill-surface-upgrade-integrity-01M482Z3`
- **Origin flow:** `specify`
- **Slot key:** `specify.fix.doctor-fix-behaviour`
- **Input key:** `doctor_fix_behaviour`
- **Status:** `resolved`
- **Created:** `2026-10-06T07:49:02.819137+00:00`
- **Resolved:** `2026-10-06T07:53:47.230668+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When doctor skills finds an in-force pack skill that is missing, should --fix project it itself (via project_pack_skills) or only report it and name spec-kitty upgrade?

## Options

- Project it in --fix (recommended)
- Report only, name spec-kitty upgrade
- Other

## Final answer

Project it in --fix via project_pack_skills, then re-check. Additionally: doctor must fail when NO configured (charter-supported) harness folder exists locally; at least one is required, not all.

## Rationale

_(none)_

## Change log

- `2026-10-06T07:49:02.819137+00:00` — opened
- `2026-10-06T07:53:47.230668+00:00` — resolved (final_answer="Project it in --fix via project_pack_skills, then re-check. Additionally: doctor must fail when NO configured (charter-supported) harness folder exists locally; at least one is required, not all.")
