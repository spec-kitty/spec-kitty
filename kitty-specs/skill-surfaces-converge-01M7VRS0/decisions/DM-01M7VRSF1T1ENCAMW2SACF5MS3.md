# Decision Moment `01M7VRSF1T1ENCAMW2SACF5MS3`

- **Mission:** `skill-surfaces-converge-01M7VRS0`
- **Origin flow:** `specify`
- **Slot key:** `specify.doctor.old-root-fix`
- **Input key:** `old_root_fix_policy`
- **Status:** `deferred`
- **Created:** `2026-11-20T06:02:38.010253+00:00`
- **Resolved:** `2026-11-20T06:05:14.650832+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

May doctor --fix ever remove a proven-generated stale file under the old ~/.claude root when CLAUDE_CONFIG_DIR redirects the resolved root, or only report it?

## Options

- A: report only, with a cleanup hint; delete nothing
- B: --fix removes only byte-proven files there; unproven ones reported
- Other

## Final answer

_(none)_

## Rationale

Raised to the operator via the orchestrator; working assumption A (report only) until answered

## Change log

- `2026-11-20T06:02:38.010253+00:00` - opened
- `2026-11-20T06:05:14.650832+00:00` - deferred
