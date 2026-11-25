# Decision Moment `01M7VRSF1T1ENCAMW2SACF5MS3`

- **Mission:** `skill-surfaces-converge-01M7VRS0`
- **Origin flow:** `specify`
- **Slot key:** `specify.doctor.old-root-fix`
- **Input key:** `old_root_fix_policy`
- **Status:** `resolved`
- **Created:** `2026-11-20T06:02:38.010253+00:00`
- **Resolved:** `2026-11-20T06:31:06.215518+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

May doctor --fix ever remove a proven-generated stale file under the old ~/.claude root when CLAUDE_CONFIG_DIR redirects the resolved root, or only report it?

## Options

- A: report only, with a cleanup hint; delete nothing
- B: --fix removes only byte-proven files there; unproven ones reported
- Other

## Final answer

A: report only in this PR (list proven files with an rm hint, delete nothing); file a P3 follow-up for opt-in --fix removal of byte-proven files under the old root, linked to #7723 (operator ruling via orchestrator 2026-11-20)

## Rationale

_(none)_

## Change log

- `2026-11-20T06:02:38.010253+00:00` - opened
- `2026-11-20T06:31:06.215518+00:00` - resolved (final_answer="A: report only in this PR (list proven files with an rm hint, delete nothing); file a P3 follow-up for opt-in --fix removal of byte-proven files under the old root, linked to #7723 (operator ruling via orchestrator 2026-11-20)")
